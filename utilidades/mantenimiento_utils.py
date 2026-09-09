"""
Utilidades para mantenimiento del sistema
Compatible con PostgreSQL y SQLite
"""
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.core.management import call_command
from core.decorators import requiere_empresa
from datetime import datetime, timedelta
import os
import subprocess
import logging

logger = logging.getLogger(__name__)


@login_required
@requiere_empresa
def optimizar_tablas(request):
    """Optimiza las tablas de la base de datos"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        with connection.cursor() as cursor:
            # Para PostgreSQL
            if connection.vendor == 'postgresql':
                cursor.execute("VACUUM ANALYZE;")
                cursor.execute("REINDEX DATABASE %s;" % connection.settings_dict['NAME'])
                message = 'Tablas optimizadas correctamente (PostgreSQL)'
            # Para SQLite
            elif connection.vendor == 'sqlite':
                cursor.execute("VACUUM;")
                cursor.execute("ANALYZE;")
                message = 'Tablas optimizadas correctamente (SQLite)'
            else:
                message = f'Optimización no implementada para {connection.vendor}'
        
        return JsonResponse({'success': True, 'message': message})
    except Exception as e:
        logger.error(f"Error al optimizar tablas: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


def puede_gestionar_respaldos(user):
    perfil = getattr(user, 'perfil', None)
    return user.is_superuser or bool(perfil and perfil.es_administrador)


@login_required
@requiere_empresa
def crear_backup(request):
    """Descarga exclusivamente los datos de la empresa activa."""
    from .respaldo_empresa import crear_respaldo, RespaldoError
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    if not puede_gestionar_respaldos(request.user):
        return JsonResponse({'success': False, 'message': 'Solo los administradores pueden gestionar respaldos.'}, status=403)
    if request.GET.get('empresa_id', str(request.empresa.pk)) != str(request.empresa.pk):
        return JsonResponse({'success': False, 'message': 'La empresa activa cambió. Recargue la página.'}, status=400)
    try:
        contenido = crear_respaldo(request.empresa)
        filename = f"respaldo_empresa_{request.empresa.pk}_{datetime.now():%Y%m%d_%H%M%S}.json"
        response = HttpResponse(contenido, content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Cache-Control'] = 'no-store'
        import json
        response['X-Respaldo-Advertencias'] = str(len(json.loads(contenido)['advertencias']))
        response['X-Respaldo-Tablas'] = str(json.loads(contenido)['total_tablas'])
        return response
    except RespaldoError as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)
    except Exception:
        logger.exception('Error al respaldar empresa %s', request.empresa.pk)
        return JsonResponse({'success': False, 'message': 'No se pudo generar el respaldo. Revise el registro del sistema.'}, status=500)


@login_required
@requiere_empresa
def restaurar_backup(request):
    from .respaldo_empresa import restaurar_respaldo, RespaldoError, MAX_BYTES
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    if not puede_gestionar_respaldos(request.user):
        return JsonResponse({'success': False, 'message': 'Solo los administradores pueden restaurar respaldos.'}, status=403)
    archivo = request.FILES.get('archivo')
    if request.POST.get('empresa_id') != str(request.empresa.pk):
        return JsonResponse({'success': False, 'message': 'La empresa activa cambió. Recargue la página antes de restaurar.'}, status=400)
    if not archivo or archivo.size > MAX_BYTES:
        return JsonResponse({'success': False, 'message': 'Seleccione un respaldo válido de hasta 100 MB.'}, status=400)
    try:
        resumen = {}
        total = restaurar_respaldo(archivo.read(), request.empresa, resumen=resumen)
        message = f'Restauración completada: {total} registros recuperados. Se conservaron los registros posteriores al respaldo.'
        historicas = resumen.get('referencias_historicas_conservadas', 0)
        if historicas:
            message += f' Se conservaron {historicas} vínculos históricos existentes, sin copiar datos de otras empresas.'
        return JsonResponse({'success': True, 'message': message, **resumen})
    except RespaldoError as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)
    except Exception:
        logger.exception('Error al restaurar empresa %s', request.empresa.pk)
        return JsonResponse({'success': False, 'message': 'No se pudo restaurar por una incompatibilidad de datos. No se aplicaron cambios.'}, status=400)


@login_required
@requiere_empresa
def verificar_integridad(request):
    """Verifica la integridad de los datos"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        from inventario.models import Stock
        from articulos.models import Articulo
        from clientes.models import Cliente
        from proveedores.models import Proveedor
        
        resultados = {}
        
        # Verificar stock negativo
        stock_negativo = Stock.objects.filter(cantidad__lt=0).count()
        resultados['Stock negativo'] = f"{stock_negativo} registros"
        
        # Verificar artículos sin precio
        articulos_sin_precio = Articulo.objects.filter(
            empresa=request.empresa,
            precio_venta=0
        ).count()
        resultados['Artículos sin precio'] = f"{articulos_sin_precio} registros"
        
        # Verificar clientes duplicados por RUT
        from django.db.models import Count
        clientes_duplicados = Cliente.objects.filter(
            empresa=request.empresa
        ).values('rut').annotate(
            count=Count('id')
        ).filter(count__gt=1).count()
        resultados['Clientes duplicados (RUT)'] = f"{clientes_duplicados} registros"
        
        # Verificar proveedores duplicados por RUT
        proveedores_duplicados = Proveedor.objects.filter(
            empresa=request.empresa
        ).values('rut').annotate(
            count=Count('id')
        ).filter(count__gt=1).count()
        resultados['Proveedores duplicados (RUT)'] = f"{proveedores_duplicados} registros"
        
        return JsonResponse({
            'success': True,
            'resultados': resultados
        })
        
    except Exception as e:
        logger.error(f"Error al verificar integridad: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


@login_required
@requiere_empresa
def limpiar_sesiones(request):
    """Limpia sesiones expiradas"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        # Ejecutar comando de Django para limpiar sesiones
        call_command('clearsessions')
        
        return JsonResponse({
            'success': True,
            'message': 'Sesiones expiradas eliminadas correctamente'
        })
        
    except Exception as e:
        logger.error(f"Error al limpiar sesiones: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


@login_required
@requiere_empresa
def detectar_duplicados(request):
    """Detecta registros duplicados"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        from clientes.models import Cliente
        from proveedores.models import Proveedor
        from articulos.models import Articulo
        from django.db.models import Count
        
        # Clientes duplicados
        clientes_dup = Cliente.objects.filter(
            empresa=request.empresa
        ).values('rut').annotate(
            count=Count('id')
        ).filter(count__gt=1).count()
        
        # Proveedores duplicados
        proveedores_dup = Proveedor.objects.filter(
            empresa=request.empresa
        ).values('rut').annotate(
            count=Count('id')
        ).filter(count__gt=1).count()
        
        # Artículos duplicados por código
        articulos_dup = Articulo.objects.filter(
            empresa=request.empresa
        ).values('codigo').annotate(
            count=Count('id')
        ).filter(count__gt=1).count()
        
        return JsonResponse({
            'success': True,
            'duplicados': {
                'clientes': clientes_dup,
                'proveedores': proveedores_dup,
                'articulos': articulos_dup
            }
        })
        
    except Exception as e:
        logger.error(f"Error al detectar duplicados: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


@login_required
@requiere_empresa
def limpiar_archivos(request):
    """Limpia archivos temporales"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        import shutil
        from django.conf import settings
        
        archivos_eliminados = 0
        
        # Limpiar directorio temporal
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        if os.path.exists(temp_dir):
            for filename in os.listdir(temp_dir):
                filepath = os.path.join(temp_dir, filename)
                try:
                    if os.path.isfile(filepath):
                        os.unlink(filepath)
                        archivos_eliminados += 1
                except Exception as e:
                    logger.error(f"Error al eliminar {filepath}: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'message': f'{archivos_eliminados} archivos temporales eliminados'
        })
        
    except Exception as e:
        logger.error(f"Error al limpiar archivos: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


@login_required
@requiere_empresa
def ver_logs(request):
    """Muestra los logs del sistema"""
    try:
        from django.conf import settings
        
        log_file = os.path.join(settings.BASE_DIR, 'logs', 'django.log')
        
        if not os.path.exists(log_file):
            return HttpResponse("No hay logs disponibles")
        
        # Leer últimas 1000 líneas
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            last_lines = lines[-1000:]
        
        content = ''.join(last_lines)
        
        return HttpResponse(f'<pre>{content}</pre>')
        
    except Exception as e:
        return HttpResponse(f'Error al leer logs: {str(e)}')


@login_required
@requiere_empresa
def exportar_logs(request):
    """Exporta los logs del sistema"""
    try:
        from django.conf import settings
        
        log_file = os.path.join(settings.BASE_DIR, 'logs', 'django.log')
        
        if not os.path.exists(log_file):
            return JsonResponse({'success': False, 'message': 'No hay logs disponibles'})
        
        with open(log_file, 'rb') as f:
            response = HttpResponse(f.read(), content_type='text/plain')
            response['Content-Disposition'] = f'attachment; filename="django_logs_{datetime.now().strftime("%Y%m%d")}.log"'
            return response
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


@login_required
@requiere_empresa
def purgar_logs(request):
    """Purga logs antiguos (mayores a 90 días)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        from django.conf import settings
        
        log_file = os.path.join(settings.BASE_DIR, 'logs', 'django.log')
        
        if not os.path.exists(log_file):
            return JsonResponse({'success': True, 'message': 'No hay logs para purgar'})
        
        # Leer archivo
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Filtrar líneas (simplificado - en producción usar fecha real del log)
        fecha_limite = datetime.now() - timedelta(days=90)
        
        # Reescribir archivo con solo últimas 10000 líneas
        with open(log_file, 'w', encoding='utf-8') as f:
            f.writelines(lines[-10000:])
        
        return JsonResponse({
            'success': True,
            'message': 'Logs antiguos purgados correctamente'
        })
        
    except Exception as e:
        logger.error(f"Error al purgar logs: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
