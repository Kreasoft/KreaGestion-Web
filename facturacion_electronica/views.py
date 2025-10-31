from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from core.decorators import requiere_empresa
from .models import ArchivoCAF, DocumentoTributarioElectronico, EnvioDTE, ConfiguracionAlertaFolios
from .forms import ArchivoCAFForm
import xml.etree.ElementTree as ET
from datetime import datetime


@login_required
@requiere_empresa
def caf_list(request):
    """Lista de archivos CAF de la empresa"""
    archivos_caf = ArchivoCAF.objects.filter(
        empresa=request.empresa
    ).order_by('-fecha_carga')
    
    # Estadísticas
    total_caf = archivos_caf.count()
    activos = archivos_caf.filter(estado='activo').count()
    agotados = archivos_caf.filter(estado='agotado').count()
    
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
    
    context = {
        'archivos_caf': archivos_caf,
        'total_caf': total_caf,
        'activos': activos,
        'agotados': agotados,
        'folios_por_tipo': folios_por_tipo,
        'alertas_config': alertas_config,
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
        form = ArchivoCAFForm(request.POST, request.FILES)
        
        print(f"[DEBUG] DEBUG CAF - POST recibido")
        print(f"   - Empresa: {request.empresa}")
        print(f"   - Files: {request.FILES}")
        print(f"   - Form válido: {form.is_valid()}")
        if not form.is_valid():
            print(f"   - Errores: {form.errors}")
        
        if form.is_valid():
            try:
                # Leer el archivo ANTES de la transacción
                archivo_xml = request.FILES['archivo_xml']
                
                # Intentar decodificar con diferentes codificaciones (SII usa ISO-8859-1)
                contenido_bytes = archivo_xml.read()
                contenido_xml = None
                
                for encoding in ['utf-8', 'iso-8859-1', 'windows-1252', 'latin-1']:
                    try:
                        contenido_xml = contenido_bytes.decode(encoding)
                        print(f"[OK] Archivo decodificado exitosamente con: {encoding}")
                        break
                    except UnicodeDecodeError:
                        continue
                
                if contenido_xml is None:
                    raise ValueError("No se pudo decodificar el archivo XML. Formato no soportado.")
                
                # Parsear el XML para extraer datos
                root = ET.fromstring(contenido_xml)
                
                with transaction.atomic():
                    
                    # Buscar los datos del CAF
                    # Namespace del SII
                    ns = {'sii': 'http://www.sii.cl/SiiDte'}
                    
                    # Intentar con y sin namespace
                    da = root.find('.//DA') or root.find('.//{http://www.sii.cl/SiiDte}DA')
                    
                    if da is None:
                        raise ValueError("No se encontró el elemento DA en el archivo CAF")
                    
                    # Extraer datos
                    rango_elem = da.find('.//RNG') or da.find('.//{http://www.sii.cl/SiiDte}RNG')
                    if rango_elem is None:
                        raise ValueError("No se encontró el rango de folios (RNG) en el CAF")
                    
                    folio_desde = int(rango_elem.find('D').text if rango_elem.find('D') is not None 
                                    else rango_elem.find('{http://www.sii.cl/SiiDte}D').text)
                    folio_hasta = int(rango_elem.find('H').text if rango_elem.find('H') is not None 
                                    else rango_elem.find('{http://www.sii.cl/SiiDte}H').text)
                    
                    # Fecha de autorización
                    fa_elem = da.find('.//FA') or da.find('.//{http://www.sii.cl/SiiDte}FA')
                    if fa_elem is not None:
                        fecha_texto = fa_elem.text
                        try:
                            fecha_autorizacion = datetime.strptime(fecha_texto, '%Y-%m-%d').date()
                        except:
                            fecha_autorizacion = datetime.now().date()
                    else:
                        fecha_autorizacion = datetime.now().date()
                    
                    # Firma electrónica (FRMA)
                    frma_elem = root.find('.//FRMA') or root.find('.//{http://www.sii.cl/SiiDte}FRMA')
                    firma_electronica = frma_elem.text if frma_elem is not None else ''
                    
                    # Verificar si ya existe un CAF con este rango
                    tipo_documento = form.cleaned_data['tipo_documento']
                    if ArchivoCAF.objects.filter(
                        empresa=request.empresa,
                        tipo_documento=tipo_documento,
                        folio_desde=folio_desde,
                        folio_hasta=folio_hasta
                    ).exists():
                        messages.error(request, f'Ya existe un CAF para este rango de folios ({folio_desde}-{folio_hasta})')
                        return redirect('facturacion_electronica:caf_list')
                    
                    # Obtener folio inicial si se especificó
                    folio_inicial = form.cleaned_data.get('folio_inicial')
                    
                    # Validar folio inicial
                    if folio_inicial:
                        if folio_inicial < folio_desde:
                            messages.error(request, f'El folio inicial ({folio_inicial}) no puede ser menor al primer folio del CAF ({folio_desde})')
                            return redirect('facturacion_electronica:caf_list')
                        if folio_inicial > folio_hasta:
                            messages.error(request, f'El folio inicial ({folio_inicial}) no puede ser mayor al último folio del CAF ({folio_hasta})')
                            return redirect('facturacion_electronica:caf_list')
                        
                        # Calcular folios ya utilizados
                        folios_ya_usados = folio_inicial - folio_desde
                        folio_actual = folio_inicial - 1
                        print(f"📋 Folio inicial especificado: {folio_inicial}")
                        print(f"   Folios ya usados: {folios_ya_usados}")
                    else:
                        # Comenzar desde el principio
                        folios_ya_usados = 0
                        folio_actual = folio_desde - 1
                        print(f"📋 Sin folio inicial, comenzando desde: {folio_desde}")
                    
                    # Crear el registro CAF
                    caf = form.save(commit=False)
                    caf.empresa = request.empresa
                    caf.folio_desde = folio_desde
                    caf.folio_hasta = folio_hasta
                    caf.cantidad_folios = folio_hasta - folio_desde + 1
                    caf.folio_actual = folio_actual
                    caf.folios_utilizados = folios_ya_usados
                    caf.contenido_caf = contenido_xml
                    caf.fecha_autorizacion = fecha_autorizacion
                    caf.firma_electronica = firma_electronica
                    caf.usuario_carga = request.user
                    caf.estado = 'activo'
                    
                    # Guardar el archivo (resetear puntero si es necesario)
                    # Verificar si el archivo ya fue leído
                    if hasattr(archivo_xml, 'seek'):
                        try:
                            archivo_xml.seek(0)
                        except:
                            pass
                    
                    caf.save()
                    
                    # Mensaje de éxito con información del folio inicial
                    if folio_inicial:
                        mensaje_exito = (
                            f'CAF cargado exitosamente. '
                            f'Folios: {folio_desde} - {folio_hasta} ({caf.cantidad_folios} folios). '
                            f'Iniciando desde folio {folio_inicial} ({folios_ya_usados} folios ya usados, '
                            f'{caf.folios_disponibles()} disponibles).'
                        )
                    else:
                        mensaje_exito = (
                            f'CAF cargado exitosamente. '
                            f'Folios: {folio_desde} - {folio_hasta} ({caf.cantidad_folios} folios disponibles).'
                        )
                    
                    messages.success(request, mensaje_exito)
                    return redirect('facturacion_electronica:caf_list')
                    
            except ET.ParseError as e:
                print(f"[ERROR] ERROR ParseError: {str(e)}")
                messages.error(request, f'Error al leer el archivo XML: {str(e)}')
            except ValueError as e:
                print(f"[ERROR] ERROR ValueError: {str(e)}")
                messages.error(request, f'Error en los datos del CAF: {str(e)}')
            except Exception as e:
                print(f"[ERROR] ERROR Exception: {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Error al procesar el CAF: {str(e)}')
    else:
        form = ArchivoCAFForm()
    
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
    """Lista de DTEs emitidos"""
    dtes = DocumentoTributarioElectronico.objects.filter(
        empresa=request.empresa
    ).order_by('-fecha_emision', '-folio')
    
    context = {
        'dtes': dtes,
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
