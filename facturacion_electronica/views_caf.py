"""
Vistas para gestión de Archivos CAF
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from core.decorators import requiere_empresa
from facturacion_electronica.models import ArchivoCAF
from empresas.models import Sucursal


@login_required
@requiere_empresa
def listar_cafs(request):
    """Lista todos los CAFs de la empresa del usuario"""
    empresa = request.empresa
    
    # Filtros
    sucursal_id = request.GET.get('sucursal')
    tipo_documento = request.GET.get('tipo_documento')
    estado = request.GET.get('estado')
    mostrar_ocultos = request.GET.get('mostrar_ocultos') == '1'
    
    # Query base
    cafs = ArchivoCAF.objects.filter(empresa=empresa)
    
    # Aplicar filtros
    if sucursal_id:
        cafs = cafs.filter(sucursal_id=sucursal_id)
    
    if tipo_documento:
        cafs = cafs.filter(tipo_documento=tipo_documento)
    
    if estado:
        cafs = cafs.filter(estado=estado)
    
    if not mostrar_ocultos:
        cafs = cafs.filter(oculto=False)
    
    # Ordenar
    cafs = cafs.select_related('sucursal', 'usuario_carga').order_by('-fecha_carga')
    
    # Estadísticas
    stats = {
        'total': cafs.count(),
        'activos': cafs.filter(estado='activo').count(),
        'agotados': cafs.filter(estado='agotado').count(),
        'vencidos': cafs.filter(estado='vencido').count(),
        'ocultos': ArchivoCAF.objects.filter(empresa=empresa, oculto=True).count(),
    }
    
    # Sucursales para filtro
    sucursales = Sucursal.objects.filter(empresa=empresa)
    
    context = {
        'cafs': cafs,
        'stats': stats,
        'sucursales': sucursales,
        'tipo_documento_choices': ArchivoCAF.TIPO_DOCUMENTO_CHOICES,
        'estado_choices': ArchivoCAF.ESTADO_CHOICES,
        'filtros': {
            'sucursal': sucursal_id,
            'tipo_documento': tipo_documento,
            'estado': estado,
            'mostrar_ocultos': mostrar_ocultos,
        }
    }
    
    return render(request, 'facturacion_electronica/caf_list.html', context)


@login_required
@requiere_empresa
def ocultar_caf(request, caf_id):
    """Oculta un CAF específico"""
    caf = get_object_or_404(ArchivoCAF, id=caf_id, empresa=request.empresa)
    caf.oculto = True
    caf.save()
    messages.success(request, f'CAF {caf} ocultado correctamente')
    return redirect('facturacion_electronica:listar_cafs')


@login_required
@requiere_empresa
def mostrar_caf(request, caf_id):
    """Muestra un CAF oculto"""
    caf = get_object_or_404(ArchivoCAF, id=caf_id, empresa=request.empresa)
    caf.oculto = False
    caf.save()
    messages.success(request, f'CAF {caf} visible nuevamente')
    return redirect('facturacion_electronica:listar_cafs')


@login_required
@requiere_empresa
def ocultar_cafs_agotados(request):
    """Oculta todos los CAFs agotados o vencidos"""
    empresa = request.empresa
    sucursal_id = request.GET.get('sucursal')
    
    cantidad = ArchivoCAF.ocultar_cafs_agotados(empresa.id, sucursal_id)
    
    if cantidad > 0:
        messages.success(request, f'Se ocultaron {cantidad} CAFs agotados/vencidos')
    else:
        messages.info(request, 'No hay CAFs agotados/vencidos para ocultar')
    
    return redirect('facturacion_electronica:listar_cafs')


@login_required
@requiere_empresa
def mostrar_cafs_ocultos(request):
    """Muestra todos los CAFs ocultos"""
    empresa = request.empresa
    sucursal_id = request.GET.get('sucursal')
    
    cantidad = ArchivoCAF.mostrar_cafs_ocultos(empresa.id, sucursal_id)
    
    if cantidad > 0:
        messages.success(request, f'Se mostraron {cantidad} CAFs ocultos')
    else:
        messages.info(request, 'No hay CAFs ocultos para mostrar')
    
    return redirect('facturacion_electronica:listar_cafs')


@login_required
@requiere_empresa
def eliminar_cafs_sin_uso(request):
    """Elimina CAFs que nunca fueron utilizados"""
    if request.method == 'POST':
        empresa = request.empresa
        sucursal_id = request.POST.get('sucursal')
        
        cantidad, detalles = ArchivoCAF.eliminar_cafs_sin_uso(empresa.id, sucursal_id)
        
        if cantidad > 0:
            messages.success(request, f'Se eliminaron {cantidad} CAFs sin uso')
        else:
            messages.info(request, 'No hay CAFs sin uso para eliminar')
        
        return redirect('facturacion_electronica:listar_cafs')
    
    return redirect('facturacion_electronica:listar_cafs')


@login_required
@requiere_empresa
def cargar_caf(request):
    """Formulario para cargar un nuevo CAF"""
    if request.method == 'POST':
        from facturacion_electronica.forms import CargarCAFForm
        from django.core.exceptions import ValidationError
        
        form = CargarCAFForm(request.POST, request.FILES, empresa=request.empresa)
        
        if form.is_valid():
            try:
                caf = form.save(commit=False)
                caf.empresa = request.empresa
                caf.usuario_carga = request.user
                caf.save()  # Aquí se ejecutan las validaciones del modelo
                
                messages.success(request, f'✅ CAF {caf} cargado correctamente')
                return redirect('facturacion_electronica:listar_cafs')
                
            except ValidationError as e:
                # Error de validación de duplicado o rango solapado
                error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
                messages.error(request, error_msg)
            except Exception as e:
                # Otros errores
                messages.error(request, f'❌ Error al cargar el CAF: {str(e)}')
    else:
        from facturacion_electronica.forms import CargarCAFForm
        form = CargarCAFForm(empresa=request.empresa)
    
    context = {
        'form': form,
        'titulo': 'Cargar Archivo CAF',
    }
    
    return render(request, 'facturacion_electronica/caf_form.html', context)


@login_required
@requiere_empresa
def eliminar_caf(request, caf_id):
    """Elimina un CAF específico si no tiene folios utilizados"""
    if request.method == 'POST':
        caf = get_object_or_404(ArchivoCAF, id=caf_id, empresa=request.empresa)
        
        # Verificar que no tenga folios utilizados
        if caf.folios_utilizados > 0:
            messages.error(
                request, 
                f'No se puede eliminar el CAF {caf} porque tiene {caf.folios_utilizados} folios utilizados. '
                'Solo se pueden eliminar CAFs sin uso.'
            )
            return redirect('facturacion_electronica:listar_cafs')
        
        # Guardar información para el mensaje
        tipo_doc = caf.get_tipo_documento_display()
        rango = f'{caf.folio_desde}-{caf.folio_hasta}'
        
        # Eliminar el CAF
        caf.delete()
        
        messages.success(
            request, 
            f'✅ CAF eliminado correctamente: {tipo_doc} ({rango})'
        )
        
        return redirect('facturacion_electronica:listar_cafs')
    
    # Si no es POST, redirigir
    return redirect('facturacion_electronica:listar_cafs')