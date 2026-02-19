from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from core.decorators import requiere_empresa
from .models import ArchivoCAF, DocumentoTributarioElectronico, EnvioDTE, ConfiguracionAlertaFolios
from .forms import CargarCAFForm as ArchivoCAFForm  # Alias para compatibilidad
import xml.etree.ElementTree as ET
from datetime import datetime


@login_required
@requiere_empresa
def caf_list(request):
    """Lista de archivos CAF de la empresa"""
    archivos_caf = ArchivoCAF.objects.filter(
        empresa=request.empresa
    ).select_related('sucursal').order_by('-fecha_carga')
    
    # Estadísticas
    total_caf = archivos_caf.count()
    activos = archivos_caf.filter(estado='activo').count()
    agotados = archivos_caf.filter(estado='agotado').count()
    vencidos = archivos_caf.filter(estado='vencido').count()
    ocultos = archivos_caf.filter(oculto=True).count()
    
    # Folios por tipo de documento
    folios_por_tipo = {}
    for tipo_doc, nombre in ArchivoCAF.TIPO_DOCUMENTO_CHOICES:
        cafs_tipo = archivos_caf.filter(tipo_documento=tipo_doc, estado='activo')
        folios_disponibles = sum([caf.folios_disponibles() for caf in cafs_tipo])
        folios_por_tipo[nombre] = {
            'codigo': tipo_doc,
            'disponibles': folios_disponibles,
            'archivos': cafs_tipo.count()
        }
    
    # Obtener configuraciones de alertas por tipo de documento
    alertas_config = {}
    for config in ConfiguracionAlertaFolios.objects.filter(empresa=request.empresa, activo=True):
        alertas_config[config.tipo_documento] = config.folios_minimos
    
    # Sucursales para filtro
    from empresas.models import Sucursal
    sucursales = Sucursal.objects.filter(empresa=request.empresa)
    
    context = {
        'archivos_caf': archivos_caf,
        'cafs': archivos_caf,  # Alias para compatibilidad con nuevo template
        'total_caf': total_caf,
        'activos': activos,
        'agotados': agotados,
        'folios_por_tipo': folios_por_tipo,
        'alertas_config': alertas_config,
        # Variables para nuevo template
        'sucursales': sucursales,
        'tipo_documento_choices': ArchivoCAF.TIPO_DOCUMENTO_CHOICES,
        'estado_choices': ArchivoCAF.ESTADO_CHOICES,
        'stats': {
            'total': total_caf,
            'activos': activos,
            'agotados': agotados,
            'vencidos': vencidos,
            'ocultos': ocultos,
        },
        'filtros': {
            'sucursal': None,
            'tipo_documento': None,
            'estado': None,
            'mostrar_ocultos': False,
        }
    }
    
    return render(request, 'facturacion_electronica/caf_list.html', context)


@login_required
@requiere_empresa
def caf_create(request):
    """Cargar nuevo archivo CAF"""
    
    if not request.empresa.facturacion_electronica:
        messages.error(request, 'La facturación electrónica no está activada para esta empresa.')
        return redirect('empresas:editar_empresa_activa')
    
    if request.method == 'POST':
        from django.core.exceptions import ValidationError
        form = ArchivoCAFForm(request.POST, request.FILES, empresa=request.empresa)
        
        if form.is_valid():
            try:
                # El formulario ya parsea automáticamente el XML
                caf = form.save(commit=False)
                caf.empresa = request.empresa
                caf.usuario_carga = request.user
                caf.save()  # Aquí se ejecutan las validaciones del modelo
                
                messages.success(
                    request,
                    f'✅ CAF cargado exitosamente. '
                    f'Folios: {caf.folio_desde} - {caf.folio_hasta} ({caf.cantidad_folios} folios disponibles).'
                )
                return redirect('facturacion_electronica:caf_list')
                
            except ValidationError as e:
                # Error de validación de duplicado o rango solapado
                messages.error(request, str(e.message))
            except Exception as e:
                print(f"[ERROR] Error al procesar CAF: {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'❌ Error al procesar el CAF: {str(e)}')
        else:
            print(f"[ERROR] Errores en formulario: {form.errors}")
    else:
        form = ArchivoCAFForm(empresa=request.empresa)
    
    context = {
        'form': form,
        'titulo': 'Cargar Archivo CAF'
    }
    
    return render(request, 'facturacion_electronica/caf_form.html', context)


@login_required
@requiere_empresa
def caf_detail(request, pk):
    """Detalle de un archivo CAF"""
    caf = get_object_or_404(ArchivoCAF, pk=pk, empresa=request.empresa)
    
    context = {
        'caf': caf,
    }
    
    return render(request, 'facturacion_electronica/caf_detail.html', context)


@login_required
@requiere_empresa
def caf_ajustar_folio(request, pk):
    """Ajustar el folio actual de un CAF"""
    caf = get_object_or_404(ArchivoCAF, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        nuevo_folio = int(request.POST.get('nuevo_folio'))
        
        # Validaciones
        if nuevo_folio < caf.folio_desde:
            messages.error(request, f'El folio no puede ser menor al inicial ({caf.folio_desde})')
        elif nuevo_folio > caf.folio_hasta + 1:
            messages.error(request, f'El folio no puede ser mayor al final ({caf.folio_hasta})')
        else:
            # Calcular folios utilizados
            folio_actual_anterior = caf.folio_actual
            folios_usados_anterior = caf.folios_utilizados
            
            caf.folio_actual = nuevo_folio - 1
            caf.folios_utilizados = (nuevo_folio - 1) - caf.folio_desde + 1
            
            # Verificar si se agotó
            if caf.folios_disponibles() == 0:
                caf.estado = 'agotado'
            
            caf.save()
            
            messages.success(
                request, 
                f'Folio actual actualizado correctamente. '
                f'Próximo folio a asignar: {nuevo_folio}. '
                f'Folios disponibles: {caf.folios_disponibles()}'
            )
            
            print(f"[INFO] Ajuste de folio en CAF {caf.id}:")
            print(f"   Folio actual: {folio_actual_anterior} → {caf.folio_actual}")
            print(f"   Folios usados: {folios_usados_anterior} → {caf.folios_utilizados}")
            print(f"   Folios disponibles: {caf.folios_disponibles()}")
        
        return redirect('facturacion_electronica:caf_detail', pk=pk)
    
    return redirect('facturacion_electronica:caf_detail', pk=pk)


@login_required
@requiere_empresa
def caf_anular(request, pk):
    """Anular un archivo CAF"""
    caf = get_object_or_404(ArchivoCAF, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        if caf.folios_utilizados > 0:
            messages.error(
                request, 
                f'No se puede anular un CAF que ya tiene {caf.folios_utilizados} folios utilizados'
            )
        else:
            caf.estado = 'anulado'
            caf.save()
            messages.success(request, 'CAF anulado exitosamente')
        
        return redirect('facturacion_electronica:caf_list')
    
    context = {
        'caf': caf,
    }
    
    return render(request, 'facturacion_electronica/caf_confirm_anular.html', context)


@login_required
@requiere_empresa
def dte_list(request):
    """
    Libro de Ventas Electrónico (Documentos Emitidos / Enviados)
    Se muestran solo los documentos emitidos por la empresa (Ventas).
    """
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    
    # Establecer fechas por defecto: primer día del año actual hasta hoy
    hoy = timezone.now().date()
    primer_dia_ano = hoy.replace(month=1, day=1)
    
    # Filtrar solo documentos emitidos por la empresa (Enviados)
    # y vinculados a la empresa actual
    dtes = DocumentoTributarioElectronico.objects.filter(
        empresa=request.empresa
    ).order_by('-fecha_emision', '-folio')

    # Aplicar filtros de búsqueda
    fecha_desde = request.GET.get('fecha_desde', primer_dia_ano.strftime('%Y-%m-%d'))
    fecha_hasta = request.GET.get('fecha_hasta', hoy.strftime('%Y-%m-%d'))
    tipo_dte = request.GET.get('tipo_dte')
    cliente_id = request.GET.get('cliente')
    estado = request.GET.get('estado')
    search = request.GET.get('search')

    if fecha_desde:
        dtes = dtes.filter(fecha_emision__gte=fecha_desde)
    if fecha_hasta:
        dtes = dtes.filter(fecha_emision__lte=fecha_hasta)
    if tipo_dte:
        dtes = dtes.filter(tipo_dte=tipo_dte)
    if cliente_id:
        dtes = dtes.filter(rut_receptor=cliente_id) # Ajustar si cliente es ID o RUT
    if estado:
        dtes = dtes.filter(estado_sii=estado)
    if search:
        dtes = dtes.filter(
            Q(folio__icontains=search) |
            Q(rut_receptor__icontains=search) |
            Q(razon_social_receptor__icontains=search)
        )

    # Calcular estadísticas (Totales)
    # Usar 'dtes' filtrado para que los stats reflejen la búsqueda, 
    # o usar 'dtes_all' si se quieren stats globales. Usualmente globales o del periodo.
    # Aquí usaremos estadísticas del conjunto filtrado actual.
    
    stats = dtes.aggregate(
        total_documentos=Count('id'),
        total_neto=Sum('monto_neto'),
        total_iva=Sum('monto_iva'),
        total_general=Sum('monto_total')
    )

    # Estadísticas por tipo
    stats_por_tipo = dtes.values('tipo_dte').annotate(
        cantidad=Count('id'),
        total=Sum('monto_total')
    ).order_by('tipo_dte')

    # Contexto para el template
    context = {
        'dtes': dtes,
        'stats': stats,
        'stats_por_tipo': stats_por_tipo,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'tipo_dte': tipo_dte,
        'estado': estado,
        'search': search,
        'tipos_dte': dict(DocumentoTributarioElectronico.TIPO_DTE_CHOICES),
        'estados_sii': DocumentoTributarioElectronico.ESTADO_CHOICES,
        # Necesitamos clientes para el filtro. 
        # Idealmente obtener lista de clientes únicos de los DTEs o cargar Clientes.
        # Por rendimiento, dejaremos clientes vacío o una lista básica
        'clientes': [] 
    }
    
    return render(request, 'facturacion_electronica/dte_list.html', context)


@login_required
@requiere_empresa
def dte_detail(request, pk):
    """Detalle de un DTE"""
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=pk, empresa=request.empresa)
    
    context = {
        'dte': dte,
    }
    
    return render(request, 'facturacion_electronica/dte_detail.html', context)


@login_required
@requiere_empresa
def alertas_folios_config(request):
    """Configurar alertas de folios por tipo de documento"""
    
    # Obtener o crear configuraciones para todos los tipos de documento
    configuraciones = []
    for tipo_codigo, tipo_nombre in ArchivoCAF.TIPO_DOCUMENTO_CHOICES:
        config, created = ConfiguracionAlertaFolios.objects.get_or_create(
            empresa=request.empresa,
            tipo_documento=tipo_codigo,
            defaults={'folios_minimos': 20, 'activo': True}
        )
        configuraciones.append(config)
    
    if request.method == 'POST':
        # Procesar formulario
        for config in configuraciones:
            field_name = f'folios_{config.tipo_documento}'
            activo_field = f'activo_{config.tipo_documento}'
            
            if field_name in request.POST:
                try:
                    folios = int(request.POST.get(field_name, 20))
                    activo = activo_field in request.POST
                    
                    config.folios_minimos = folios
                    config.activo = activo
                    config.save()
                except (ValueError, TypeError):
                    pass
        
        messages.success(request, 'Configuración de alertas actualizada correctamente')
        return redirect('facturacion_electronica:alertas_folios_config')
    
    context = {
        'configuraciones': configuraciones,
        'titulo': 'Configuración de Alertas de Folios'
    }
    
    return render(request, 'facturacion_electronica/alertas_folios_config.html', context)
