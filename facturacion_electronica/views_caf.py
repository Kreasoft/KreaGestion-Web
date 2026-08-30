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


def _build_ambiente_sections(cafs_queryset, ambiente_activo=None, historico=False):
    sections = []
    for key, label in ArchivoCAF.AMBIENTE_CHOICES:
        if ambiente_activo and key != ambiente_activo:
            continue
        subset = cafs_queryset.filter(ambiente=key).order_by('tipo_documento', '-fecha_carga')
        sections.append({
            'key': key,
            'label': label,
            'items': subset,
            'count': subset.count(),
            'historico': historico,
        })
    return sections


@login_required
@requiere_empresa
def listar_cafs(request):
    """Lista todos los CAFs de la empresa del usuario"""
    empresa = request.empresa
    ArchivoCAF.sincronizar_cafs_vencidos(empresa.id)
    ambiente_actual = getattr(empresa, 'ambiente_sii', 'certificacion')
    
    # Filtros
    sucursal_id = request.GET.get('sucursal')
    tipo_documento = request.GET.get('tipo_documento')
    estado = request.GET.get('estado')
    mostrar_ocultos = request.GET.get('mostrar_ocultos') == '1'
    
    # Query base (sin filtrar ocultos inicialmente para clasificarlos)
    cafs_base = ArchivoCAF.objects.filter(empresa=empresa)
    
    # Aplicar filtros
    if sucursal_id:
        cafs_base = cafs_base.filter(sucursal_id=sucursal_id)
    
    if tipo_documento:
        cafs_base = cafs_base.filter(tipo_documento=tipo_documento)
    
    if estado:
        cafs_base = cafs_base.filter(estado=estado)
    
    # Ordenar y seleccionar relacionados
    cafs_base = cafs_base.select_related('sucursal', 'usuario_carga').order_by('-fecha_carga')
    
    # Clasificar para las pestañas
    cafs_vigentes = cafs_base.filter(estado='activo', oculto=False)
    cafs_historico = cafs_base.filter(Q(estado__in=['agotado', 'vencido', 'anulado']) | Q(oculto=True))
    vigentes_por_ambiente = _build_ambiente_sections(cafs_vigentes, ambiente_activo=ambiente_actual)
    historico_por_ambiente = _build_ambiente_sections(cafs_historico, ambiente_activo=ambiente_actual, historico=True)
    
    # Estadísticas
    stats = {
        'total': cafs_base.count(),
        'activos': cafs_base.filter(estado='activo').count(),
        'agotados': cafs_base.filter(estado='agotado').count(),
        'vencidos': cafs_base.filter(estado='vencido').count(),
        'ocultos': ArchivoCAF.objects.filter(empresa=empresa, oculto=True).count(),
        'produccion': {
            'activos': cafs_base.filter(ambiente='produccion', estado='activo', oculto=False).count(),
            'historico': cafs_base.filter(ambiente='produccion').filter(Q(estado__in=['agotado', 'vencido', 'anulado']) | Q(oculto=True)).count(),
        },
        'certificacion': {
            'activos': cafs_base.filter(ambiente='certificacion', estado='activo', oculto=False).count(),
            'historico': cafs_base.filter(ambiente='certificacion').filter(Q(estado__in=['agotado', 'vencido', 'anulado']) | Q(oculto=True)).count(),
        },
    }
    
    # Sucursales para filtro
    sucursales = Sucursal.objects.filter(empresa=empresa)
    
    context = {
        'cafs_vigentes': cafs_vigentes,
        'cafs_historico': cafs_historico,
        'vigentes_por_ambiente': vigentes_por_ambiente,
        'historico_por_ambiente': historico_por_ambiente,
        'stats': stats,
        'ambiente_actual_empresa': ambiente_actual,
        'sucursales': sucursales,
        'tipo_documento_choices': ArchivoCAF.TIPO_DOCUMENTO_CHOICES,
        'ambiente_choices': ArchivoCAF.AMBIENTE_CHOICES,
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
    if request.method != 'POST':
        messages.warning(request, 'La acción de mover a historial debe enviarse desde el botón de la pantalla.')
        return redirect('facturacion_electronica:listar_cafs')
    caf = get_object_or_404(ArchivoCAF, id=caf_id, empresa=request.empresa)
    caf.oculto = True
    caf.save()
    messages.success(request, f'CAF {caf} movido correctamente a historial')
    return redirect('facturacion_electronica:listar_cafs')


@login_required
@requiere_empresa
def mostrar_caf(request, caf_id):
    """Muestra un CAF oculto"""
    if request.method != 'POST':
        messages.warning(request, 'La acción de mover a vigentes debe enviarse desde el botón de la pantalla.')
        return redirect('facturacion_electronica:listar_cafs')
    caf = get_object_or_404(ArchivoCAF, id=caf_id, empresa=request.empresa)
    if caf.estado != 'activo':
        messages.warning(request, f'El CAF {caf} no puede volver a vigentes porque está {caf.get_estado_display().lower()}')
        return redirect('facturacion_electronica:listar_cafs')
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
        'ambiente_actual_empresa': getattr(request.empresa, 'ambiente_sii', 'certificacion'),
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


@login_required
@requiere_empresa
def ajustar_folio_caf(request, caf_id):
    """Ajusta manualmente el folio actual de un CAF con validaciones"""
    from django.http import JsonResponse
    from django.db import transaction
    from facturacion_electronica.models import DocumentoTributarioElectronico
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    caf = get_object_or_404(ArchivoCAF, id=caf_id, empresa=request.empresa)
    
    try:
        nuevo_folio = int(request.POST.get('nuevo_folio'))
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'El folio debe ser un número válido'})
    
    # VALIDACIÓN 1: Rango mínimo
    if nuevo_folio < (caf.folio_desde - 1):
        return JsonResponse({
            'success': False, 
            'error': f'El folio {nuevo_folio} es menor que el mínimo permitido ({caf.folio_desde - 1})'
        })
    
    # VALIDACIÓN 2: Rango máximo
    if nuevo_folio > caf.folio_hasta:
        return JsonResponse({
            'success': False, 
            'error': f'El folio {nuevo_folio} excede el máximo autorizado ({caf.folio_hasta})'
        })
    
    # VALIDACIÓN 3: Verificar que no haya DTEs con folios posteriores al nuevo folio
    dtes_posteriores = DocumentoTributarioElectronico.objects.filter(
        empresa=request.empresa,
        caf_utilizado=caf,
        folio__gt=nuevo_folio
    ).count()
    
    if dtes_posteriores > 0:
        return JsonResponse({
            'success': False,
            'error': f'No se puede ajustar a folio {nuevo_folio} porque existen {dtes_posteriores} documentos emitidos con folios superiores'
        })
    
    # Calcular nuevos valores
    if nuevo_folio < caf.folio_desde:
        nuevos_folios_utilizados = 0
    else:
        nuevos_folios_utilizados = nuevo_folio - caf.folio_desde + 1
    
    nuevo_estado = 'activo'
    if nuevos_folios_utilizados >= caf.cantidad_folios:
        nuevo_estado = 'agotado'
    
    # Aplicar cambios en transacción atómica
    with transaction.atomic():
        caf_bloqueado = ArchivoCAF.objects.select_for_update().get(pk=caf.pk)
        
        folio_anterior = caf_bloqueado.folio_actual
        folios_utilizados_anterior = caf_bloqueado.folios_utilizados
        
        caf_bloqueado.folio_actual = nuevo_folio
        caf_bloqueado.folios_utilizados = nuevos_folios_utilizados
        caf_bloqueado.estado = nuevo_estado
        caf_bloqueado.save()
        
        print(f"[AJUSTE MANUAL] CAF ID {caf.id}: folio_actual {folio_anterior}→{nuevo_folio}, "
              f"folios_utilizados {folios_utilizados_anterior}→{nuevos_folios_utilizados}, "
              f"estado→{nuevo_estado}")
    
    return JsonResponse({
        'success': True,
        'message': f'''
            <p class="mb-2"><strong>Folio ajustado correctamente:</strong></p>
            <ul class="text-start mb-0">
                <li>Folio actual: {folio_anterior} → {nuevo_folio}</li>
                <li>Folios utilizados: {folios_utilizados_anterior} → {nuevos_folios_utilizados}</li>
                <li>Próximo folio: {nuevo_folio + 1}</li>
            </ul>
        '''
    })
