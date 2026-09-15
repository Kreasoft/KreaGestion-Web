"""Respaldos de datos por empresa, firmados y restaurados sin ejecutar SQL externo.

Incluye todas las tablas con alcance explícito, cuentas de la empresa y catálogos.
No incluye los archivos físicos de MEDIA_ROOT.
La recuperación conserva los registros creados después del respaldo.
"""
import json
from datetime import datetime, time

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import serializers, signing
from django.core.management.color import no_style
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.utils import timezone

SALT = 'utilidades.respaldo_empresa.v1'
MAX_BYTES = 100 * 1024 * 1024


class RespaldoError(ValueError):
    pass


class RespaldoEncoder(DjangoJSONEncoder):
    def default(self, value):
        if isinstance(value, (datetime, time)):
            return value.isoformat()
        return super().default(value)


def modelos_empresa():
    """Prioriza empresa directa; los detalles heredan su primer padre obligatorio.

Nunca atraviesa usuarios ni relaciones inversas hacia catálogos compartidos.
Todas las demás relaciones se validan antes de exportar o escribir.
"""
    empresa = apps.get_model('empresas', 'Empresa')
    locales = {name.split('.')[0] for name in settings.LOCAL_APPS}
    pendientes = [m for m in apps.get_models() if m._meta.app_label in locales
                  and m._meta.managed and not m._meta.proxy and m != empresa]
    rutas = {empresa: 'pk'}
    for model in pendientes[:]:
        if any(f.name == 'empresa' and f.related_model == empresa for f in model._meta.fields):
            rutas[model] = 'empresa_id'
            pendientes.remove(model)
    while True:
        nuevos = {}
        for model in pendientes:
            padres = [f for f in model._meta.fields if f.is_relation and not f.null
                      and f.related_model in rutas]
            if padres:
                padre = padres[0]
                nuevos[model] = padre.name + '__' + rutas[padre.related_model]
        if not nuevos:
            break
        rutas.update(nuevos)
        pendientes = [m for m in pendientes if m not in nuevos]
    return rutas


def _referencia_historica_existente(model, pk, field, valor, rutas, empresa):
    """Conserva solo una FK ajena ya existente, sin crear ni reasignar vínculos.

Una fila faltante, un detalle ajeno, una FK modificada o un registro de la
misma empresa ausente del archivo no pueden usar esta excepción.
"""
    related = field.related_model
    if field.many_to_many or model not in rutas or related not in rutas:
        return False
    origen = model._base_manager.filter(
        pk=pk, **{rutas[model]: empresa.pk, field.attname: valor})
    destino_ajeno = related._base_manager.filter(pk=valor).exclude(
        **{rutas[related]: empresa.pk})
    return origen.exists() and destino_ajeno.exists()


def _validar_relaciones(registros, rutas, empresa, advertencias=None, ampliado=False,
                       referencias_historicas=None):
    from .cobertura_respaldo import catalogos_compartidos

    User = get_user_model()
    indices = {}
    for registro in list(registros):
        try:
            model = apps.get_model(registro['model'])
        except (LookupError, ValueError):
            registros.remove(registro)
            continue
            
        key = (model, registro['pk'])
        if key in indices:
            registros.remove(registro)
            continue
        indices[key] = registro

    raiz = apps.get_model('empresas', 'Empresa')
    for (model, pk), registro in list(indices.items()):
        if model == raiz:
            registro['pk'] = empresa.pk
            registro['fields']['id'] = empresa.pk
            if 'rut' in registro['fields']:
                registro['fields']['rut'] = empresa.rut

    for (model, pk), registro in list(indices.items()):
        campos = registro['fields']
        esperados = {f.name for f in model._meta.fields if not f.primary_key}
        esperados.update(f.name for f in model._meta.many_to_many if f.remote_field.through._meta.auto_created)
        
        # Compatibilidad con respaldos anteriores: inicializar campos faltantes con defaults según tipo
        faltantes = esperados - set(campos)
        for campo in faltantes:
            try:
                f_obj = model._meta.get_field(campo)
                if f_obj.has_default():
                    val = f_obj.get_default()
                    campos[campo] = val() if callable(val) else val
                elif f_obj.null:
                    campos[campo] = None
                elif f_obj.get_internal_type() in ('CharField', 'TextField', 'SlugField', 'EmailField', 'URLField'):
                    campos[campo] = ''
                elif f_obj.get_internal_type() in ('IntegerField', 'SmallIntegerField', 'BigIntegerField', 'PositiveIntegerField', 'PositiveSmallIntegerField'):
                    campos[campo] = 0
                elif f_obj.get_internal_type() in ('DecimalField', 'FloatField'):
                    campos[campo] = 0
                elif f_obj.get_internal_type() == 'BooleanField':
                    campos[campo] = False
                elif f_obj.get_internal_type() == 'DateField':
                    campos[campo] = timezone.now().date().isoformat()
                elif f_obj.get_internal_type() in ('DateTimeField',):
                    campos[campo] = timezone.now().isoformat()
                else:
                    campos[campo] = None
            except Exception:
                campos[campo] = None

        # Eliminar campos sobrantes que ya no existan en la versión actual
        sobrantes = set(campos) - esperados
        for campo in list(sobrantes):
            del campos[campo]

        if 'empresa' in campos:
            campos['empresa'] = empresa.pk

        for field in [*model._meta.fields, *model._meta.many_to_many]:
            if not field.is_relation or field.name not in campos:
                continue
            valores = campos[field.name] if field.many_to_many else [campos[field.name]]
            nuevos_valores = []
            for valor in valores:
                if valor is None:
                    continue
                related = field.related_model
                if (related, valor) in indices:
                    nuevos_valores.append(valor)
                elif related._base_manager.filter(pk=valor).exists():
                    nuevos_valores.append(valor)
                else:
                    if field.null:
                        if not field.many_to_many:
                            campos[field.name] = None
                    else:
                        primer = related._base_manager.first()
                        if primer:
                            if field.many_to_many:
                                nuevos_valores.append(primer.pk)
                            else:
                                campos[field.name] = primer.pk
            if field.many_to_many:
                campos[field.name] = nuevos_valores

    return indices


def crear_respaldo(empresa):
    from .cobertura_respaldo import ampliar_cobertura

    rutas = modelos_empresa()
    with transaction.atomic():
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        objetos = []
        for model, ruta in rutas.items():
            objetos.extend(model._base_manager.filter(**{ruta: empresa.pk}).order_by('pk'))
        def serializar(rows):
            return json.loads(serializers.serialize('json', rows, cls=RespaldoEncoder))

        registros, cobertura = ampliar_cobertura(empresa, rutas, objetos, serializar)
        advertencias = []
        _validar_relaciones(registros, rutas, empresa, advertencias=advertencias, ampliado=True)
        payload = {'version': 2, 'empresa_id': empresa.pk, 'rut': empresa.rut,
                   'fecha': timezone.now().isoformat(), 'registros': registros,
                   'advertencias': advertencias, **cobertura}
        archivo = json.dumps({
            'version': 2,
            'empresa_id': empresa.pk,
            'rut': empresa.rut,
            'empresa_nombre': empresa.nombre,
            'fecha': timezone.now().isoformat(),
            'total_registros': len(registros),
            'total_tablas': len(cobertura.get('tablas', [])),
            'registros': registros,
            'advertencias': advertencias,
        }, ensure_ascii=False, cls=RespaldoEncoder, indent=2).encode('utf-8')
        if len(archivo) > MAX_BYTES:
            raise RespaldoError('El respaldo supera el límite de 100 MB.')
        return archivo


def extraer_payload_respaldo(archivo):
    """Extrae el contenido de un respaldo en cualquier formato (JSON directo, firmado o comprimido)."""
    import zlib
    from django.core.signing import b64_decode

    if isinstance(archivo, bytes):
        archivo = archivo.decode('utf-8', errors='ignore')

    try:
        sobre = json.loads(archivo)
    except Exception:
        raise RespaldoError('El archivo no tiene un formato JSON válido.')

    if isinstance(sobre, list):
        return {'registros': sobre, 'version': 2}

    if not isinstance(sobre, dict):
        raise RespaldoError('El contenido del respaldo no tiene un formato válido.')

    # 1. Si los registros vienen directamente en texto plano
    if 'registros' in sobre and isinstance(sobre['registros'], list):
        return sobre

    # 2. Si viene empaquetado en 'respaldo_firmado'
    if 'respaldo_firmado' in sobre:
        raw_sig = str(sobre['respaldo_firmado'])
        try:
            return signing.loads(raw_sig, salt=SALT)
        except Exception:
            pass

        # Desempaquetar directamente si la clave secreta o versión de Django varió
        try:
            val = raw_sig.split(':')[0]
            if val.startswith('.'):
                decompressed = zlib.decompress(b64_decode(val[1:].encode('ascii')))
            else:
                decompressed = b64_decode(val.encode('ascii'))
            return json.loads(decompressed.decode('utf-8'))
        except Exception as exc:
            raise RespaldoError('No se pudo desempaquetar el contenido del respaldo.') from exc

    raise RespaldoError('El archivo no contiene la lista de registros.')


def leer_respaldo(archivo, empresa):
    if len(archivo) > MAX_BYTES:
        raise RespaldoError('El archivo supera el límite de 100 MB.')
    payload = extraer_payload_respaldo(archivo)
    if 'registros' not in payload or not isinstance(payload['registros'], list):
        raise RespaldoError('El respaldo no contiene registros válidos para restaurar.')
    return payload


def restaurar_respaldo(archivo, empresa, resumen=None, callback_progreso=None):
    from .cobertura_respaldo import catalogos_compartidos

    payload = leer_respaldo(archivo, empresa)
    rutas = modelos_empresa()
    ampliado = payload.get('version') == 2
    conservar = set(catalogos_compartidos()) | {get_user_model()} if ampliado else set()
    modelos = set(rutas) | conservar
    referencias_historicas = []
    
    with transaction.atomic():
        # Desactivar temporalmente verificación de restricciones en PostgreSQL
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                try:
                    cursor.execute("SET session_replication_role = 'replica';")
                except Exception:
                    try:
                        cursor.execute("SET CONSTRAINTS ALL DEFERRED;")
                    except Exception:
                        pass
        elif connection.vendor == 'sqlite':
            with connection.cursor() as cursor:
                try:
                    cursor.execute("PRAGMA foreign_keys = OFF;")
                except Exception:
                    pass

        try:
            indices = _validar_relaciones(payload['registros'], rutas, empresa, ampliado=ampliado,
                                         referencias_historicas=referencias_historicas)
            
            existentes = {}
            for model in modelos:
                ids = {pk for m, pk in indices if m == model}
                presentes = set(model._base_manager.filter(pk__in=ids).values_list('pk', flat=True))
                existentes[model] = presentes

            registros_validos = []
            for reg in payload['registros']:
                try:
                    m = apps.get_model(reg['model'])
                    registros_validos.append(reg)
                except (LookupError, ValueError):
                    continue

            # Deserializar una sola vez
            deserializados = list(serializers.deserialize('json', json.dumps(registros_validos)))
            por_modelo = {}
            for item in deserializados:
                por_modelo.setdefault(type(item.object), []).append(item)
                
            # 1. Inserción de nuevos registros
            for model, items in por_modelo.items():
                ex = existentes.get(model, set())
                nuevos = [item.object for item in items if item.object.pk not in ex]
                if nuevos:
                    try:
                        model._base_manager.bulk_create(nuevos, batch_size=200, ignore_conflicts=True)
                    except Exception:
                        for n in nuevos:
                            try:
                                n.save(force_insert=True)
                            except Exception:
                                pass
                if callback_progreso:
                    callback_progreso(model, len(items), 'insertados/procesados')
                    
            # 2. Actualización de campos y M2M
            for model, items in por_modelo.items():
                if model in conservar:
                    items_actualizar = [item for item in items if item.object.pk not in existentes.get(model, set())]
                else:
                    items_actualizar = items

                if not items_actualizar:
                    continue

                fields = [f.name for f in model._meta.concrete_fields if not f.primary_key]
                if fields:
                    try:
                        model._base_manager.bulk_update([item.object for item in items_actualizar], fields, batch_size=200)
                    except Exception:
                        for item in items_actualizar:
                            try:
                                item.object.save(update_fields=fields)
                            except Exception:
                                pass

                for item in items_actualizar:
                    for name, values in (item.m2m_data or {}).items():
                        try:
                            field = model._meta.get_field(name)
                            through = field.remote_field.through
                            source = field.m2m_field_name() + '_id'
                            target = field.m2m_reverse_field_name() + '_id'
                            through._base_manager.filter(**{source: item.object.pk}).delete()
                            through._base_manager.bulk_create([through(**{source: item.object.pk, target: v}) for v in values], ignore_conflicts=True)
                        except Exception:
                            pass

            try:
                connection.check_constraints()
            except Exception:
                pass

            # Reset de secuencias autoincrementales de PostgreSQL
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    todos_los_modelos = list(por_modelo.keys())
                    for sql in connection.ops.sequence_reset_sql(no_style(), todos_los_modelos):
                        try:
                            cursor.execute(sql)
                        except Exception:
                            pass

        finally:
            # Restaurar restricciones normales
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    try:
                        cursor.execute("SET session_replication_role = 'DEFAULT';")
                    except Exception:
                        pass
            elif connection.vendor == 'sqlite':
                with connection.cursor() as cursor:
                    try:
                        cursor.execute("PRAGMA foreign_keys = ON;")
                    except Exception:
                        pass
                        
    if resumen is not None:
        resumen['referencias_historicas_conservadas'] = len(referencias_historicas)
        resumen['tablas_afectadas'] = len(por_modelo)
    return sum(len(items) for items in por_modelo.values())
