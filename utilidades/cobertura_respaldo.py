"""Cobertura explícita de tablas compartidas, técnicas y de relaciones.

Los registros técnicos se archivan para consulta, no se aplican a un sistema
en funcionamiento. Los catálogos y las cuentas existentes nunca se sobrescriben.
"""
from collections import Counter

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


def catalogos_compartidos():
    """Campos de identidad: permiten detectar una PK reutilizada antes de restaurar."""
    return {
        apps.get_model('empresas', 'PlanSaaS'): ('nombre',),
        ContentType: ('app_label', 'model'),
        Permission: ('content_type_id', 'codename'),
        Group: ('name',),
    }


def ampliar_cobertura(empresa, rutas, objetos, serializar):
    from .respaldo_empresa import RespaldoError

    por_modelo = {m: [] for m in rutas}
    for obj in objetos:
        por_modelo[type(obj)].append(obj)
    User = get_user_model()
    # Los administradores globales son referencias externas: no pertenecen
    # exclusivamente a una empresa y sus credenciales no se exportan.
    usuarios = list(User._base_manager.filter(perfil__empresa=empresa, is_superuser=False).order_by('pk'))
    por_modelo[User] = usuarios
    usuario_ids = {u.pk for u in usuarios}
    nombres = [u.get_username() for u in usuarios]
    for model in catalogos_compartidos():
        qs = model._base_manager.all()
        if model == Group:
            qs = qs.filter(user__pk__in=usuario_ids).distinct()
        por_modelo[model] = list(qs.order_by('pk'))

    tecnicos = {}
    tecnicos[Session] = []
    for session in Session.objects.iterator():
        data = session.get_decoded()
        empresa_id = data.get('empresa_activa_id') or data.get('empresa_activa')
        if str(empresa_id) == str(empresa.pk) and str(data.get('_auth_user_id')) in {str(pk) for pk in usuario_ids}:
            tecnicos[Session].append(session)
    for label in ('axes.AccessAttempt', 'axes.AccessFailureLog', 'axes.AccessLog'):
        model = apps.get_model(label)
        tecnicos[model] = list(model._base_manager.filter(username__in=nombres).order_by('pk'))
    expiracion = apps.get_model('axes.AccessAttemptExpiration')
    tecnicos[expiracion] = list(expiracion._base_manager.filter(
        access_attempt_id__in=[o.pk for o in tecnicos[apps.get_model('axes.AccessAttempt')]]).order_by('pk'))

    # El usuario de un log de administración no basta: también se verifica
    # el objeto, pues un operador podría haber trabajado en otra empresa.
    LogEntry = apps.get_model('admin.LogEntry')
    contenido_ids = {ct.pk: (ct.app_label, ct.model) for ct in por_modelo[ContentType]}
    ids_propios = {(m._meta.app_label, m._meta.model_name): {str(o.pk) for o in rows}
                  for m, rows in por_modelo.items() if m in rutas or m == User}
    tecnicos[LogEntry] = [o for o in LogEntry.objects.filter(user_id__in=usuario_ids).order_by('pk')
                          if o.object_id in ids_propios.get(contenido_ids.get(o.content_type_id), set())]

    relaciones = {}
    for model, rows in por_modelo.items():
        for field in model._meta.many_to_many:
            through = field.remote_field.through
            if not through._meta.auto_created:
                continue
            source = field.m2m_field_name() + '_id'
            relaciones[through] = list(through._base_manager.filter(
                **{source + '__in': [o.pk for o in rows]}).order_by('pk'))

    registros = serializar([obj for rows in por_modelo.values() for obj in rows])
    modelos = {m._meta.db_table: m for m in [*por_modelo, *tecnicos, *relaciones]}
    inventario = []
    datos_tecnicos = []
    with connection.cursor() as cursor:
        tablas = connection.introspection.table_names(cursor)
        desconocidas = set(tablas) - set(modelos) - {'django_migrations'}
        if desconocidas:
            raise RespaldoError('Falta definir el alcance de estas tablas; no se generó un respaldo incompleto: '
                                + ', '.join(sorted(desconocidas)))
        for tabla in sorted(tablas):
            model = modelos.get(tabla)
            if tabla == 'django_migrations':
                rows = list(MigrationRecorder.Migration.objects.order_by('pk').values())
                datos_tecnicos.append({'tabla': tabla, 'filas': rows})
                alcance, modo, cantidad = 'global_tecnico', 'solo_consulta', len(rows)
            elif model in tecnicos:
                rows = serializar(tecnicos[model])
                datos_tecnicos.append({'tabla': tabla, 'filas': rows})
                alcance, modo, cantidad = 'tecnico_empresa', 'solo_consulta', len(rows)
            elif model in relaciones:
                alcance, modo, cantidad = 'relacion', 'mediante_modelo_origen', len(relaciones[model])
            else:
                alcance = 'empresa' if model in rutas else ('cuenta_empresa' if model == User else 'catalogo_compartido')
                modo = 'actualizar_o_crear' if model in rutas else 'crear_solo_faltantes'
                cantidad = len(por_modelo[model])
            columnas = [{'nombre': c.name, 'tipo': str(c.type_code), 'admite_nulo': c.null_ok}
                        for c in connection.introspection.get_table_description(cursor, tabla)]
            inventario.append({'tabla': tabla, 'modelo': model._meta.label_lower if model else None,
                               'alcance': alcance, 'restauracion': modo, 'cantidad': cantidad,
                               'columnas': columnas})
    return registros, {
        'tablas': inventario,
        'datos_tecnicos': datos_tecnicos,
        'relaciones': [{'tabla': m._meta.db_table, 'filas': serializar(rows)} for m, rows in relaciones.items()],
    }


def validar_cuentas(indices, empresa):
    """La identidad y la pertenencia del archivo se validan también sin filas actuales."""
    from .respaldo_empresa import RespaldoError

    User = get_user_model()
    Perfil = apps.get_model('usuarios', 'PerfilUsuario')
    propietarios = {r['fields']['usuario']: r['fields']['empresa']
                    for (m, _), r in indices.items() if m == Perfil}
    for (model, pk), registro in indices.items():
        if model == User:
            if propietarios.get(pk) != empresa.pk or registro['fields']['is_superuser']:
                raise RespaldoError('El respaldo contiene una cuenta ajena a la empresa o un administrador global.')
            actual = User._base_manager.filter(pk=pk).first()
            if actual and (actual.is_superuser or actual.username != registro['fields']['username']
                           or not Perfil.objects.filter(usuario_id=pk, empresa=empresa).exists()):
                raise RespaldoError('Una cuenta del respaldo pertenece actualmente a otra empresa o cambió de identidad.')


def validar_catalogos(indices):
    from .respaldo_empresa import RespaldoError

    for model, identidad in catalogos_compartidos().items():
        filas = {pk: row for (m, pk), row in indices.items() if m == model}
        for actual in model._base_manager.filter(pk__in=filas):
            fields = filas[actual.pk]['fields']
            for atributo in identidad:
                campo = model._meta.get_field(atributo).name
                if getattr(actual, atributo) != fields[campo]:
                    raise RespaldoError('Un catálogo compartido cambió de identidad. No se aplicaron cambios: '
                                        + model._meta.label)


def validar_inventario(payload, registros):
    """Evita aceptar un v2 con cobertura parcial o datos ajenos como tablas nuevas."""
    from .respaldo_empresa import RespaldoError

    tablas = payload.get('tablas', [])
    nombres = [t['tabla'] for t in tablas]
    actuales = set(connection.introspection.table_names())
    if len(set(nombres)) != len(nombres) or set(nombres) != actuales:
        raise RespaldoError('Las tablas del respaldo no coinciden con esta instalación. Genere un respaldo nuevo.')
    conteos = Counter(r['model'] for r in registros)
    for tabla in tablas:
        if tabla['restauracion'] in ('actualizar_o_crear', 'crear_solo_faltantes'):
            if conteos[tabla['modelo']] != tabla['cantidad']:
                raise RespaldoError('El inventario del respaldo no coincide con sus registros.')
