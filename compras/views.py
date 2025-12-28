from utilidades.utils import clean_id
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, F
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import OrdenCompra, ItemOrdenCompra, RecepcionMercancia, ItemRecepcion
from .forms import (
    OrdenCompraForm, ItemOrdenCompraFormSet, RecepcionMercanciaForm, 
    ItemRecepcionFormSet, BusquedaOrdenForm
)
from empresas.models import Empresa
from articulos.models import Articulo
from proveedores.models import Proveedor
from core.decorators import requiere_empresa
from libreria_dte_gdexpress.dte_gdexpress.gdexpress.cliente import ClienteGDExpress
import json


def obtener_empresa_usuario(request):
    """Obtener la empresa del usuario con lógica de sesión para superusuarios"""
    if request.user.is_superuser:
        # Para superusuarios, usar empresa de sesión o Kreasoft por defecto
        empresa_id = request.session.get('empresa_activa')
        if empresa_id:
            try:
                empresa = Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
        else:
            empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
        
        if not empresa:
            empresa = Empresa.objects.first()
        
        if not empresa:
            return None, 'No hay empresas configuradas en el sistema.'
            
        # Guardar empresa en sesión
        request.session['empresa_activa'] = empresa.id
        return empresa, None
    else:
        # Para usuarios normales, usar su empresa asociada
        try:
            empresa = request.user.perfil.empresa
            return empresa, None
        except:
            return None, 'Usuario no tiene empresa asociada.'


@login_required
@requiere_empresa
@permission_required('compras.view_ordencompra', raise_exception=True)
def orden_compra_list(request):
    """Lista de órdenes de compra"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('dashboard')
    
    # Formulario de búsqueda
    search_form = BusquedaOrdenForm(request.GET)
    
    # Obtener órdenes de compra
    ordenes = OrdenCompra.objects.filter(empresa=empresa)
    
    # Aplicar filtros
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        estado_orden = search_form.cleaned_data.get('estado_orden')
        estado_pago = search_form.cleaned_data.get('estado_pago')
        prioridad = search_form.cleaned_data.get('prioridad')
        fecha_desde = search_form.cleaned_data.get('fecha_desde')
        fecha_hasta = search_form.cleaned_data.get('fecha_hasta')
        
        if search:
            ordenes = ordenes.filter(
                Q(numero_orden__icontains=search) |
                Q(proveedor__nombre__icontains=search) |
                Q(items__articulo__nombre__icontains=search)
            ).distinct()
        
        if estado_orden:
            ordenes = ordenes.filter(estado_orden=estado_orden)
        
        if estado_pago:
            ordenes = ordenes.filter(estado_pago=estado_pago)
        
        if prioridad:
            ordenes = ordenes.filter(prioridad=prioridad)
        
        if fecha_desde:
            ordenes = ordenes.filter(fecha_orden__gte=fecha_desde)
        
        if fecha_hasta:
            ordenes = ordenes.filter(fecha_orden__lte=fecha_hasta)
    
    # Ordenar por fecha de orden descendente
    ordenes = ordenes.order_by('-fecha_orden', '-numero_orden')
    
    # Paginación
    paginator = Paginator(ordenes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    stats = {
        'total_ordenes': ordenes.count(),
        'pendientes_aprobacion': ordenes.filter(estado_orden='pendiente_aprobacion').count(),
        'en_proceso': ordenes.filter(estado_orden='en_proceso').count(),
        'completamente_recibidas': ordenes.filter(estado_orden='completamente_recibida').count(),
        'valor_total': ordenes.aggregate(total=Sum('total_orden'))['total'] or Decimal('0.00'),
    }
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'stats': stats,
        'empresa': empresa,
    }
    
    return render(request, 'compras/orden_compra_list.html', context)


@login_required
@requiere_empresa
def orden_compra_detail(request, pk):
    """Detalle de una orden de compra"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('dashboard')
    orden = get_object_or_404(OrdenCompra, pk=pk, empresa=empresa)
    
    # Items de la orden
    items = orden.items.all()
    
    # Recepciones de la orden
    recepciones = orden.recepciones.all()
    
    context = {
        'orden': orden,
        'items': items,
        'recepciones': recepciones,
        'empresa': empresa,
    }
    
    return render(request, 'compras/orden_compra_detail.html', context)


@login_required
@requiere_empresa
@permission_required('compras.add_ordencompra', raise_exception=True)
def orden_compra_create(request):
    """Crear nueva orden de compra"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = OrdenCompraForm(request.POST, empresa=empresa)
        formset = ItemOrdenCompraFormSet(request.POST)
        
        print("=== DEBUG FORMULARIO ===")
        print("Form is valid:", form.is_valid())
        if not form.is_valid():
            print("Form errors:", form.errors)
        print("Formset is valid:", formset.is_valid())
        if not formset.is_valid():
            print("Formset errors:", formset.errors)
        print("POST data:", request.POST)
        
        if form.is_valid() and formset.is_valid():
            try:
                orden = form.save(commit=False)
                orden.empresa = empresa
                orden.creado_por = request.user

                # Generar número de orden usando ConfiguracionEmpresa
                try:
                    from empresas.models import ConfiguracionEmpresa
                    configuracion = ConfiguracionEmpresa.objects.get(empresa=empresa)
                    orden.numero_orden = configuracion.generar_numero_orden_compra()
                except Exception as e:
                    print(f"Error generando número: {e}")
                    # Fallback: usar el del formulario o generar uno simple
                    ultima_orden = OrdenCompra.objects.filter(empresa=empresa).order_by('-id').first()
                    if ultima_orden and '-' in ultima_orden.numero_orden:
                        try:
                            numero = int(ultima_orden.numero_orden.split('-')[-1]) + 1
                        except ValueError:
                            numero = 1
                    else:
                        numero = 1
                    orden.numero_orden = f"OC-{numero:06d}"

                orden.save()
                
                # Guardar items
                formset.instance = orden
                formset.save()
                
                # Calcular totales
                orden.calcular_totales()
                
                messages.success(request, f'Orden de compra {orden.numero_orden} creada exitosamente.')
                return redirect('compras:orden_compra_detail', pk=orden.pk)
            except Exception as e:
                print("Error al guardar:", str(e))
                messages.error(request, f'Error al crear la orden: {str(e)}')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = OrdenCompraForm(empresa=empresa)
        formset = ItemOrdenCompraFormSet()
    
    context = {
        'form': form,
        'formset': formset,
        'empresa': empresa,
        'titulo': 'Crear Orden de Compra',
        'articulos_empresa': Articulo.objects.filter(empresa=empresa) if empresa else Articulo.objects.none(),
    }
    
    return render(request, 'compras/orden_compra_form.html', context)


@login_required
@requiere_empresa
@permission_required('compras.change_ordencompra', raise_exception=True)
def orden_compra_update(request, pk):
    """Editar orden de compra"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('dashboard')
    orden = get_object_or_404(OrdenCompra, pk=pk, empresa=empresa)
    
    # Verificar que se puede editar - NO se pueden editar órdenes completadas
    if orden.estado_orden == 'completada':
        messages.error(request, 'No se puede editar una orden completada.')
        return redirect('compras:orden_compra_detail', pk=orden.pk)
    
    if request.method == 'POST':
        print("=== DEBUG ORDEN COMPRA UPDATE ===")
        print("POST data recibido:", request.POST)
        
        form = OrdenCompraForm(request.POST, instance=orden, empresa=empresa)
        formset = ItemOrdenCompraFormSet(request.POST, instance=orden)
        
        print("Form is valid:", form.is_valid())
        if not form.is_valid():
            print("Form errors:", form.errors)
        
        print("Formset is valid:", formset.is_valid())
        if not formset.is_valid():
            print("Formset errors:", formset.errors)
            print("Formset non_form_errors:", formset.non_form_errors())
        
        if form.is_valid() and formset.is_valid():
            try:
                orden = form.save()
                print("Orden guardada:", orden.pk)
                
                # Guardar items
                formset.save()
                print("Formset guardado exitosamente")
                
                # Calcular totales
                orden.calcular_totales()
                print("Totales calculados")
                
                messages.success(request, f'Orden de compra {orden.numero_orden} actualizada exitosamente.')
                return redirect('compras:orden_compra_detail', pk=orden.pk)
            except Exception as e:
                print("Error al guardar:", str(e))
                messages.error(request, f'Error al actualizar la orden: {str(e)}')
        else:
            print("Formulario no válido - no se guarda")
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = OrdenCompraForm(instance=orden, empresa=empresa)
        # Inicializar formset con los items existentes
        formset = ItemOrdenCompraFormSet(instance=orden)
        # Asegurar que se carguen todos los items existentes
        if orden.items.exists():
            formset = ItemOrdenCompraFormSet(instance=orden, queryset=orden.items.all())
    
    context = {
        'form': form,
        'formset': formset,
        'orden': orden,
        'empresa': empresa,
        'titulo': 'Editar Orden de Compra',
        'articulos_empresa': Articulo.objects.filter(empresa=empresa) if empresa else Articulo.objects.none(),
    }
    
    return render(request, 'compras/orden_compra_form.html', context)


@login_required
@requiere_empresa
@permission_required('compras.delete_ordencompra', raise_exception=True)
def orden_compra_delete(request, pk):
    """Eliminar orden de compra"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        return JsonResponse({'success': False, 'message': error})
    
    try:
        orden = get_object_or_404(OrdenCompra, pk=pk, empresa=empresa)
        
        # Verificar que se puede eliminar - NO se pueden eliminar órdenes completadas
        if orden.estado_orden == 'completada':
            return JsonResponse({
                'success': False, 
                'message': 'No se pueden eliminar órdenes completadas.'
            })
        
        if request.method == 'POST':
            numero_orden = orden.numero_orden
            orden.delete()
            return JsonResponse({
                'success': True,
                'message': f'Orden de compra {numero_orden} eliminada exitosamente.'
            })
        
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@requiere_empresa
def orden_compra_aprobar(request, pk):
    """Aprobar una orden de compra"""
    # Obtener la empresa del usuario
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('dashboard')
    orden = get_object_or_404(OrdenCompra, pk=pk, empresa=empresa)
    
    if orden.puede_aprobar():
        orden.estado_orden = 'aprobada'
        orden.aprobado_por = request.user
        orden.fecha_aprobacion = timezone.now()
        orden.save()
        
        messages.success(request, f'Orden de compra {orden.numero_orden} aprobada exitosamente.')
    else:
        messages.error(request, 'Esta orden no puede ser aprobada.')
    
    return redirect('compras:orden_compra_detail', pk=orden.pk)


@login_required
@requiere_empresa
def get_articulo_info(request):
    """Obtener información de un artículo via AJAX"""
    articulo_id = clean_id(request.GET.get('articulo_id'))
    
    try:
        articulo = Articulo.objects.get(pk=articulo_id)
        data = {
            'nombre': articulo.nombre,
            'descripcion': articulo.descripcion,
            'unidad_medida': articulo.unidad_medida.nombre if articulo.unidad_medida else '',
            'precio_compra': str(articulo.precio_compra) if articulo.precio_compra else '0.00',
            'stock_actual': str(articulo.get_stock_total()),
        }
        return JsonResponse(data)
    except Articulo.DoesNotExist:
        return JsonResponse({'error': 'Artículo no encontrado'}, status=404)


@login_required
def proveedor_create_ajax(request):
    """Vista AJAX para crear un nuevo proveedor desde el formulario de documento de compra"""
    if request.method == 'POST':
        try:
            # Obtener la empresa del usuario
            empresa, error = obtener_empresa_usuario(request)
            if error:
                return JsonResponse({
                    'success': False,
                    'message': error
                }, status=400)
            
            # Parsear datos JSON
            data = json.loads(request.body)
            
            # Validar campos obligatorios
            rut = data.get('rut', '').strip()
            razon_social = data.get('razon_social', '').strip()
            
            if not rut or not razon_social:
                return JsonResponse({
                    'success': False,
                    'message': 'RUT y Razón Social son obligatorios'
                }, status=400)
            
            # Verificar si el proveedor ya existe
            if Proveedor.objects.filter(empresa=empresa, rut=rut).exists():
                return JsonResponse({
                    'success': False,
                    'message': f'Ya existe un proveedor con el RUT {rut} en esta empresa'
                }, status=400)
            
            # Crear el proveedor
            proveedor = Proveedor.objects.create(
                empresa=empresa,
                nombre=data.get('nombre_fantasia', razon_social),
                razon_social=razon_social,
                rut=rut,
                giro=data.get('giro', 'Sin especificar'),
                direccion=data.get('direccion', 'Sin especificar'),
                comuna=data.get('comuna', 'Sin especificar'),
                ciudad=data.get('ciudad', 'Sin especificar'),
                region=data.get('region', 'Sin especificar'),
                telefono=data.get('telefono', ''),
                email=data.get('email', ''),
                tipo_proveedor='productos',
                estado='activo',
                creado_por=request.user
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Proveedor creado exitosamente',
                'proveedor': {
                    'id': proveedor.id,
                    'rut': proveedor.rut,
                    'razon_social': proveedor.razon_social,
                    'nombre': proveedor.nombre
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Error al procesar los datos JSON'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al crear el proveedor: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Método no permitido'
    }, status=405)


@login_required
@requiere_empresa
@permission_required('compras.view_ordencompra', raise_exception=True)
def facturas_recibidas_sii(request):
    """
    Vista para listar facturas recibidas del SII (vía DTEBox)
    Por defecto muestra los documentos del mes y año actual
    """
    # Obtener empresa activa
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('dashboard')

    if not getattr(empresa, 'dtebox_habilitado', False):
        messages.warning(request, f"La empresa {empresa.nombre} no tiene habilitada la integración con DTEBox.")
        return redirect('compras:orden_compra_list')

    # Calcular fechas
    hoy = datetime.now()
    
    # Prioridad: fechas específicas -> días atrás -> mes actual
    f_desde_str = request.GET.get('fecha_desde')
    f_hasta_str = request.GET.get('fecha_hasta')
    
    if f_desde_str and f_hasta_str:
        fecha_desde = f_desde_str
        fecha_hasta = f_hasta_str
        dias = None # No se usa si hay fechas fijas
    else:
        if request.GET.get('dias'):
            try:
                dias = int(request.GET['dias'])
            except:
                inicio_mes = hoy.replace(day=1)
                dias = (hoy - inicio_mes).days + 1
        else:
            inicio_mes = hoy.replace(day=1)
            dias = (hoy - inicio_mes).days + 1
            
        fecha_desde = (hoy - timedelta(days=dias)).strftime('%Y-%m-%d')
        fecha_hasta = hoy.strftime('%Y-%m-%d')
    
    # Consultar DTEBox
    documentos_transformados = []
    try:
        import base64
        import urllib.request
        import json
        
        ambiente = 'P'
        grupo = 'R'
        
        # El RUT para RUTRecep debe tener guión pero sin puntos
        rut_raw = empresa.rut.replace('.', '').replace(' ', '').strip()
        if '-' not in rut_raw:
            # Si no tiene guión, intentar ponerlo (asumiendo último dígito es DV)
            rut_receptor = f"{rut_raw[:-1]}-{rut_raw[-1]}"
        else:
            rut_receptor = rut_raw
            
        # Construir query
        query_string = f"(RUTRecep:{rut_receptor} AND FchEmis:[{fecha_desde} TO {fecha_hasta}] AND (TipoDTE:33 OR TipoDTE:34 OR TipoDTE:61 OR TipoDTE:56))"
        query_base64 = base64.b64encode(query_string.encode('utf-8')).decode('utf-8')
        
        base_url = empresa.dtebox_url or "http://200.6.118.43"
        if '/api/Core.svc/' in base_url:
            base_url = base_url.split('/api/')[0]
        base_url = base_url.strip().rstrip('/')
        if not base_url.startswith('http'):
            base_url = f"http://{base_url}"
            
        url = f"{base_url}/api/Core.svc/core/PaginatedSearch/{ambiente}/{grupo}/{query_base64}/0/300"
        
        req = urllib.request.Request(url)
        req.add_header('AuthKey', empresa.dtebox_auth_key)
        req.add_header('Content-Type', 'application/json')
        req.add_header('Accept', 'application/json')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        result = str(data.get('Result', '1'))
        if result == '0':
            data_base64 = data.get('Data')
            if data_base64:
                import xml.etree.ElementTree as ET
                xml_bytes = base64.b64decode(data_base64)
                xml_string = xml_bytes.decode('utf-8')
                root = ET.fromstring(xml_string)
                document_elements = root.findall('.//document')
                
                for doc_element in document_elements:
                    tipo_dte = doc_element.findtext('TipoDTE', 'N/A')
                    # Traducir tipo
                    tipos_nombre = {'33': 'Factura Electrónica', '34': 'Factura Exenta', '61': 'Nota de Crédito', '56': 'Nota de Débito'}
                    tipo_nombre = tipos_nombre.get(tipo_dte, f'DTE {tipo_dte}')
                    
                    folio = doc_element.findtext('Folio', 'N/A')
                    fecha_emis = doc_element.findtext('FchEmis', 'N/A')
                    rut_emisor = doc_element.findtext('RUTEmisor', 'N/A')
                    razon_social = doc_element.findtext('RznSoc', 'Emisor desconocido')
                    mnt_neto = int(doc_element.findtext('MntNeto', 0) or 0)
                    iva = int(doc_element.findtext('IVA', 0) or 0)
                    mnt_total = int(doc_element.findtext('MntTotal', 0) or 0)
                    doc_xml = ET.tostring(doc_element, encoding='unicode')
                    download_pdf_url = doc_element.findtext('DownloadCustomerDocumentUrl', '')
                    
                    documentos_transformados.append({
                        'tipo_documento': tipo_nombre,
                        'numero': folio,
                        'fecha_emision': fecha_emis,
                        'rut_emisor': rut_emisor,
                        'razon_social_emisor': razon_social,
                        'neto': mnt_neto,
                        'iva': iva,
                        'total': mnt_total,
                        'xml_data': doc_xml,
                        'download_pdf_url': download_pdf_url,
                    })
        
        # Aplicar búsqueda local
        search = request.GET.get('search')
        if search:
            search = search.lower()
            documentos_transformados = [
                doc for doc in documentos_transformados 
                if search in doc['numero'].lower() or 
                   search in doc['rut_emisor'].lower() or 
                   search in doc['razon_social_emisor'].lower()
            ]

    except Exception as e:
        messages.error(request, f"Error al consultar DTEBox: {str(e)}")

    # Calcular totales sobre la lista final filtrada
    total_neto = sum(doc['neto'] for doc in documentos_transformados)
    total_iva = sum(doc['iva'] for doc in documentos_transformados)
    total_general = sum(doc['total'] for doc in documentos_transformados)
    
    # Banderas para el template (evitar comparaciones complejas)
    dias_sel = request.GET.get('dias', '30')
    
    context = {
        'documentos': documentos_transformados,
        'empresa': empresa,
        'total_neto': total_neto,
        'total_iva': total_iva,
        'total_general': total_general,
        'dias_7': dias_sel == '7',
        'dias_30': dias_sel == '30',
        'dias_90': dias_sel == '90',
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'search': request.GET.get('search', ''),
    }
    
    # Guardar XMLs en sesión para permitir descarga
    request.session['facturas_sii_xmls'] = {doc['numero']: doc['xml_data'] for doc in documentos_transformados if 'xml_data' in doc}
    
    return render(request, 'compras/facturas_recibidas_list.html', context)


@login_required
def descargar_xml_factura_sii(request, folio):
    """Descarga el XML de una factura SII"""
    xmls = request.session.get('facturas_sii_xmls', {})
    xml_data = xmls.get(folio)
    
    if not xml_data:
        messages.error(request, 'XML no disponible. Vuelve a consultar los documentos.')
        return redirect('compras:facturas_recibidas_sii')
    
    # Crear respuesta HTTP con el XML
    from django.http import HttpResponse
    response = HttpResponse(xml_data, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="factura_{folio}.xml"'
    return response
