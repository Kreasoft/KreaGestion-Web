"""Respaldos de datos por empresa, firmados y restaurados sin ejecutar SQL externo.

No incluye archivos de MEDIA_ROOT, cuentas de acceso ni catálogos globales.
La recuperación conserva los registros creados después del respaldo.
"""
import json
from datetime import datetime

from django.apps import apps
from django.conf import settings
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
        if isinstance(value, datetime):
            return value.isoformat()
        return super().default(value)


def modelos_empresa():
    """Prioriza empresa directa; los detalles heredan su primer padre obligatorio.

Nunca atraviesa usuarios ni relaciones inversas hacia catálogos compartidos.
Todas las demás relaciones se validan antes de exportar o escribir.
"""
    empresa = apps.get_model('empresas', 'Empresa')
    locales = {name.split('.')[0] for name in settings.LOCAL_APPS} - {'usuarios'}
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


def _validar_relaciones(registros, rutas, empresa, advertencias=None):
    indices = {}
    for registro in registros:
        model = apps.get_model(registro['model'])
        if model not in rutas:
            raise RespaldoError('El respaldo contiene una tabla no permitida.')
        key = (model, registro['pk'])
        if key in indices:
            raise RespaldoError('El respaldo contiene registros duplicados.')
        indices[key] = registro
    raiz = apps.get_model('empresas', 'Empresa')
    if {pk for model, pk in indices if model == raiz} != {empresa.pk}:
        raise RespaldoError('El respaldo no corresponde a la empresa activa.')
    compartidas = {}
    for (model, pk), registro in indices.items():
        campos = registro['fields']
        esperados = {f.name for f in model._meta.fields if not f.primary_key}
        esperados.update(f.name for f in model._meta.many_to_many if f.remote_field.through._meta.auto_created)
        if set(campos) != esperados:
            raise RespaldoError('La estructura del respaldo no coincide con esta versión del sistema.')
        if 'empresa' in campos and campos['empresa'] != empresa.pk:
            raise RespaldoError('Se detectaron datos de otra empresa.')
        for field in [*model._meta.fields, *model._meta.many_to_many]:
            if not field.is_relation or field.name not in campos:
                continue
            valores = campos[field.name] if field.many_to_many else [campos[field.name]]
            for valor in valores:
                if valor is None:
                    continue
                related = field.related_model
                if related in rutas:
                    if (related, valor) not in indices:
                        mensaje = f'Relación incompleta o ajena a la empresa: {model._meta.label}.{field.name}, registro {pk}.'
                        if advertencias is None:
                            raise RespaldoError(mensaje + ' Corrija esta relación antes de generar un nuevo respaldo para restaurar.')
                        advertencias.append(mensaje)
                else:
                    compartidas.setdefault(related, set()).add(valor)
    for model, ids in compartidas.items():
        if set(model._base_manager.filter(pk__in=ids).values_list('pk', flat=True)) != ids:
            raise RespaldoError('Faltan usuarios o catálogos compartidos requeridos por el respaldo.')
    return indices


def crear_respaldo(empresa):
    rutas = modelos_empresa()
    with transaction.atomic():
        # Una sola instantánea evita mezclar cabeceras y detalles de distintas transacciones.
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        objetos = []
        for model, ruta in rutas.items():
            objetos.extend(model._base_manager.filter(**{ruta: empresa.pk}).order_by('pk'))
        registros = json.loads(serializers.serialize('json', objetos, cls=RespaldoEncoder))
        advertencias = []
        _validar_relaciones(registros, rutas, empresa, advertencias=advertencias)
        payload = {'version': 1, 'empresa_id': empresa.pk, 'rut': empresa.rut,
                   'fecha': timezone.now().isoformat(), 'registros': registros,
                   'advertencias': advertencias}
        archivo = json.dumps({'advertencias': advertencias, 'respaldo_firmado': signing.dumps(payload, salt=SALT)}, ensure_ascii=False).encode('utf-8')
        if len(archivo) > MAX_BYTES:
            raise RespaldoError('El respaldo supera el límite de 100 MB.')
        return archivo


def leer_respaldo(archivo, empresa):
    if len(archivo) > MAX_BYTES:
        raise RespaldoError('El archivo supera el límite de 100 MB.')
    try:
        sobre = json.loads(archivo)
        payload = signing.loads(sobre['respaldo_firmado'], salt=SALT)
    except (ValueError, KeyError, TypeError, signing.BadSignature) as exc:
        raise RespaldoError('Archivo inválido o alterado. Use un respaldo por empresa generado por esta instalación.') from exc
    if payload.get('version') != 1:
        raise RespaldoError('Versión de respaldo no compatible.')
    if payload.get('empresa_id') != empresa.pk or payload.get('rut') != empresa.rut:
        raise RespaldoError('El respaldo pertenece a otra empresa. Seleccione la empresa correspondiente.')
    return payload


def restaurar_respaldo(archivo, empresa):
    payload = leer_respaldo(archivo, empresa)
    rutas = modelos_empresa()
    with transaction.atomic():
        # Impide cambios concurrentes de propietario entre validación y escritura.
        if connection.vendor == 'postgresql':
            tablas = {m._meta.db_table for m in rutas}
            tablas.update(f.remote_field.through._meta.db_table for m in rutas for f in m._meta.many_to_many)
            with connection.cursor() as cursor:
                cursor.execute('LOCK TABLE ' + ', '.join(connection.ops.quote_name(t) for t in sorted(tablas)) + ' IN SHARE ROW EXCLUSIVE MODE')
        indices = _validar_relaciones(payload['registros'], rutas, empresa)
        existentes = {}
        for model, ruta in rutas.items():
            ids = {pk for m, pk in indices if m == model}
            presentes = set(model._base_manager.filter(pk__in=ids).values_list('pk', flat=True))
            propios = set(model._base_manager.filter(pk__in=ids, **{ruta: empresa.pk}).values_list('pk', flat=True))
            if presentes != propios:
                raise RespaldoError('Un identificador del respaldo pertenece actualmente a otra empresa. No se aplicaron cambios.')
            existentes[model] = presentes
        deserializados = list(serializers.deserialize('json', json.dumps(payload['registros'])))
        por_modelo = {}
        for item in deserializados:
            por_modelo.setdefault(type(item.object), []).append(item)
        # bulk_* evita ejecutar señales de ventas, movimientos o emisión de documentos.
        for model, items in por_modelo.items():
            nuevos = [item.object for item in items if item.object.pk not in existentes[model]]
            model._base_manager.bulk_create(nuevos, batch_size=200)
        # Deserializar de nuevo conserva auto_now/auto_now_add del archivo tras la inserción.
        por_modelo = {}
        for item in serializers.deserialize('json', json.dumps(payload['registros'])):
            por_modelo.setdefault(type(item.object), []).append(item)
        for model, items in por_modelo.items():
            fields = [f.name for f in model._meta.concrete_fields if not f.primary_key]
            model._base_manager.bulk_update([item.object for item in items], fields, batch_size=200)
            for item in items:
                for name, values in (item.m2m_data or {}).items():
                    field = model._meta.get_field(name)
                    through = field.remote_field.through
                    source = field.m2m_field_name() + '_id'
                    target = field.m2m_reverse_field_name() + '_id'
                    through._base_manager.filter(**{source: item.object.pk}).delete()
                    through._base_manager.bulk_create([through(**{source: item.object.pk, target: v}) for v in values])
        connection.check_constraints()
        with connection.cursor() as cursor:
            for sql in connection.ops.sequence_reset_sql(no_style(), list(por_modelo)):
                cursor.execute(sql)
    return len(indices)
