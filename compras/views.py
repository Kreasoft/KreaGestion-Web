from utilidades.utils import clean_id
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    OrdenCompra, ItemOrdenCompra, RecepcionMercancia, ItemRecepcion,
    DocumentoRecibidoSII, EventoAceptacionReclamoSII,
)
from .forms import (
    OrdenCompraForm, ItemOrdenCompraFormSet, RecepcionMercanciaForm, 
    ItemRecepcionFormSet, BusquedaOrdenForm
)
from empresas.models import Empresa
from articulos.models import Articulo
from proveedores.models import Proveedor
from core.decorators import requiere_empresa


def articulos_compra_qs(empresa):
    if not empresa:
        return Articulo.objects.none()
    return Articulo.objects.filter(empresa=empresa).annotate(
        stock_total=Coalesce(
            Sum('stocks__cantidad', filter=Q(stocks__empresa=empresa)),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    ).order_by('codigo')
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


def extraer_errores_formulario(form, formset=None):
    """Extrae un resumen legible de todos los errores de un formulario y formset"""
    errores = []
    if form:
        for field, err_list in form.errors.items():
            if field == '__all__':
                for err in err_list:
                    errores.append(str(err))
            else:
                label = form.fields[field].label if field in form.fields and form.fields[field].label else field
                for err in err_list:
                    errores.append(f"{label}: {err}")
    if formset:
        for i, f_err in enumerate(formset.errors):
            if f_err:
                for field, err_list in f_err.items():
                    for err in err_list:
                        errores.append(f"Fila {i+1} ({field}): {err}")
        for err in formset.non_form_errors():
            errores.append(f"Ítems: {err}")
    return errores


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
            err_list = extraer_errores_formulario(form, formset)
            if err_list:
                messages.error(request, 'Por favor corrige los siguientes errores: ' + ' | '.join(err_list))
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
        'articulos_empresa': articulos_compra_qs(empresa),
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
            err_list = extraer_errores_formulario(form, formset)
            if err_list:
                messages.error(request, 'Por favor corrige los siguientes errores: ' + ' | '.join(err_list))
            else:
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
        'articulos_empresa': articulos_compra_qs(empresa),
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
    """Bandeja auditable de facturas recibidas y sus eventos ante el SII."""
    empresa, error = obtener_empresa_usuario(request)
    if error:
        messages.error(request, error)
        return redirect('dashboard')

    documentos = DocumentoRecibidoSII.objects.filter(empresa=empresa).prefetch_related('eventos')
    search = request.GET.get('search', '').strip()
    if search:
        documentos = documentos.filter(Q(rut_emisor__icontains=search) | Q(razon_social_emisor__icontains=search) | Q(folio__icontains=search))
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    if fecha_desde:
        documentos = documentos.filter(fecha_emision__gte=fecha_desde)
    if fecha_hasta:
        documentos = documentos.filter(fecha_emision__lte=fecha_hasta)
    totales = documentos.aggregate(total_neto=Sum('monto_neto'), total_iva=Sum('monto_iva'), total_general=Sum('monto_total'))
    documentos = list(documentos)
    orden_acciones = [codigo for codigo, _ in EventoAceptacionReclamoSII.ACCIONES]
    for documento in documentos:
        # La columna Eventos representa decisiones confirmadas por el SII, no
        # intentos de comunicación rechazados. Estos últimos se conservan en
        # la auditoría, pero no se mezclan con los eventos tributarios vigentes.
        resumen_por_accion = {}
        for evento in documento.eventos.all():
            if evento.estado == 'aceptado_sii' and evento.accion not in resumen_por_accion:
                resumen_por_accion[evento.accion] = evento
        documento.eventos_resumen = [resumen_por_accion[codigo] for codigo in orden_acciones if codigo in resumen_por_accion]
    context = {
        'documentos': documentos,
        'empresa': empresa,
        'total_neto': totales['total_neto'] or 0,
        'total_iva': totales['total_iva'] or 0,
        'total_general': totales['total_general'] or 0,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'search': search,
        'acciones_sii': EventoAceptacionReclamoSII.ACCIONES,
        'periodo_sync': request.GET.get('periodo', timezone.localdate().strftime('%Y-%m')),
    }
    return render(request, 'compras/facturas_recibidas_list.html', context)


@login_required
@requiere_empresa
@permission_required('compras.add_documentorecibidosii', raise_exception=True)
@require_POST
def sincronizar_facturas_recibidas_sii(request):
    """Descarga directamente del RCV del SII los documentos del período."""
    from facturacion_electronica.registro_compras_sii import RegistroComprasSII

    periodo_form = request.POST.get('periodo', timezone.localdate().strftime('%Y-%m'))
    periodo = periodo_form.replace('-', '')
    try:
        filas = RegistroComprasSII(request.empresa).consultar_periodo(periodo)
        creados = actualizados = 0
        with transaction.atomic():
            for datos in filas:
                identificacion = {campo: datos.pop(campo) for campo in ('tipo_dte', 'folio', 'rut_emisor')}
                datos.setdefault('xml_original', '')
                datos.setdefault('xml_solicitado_a', '')
                datos.setdefault('razon_social_emisor', '')
                datos.setdefault('tipo_compra_rcv', '')
                _, creado = DocumentoRecibidoSII.objects.update_or_create(
                    empresa=request.empresa, **identificacion, defaults=datos,
                )
                creados += int(creado)
                actualizados += int(not creado)
        messages.success(request, f'RCV sincronizado directamente desde el SII: {creados} nuevos y {actualizados} actualizados.')
    except Exception as exc:
        messages.error(request, f'No fue posible sincronizar el Registro de Compras del SII: {exc}')
    return redirect('compras:facturas_recibidas_sii')


@login_required
@requiere_empresa
@permission_required('compras.add_documentorecibidosii', raise_exception=True)
@require_POST
def importar_factura_recibida_xml(request):
    """Importa el DTE recibido, validando que el receptor sea la empresa activa."""
    from lxml import etree
    from django.utils.dateparse import parse_date

    archivo = request.FILES.get('xml_dte')
    if not archivo or archivo.size > 5 * 1024 * 1024:
        messages.error(request, 'Seleccione un XML de hasta 5 MB.')
        return _redirigir_o_listado_rcv(request)
    try:
        contenido = archivo.read()
        raiz = etree.fromstring(contenido, parser=etree.XMLParser(resolve_entities=False, no_network=True, recover=False))
        valor = lambda nombre, default='': (raiz.xpath(f'(//*[local-name()="{nombre}"])[1]/text()') or [default])[0]
        tipo, folio = str(valor('TipoDTE')), int(valor('Folio'))
        rut_emisor, rut_receptor = str(valor('RUTEmisor')).upper(), str(valor('RUTRecep')).upper()
        normalizar = lambda rut: rut.replace('.', '').replace(' ', '').upper()
        if tipo not in {'33', '34', '43'}:
            raise ValueError('Solo se admiten facturas recibidas tipos 33, 34 y 43.')
        if normalizar(rut_receptor) != normalizar(request.empresa.rut):
            raise ValueError('El RUT receptor del XML no corresponde a la empresa activa.')
        defaults = {
            'razon_social_emisor': str(valor('RznSoc'))[:200],
            'fecha_emision': parse_date(str(valor('FchEmis'))),
            'monto_neto': Decimal(str(valor('MntNeto', '0') or '0')),
            'monto_iva': Decimal(str(valor('IVA', '0') or '0')),
            'monto_total': Decimal(str(valor('MntTotal', '0') or '0')),
            'xml_original': contenido.decode('iso-8859-1' if b'ISO-8859-1' in contenido[:150].upper() else 'utf-8'),
        }
        documento, creado = DocumentoRecibidoSII.objects.update_or_create(
            empresa=request.empresa, rut_emisor=rut_emisor, tipo_dte=tipo, folio=folio, defaults=defaults,
        )
        messages.success(request, f'Factura {folio} {"importada" if creado else "actualizada"}. Consulte su fecha de recepción antes de registrar un evento.')
    except Exception as exc:
        messages.error(request, f'No fue posible importar el XML: {exc}')
    return _redirigir_o_listado_rcv(request)


def _redirigir_o_listado_rcv(request, siguiente=None):
    destino = siguiente or request.POST.get('next') or request.GET.get('next') or ''
    if destino.startswith('/') and not destino.startswith('//'):
        return redirect(destino)
    return redirect('compras:facturas_recibidas_sii')


def _parsear_fecha_sii(valor):
    from django.utils.dateparse import parse_datetime
    fecha = parse_datetime(str(valor or '').replace(' ', 'T'))
    if fecha and timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha)
    return fecha


@login_required
@requiere_empresa
@permission_required('compras.view_documentorecibidosii', raise_exception=True)
@require_POST
def consultar_eventos_factura_sii(request, pk):
    from facturacion_electronica.registro_reclamo_sii import RegistroReclamoSII
    documento = get_object_or_404(DocumentoRecibidoSII, pk=pk, empresa=request.empresa)
    try:
        servicio = RegistroReclamoSII(request.empresa)
        fecha = servicio.consultar_fecha_recepcion(documento)
        fecha_dt = _parsear_fecha_sii(fecha['fecha'])
        if fecha_dt:
            documento.fecha_recepcion_sii = fecha_dt
            documento.save(update_fields=['fecha_recepcion_sii', 'actualizado_en'])
        historial = servicio.listar_eventos(documento)
        messages.success(request, historial['descripcion'] or 'Estado consultado correctamente en el SII.')
    except Exception as exc:
        messages.error(request, f'No fue posible consultar el SII: {exc}')
    return _redirigir_o_listado_rcv(request)


def _texto_solicitud_xml(request, documento, proveedor=None):
    empresa = request.empresa
    tipo = documento.get_tipo_dte_display()
    folio = documento.folio
    fecha = documento.fecha_emision.strftime('%d-%m-%Y') if documento.fecha_emision else '-'
    destino = empresa.get_email_dte() if hasattr(empresa, 'get_email_dte') else empresa.email
    emisor = documento.razon_social_emisor or (proveedor.nombre if proveedor else documento.rut_emisor)
    asunto = 'Solicitud de XML DTE %s folio %s' % (tipo, folio)
    cuerpo = (
        'Estimados:\n\n'
        'Solicitamos el envío del XML original firmado del siguiente DTE, para completar el detalle de ítems en nuestro sistema:\n\n'
        '  Emisor: %s\n'
        '  RUT emisor: %s\n'
        '  Tipo: %s (%s)\n'
        '  Folio: %s\n'
        '  Fecha: %s\n'
        '  Monto total: $ %s\n'
        '  Receptor: %s\n'
        '  RUT receptor: %s\n\n'
        'Por favor envíen el XML de intercambio a: %s\n\n'
        'Sin ese archivo no es posible reconstruir la representación con el detalle de productos/servicios.\n\n'
        'Saludos,\n%s'
        % (
            emisor, documento.rut_emisor, tipo, documento.tipo_dte, folio, fecha,
            '{:,.0f}'.format(int(documento.monto_total or 0)).replace(',', '.'),
            empresa.razon_social or empresa.nombre, empresa.rut, destino or empresa.email,
            empresa.razon_social or empresa.nombre,
        )
    )
    return asunto, cuerpo, destino


@login_required
@requiere_empresa
@permission_required('compras.view_documentorecibidosii', raise_exception=True)
@require_POST
def chequear_xml_factura_sii(request, pk):
    """Confirma si el DTE llegó al SII y si el XML de intercambio está en GestionCloud."""
    from facturacion_electronica.registro_reclamo_sii import RegistroReclamoSII
    documento = get_object_or_404(DocumentoRecibidoSII, pk=pk, empresa=request.empresa)
    sii_ok = False
    fecha_sii = documento.fecha_recepcion_sii
    try:
        servicio = RegistroReclamoSII(request.empresa)
        fecha = servicio.consultar_fecha_recepcion(documento)
        fecha_dt = _parsear_fecha_sii(fecha['fecha'])
        if fecha_dt:
            documento.fecha_recepcion_sii = fecha_dt
            documento.save(update_fields=['fecha_recepcion_sii', 'actualizado_en'])
            fecha_sii = fecha_dt
            sii_ok = True
        elif fecha.get('fecha'):
            sii_ok = True
    except Exception as exc:
        messages.warning(request, 'No se pudo consultar el SII (%s). Se revisa solo el XML en el sistema.' % exc)

    if documento.tiene_xml_dte:
        messages.success(
            request,
            'XML de intercambio ya está cargado. El PDF se puede generar con el detalle de ítems.',
        )
    elif sii_ok or fecha_sii:
        cuando = timezone.localtime(fecha_sii).strftime('%d-%m-%Y %H:%M') if fecha_sii else 'una fecha registrada'
        messages.warning(
            request,
            'El SII sí recibió el DTE (%s), pero el XML con el detalle no ha llegado a GestionCloud. '
            'Pídalo al proveedor o adjúntelo para reconstruir el PDF con ítems.' % cuando,
        )
    else:
        messages.warning(
            request,
            'No hay XML de intercambio en el sistema. El RCV no incluye ítems: hay que pedirlo al proveedor o adjuntar el XML.',
        )
    return _redirigir_o_listado_rcv(request, '/compras/facturas-sii/%s/rcv.pdf' % documento.pk)


@login_required
@requiere_empresa
@permission_required('compras.view_documentorecibidosii', raise_exception=True)
@require_POST
def solicitar_xml_factura_sii(request, pk):
    """Pide expresamente al proveedor el XML firmado del DTE."""
    from django.core.mail import EmailMessage
    from django.conf import settings
    documento = get_object_or_404(DocumentoRecibidoSII, pk=pk, empresa=request.empresa)
    proveedor = _proveedor_por_rut(request.empresa, documento.rut_emisor)
    email = (request.POST.get('email') or '').strip() or (getattr(proveedor, 'email', None) or '')
    volver = '/compras/facturas-sii/%s/rcv.pdf' % documento.pk
    if not email:
        messages.error(request, 'Indique el correo del proveedor para pedir el XML.')
        return _redirigir_o_listado_rcv(request, volver)

    asunto, cuerpo, copia = _texto_solicitud_xml(request, documento, proveedor)
    from utilidades.utils import aviso_correo_no_entregado, conexion_correo, datos_smtp
    smtp = datos_smtp(request.empresa)
    if not smtp['listo']:
        messages.error(request, aviso_correo_no_entregado(email))
        return _redirigir_o_listado_rcv(request, volver)

    enviado = False
    try:
        mensaje = EmailMessage(
            subject=asunto, body=cuerpo, from_email=smtp['from_email'] or getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            to=[email], cc=[copia] if copia and copia.lower() != email.lower() else None,
            connection=conexion_correo(request.empresa),
        )
        mensaje.send(fail_silently=False)
        enviado = True
    except Exception as exc:
        messages.warning(request, 'No se pudo enviar por el servidor de correo (%s). Use Abrir en correo si necesita reenviar.' % exc)

    documento.xml_solicitado_en = timezone.now()
    documento.xml_solicitado_a = email
    documento.save(update_fields=['xml_solicitado_en', 'xml_solicitado_a', 'actualizado_en'])
    if enviado:
        messages.success(
            request,
            'Solicitud de XML enviada a %s. Cuando llegue el archivo, adjúntelo en esta ficha para regenerar el PDF con ítems.' % email,
        )
    return _redirigir_o_listado_rcv(request, volver)


@login_required
@requiere_empresa
@permission_required('compras.registrar_evento_sii', raise_exception=True)
@require_POST
def registrar_evento_factura_sii(request, pk):
    """Registra una decisión tributaria irreversible y conserva la respuesta completa."""
    from facturacion_electronica.registro_reclamo_sii import RegistroReclamoSII
    documento = get_object_or_404(DocumentoRecibidoSII, pk=pk, empresa=request.empresa)
    accion = request.POST.get('accion', '').upper()
    motivo = request.POST.get('motivo', '').strip()
    if request.POST.get('confirmar') != '1':
        messages.error(request, 'Debe confirmar expresamente el envío de la decisión al SII.')
        return redirect('compras:facturas_recibidas_sii')
    if accion not in dict(EventoAceptacionReclamoSII.ACCIONES):
        messages.error(request, 'Acción SII no válida.')
        return redirect('compras:facturas_recibidas_sii')
    if accion.startswith('R') and not motivo:
        messages.error(request, 'Debe registrar un motivo interno para respaldar el reclamo.')
        return redirect('compras:facturas_recibidas_sii')
    if not documento.fecha_recepcion_sii:
        messages.error(request, 'Primero consulte el documento para obtener la fecha oficial de recepción del SII.')
        return redirect('compras:facturas_recibidas_sii')
    if documento.plazo_vencido:
        messages.error(request, 'El plazo legal de 8 días corridos ya está vencido.')
        return redirect('compras:facturas_recibidas_sii')
    acciones_previas = set(documento.eventos.filter(estado='aceptado_sii').values_list('accion', flat=True))
    reclamos = {'RCD', 'RFP', 'RFT'}
    if accion in acciones_previas:
        messages.error(request, 'Este evento ya fue registrado correctamente en el SII.')
        return redirect('compras:facturas_recibidas_sii')
    if accion in reclamos and acciones_previas.intersection({'ACD', 'ERM'}):
        messages.error(request, 'No se puede reclamar un DTE previamente aceptado o con acuse de recibo.')
        return redirect('compras:facturas_recibidas_sii')
    if accion in {'ACD', 'ERM'} and acciones_previas.intersection(reclamos):
        messages.error(request, 'No se puede aceptar ni acusar recibo de un DTE previamente reclamado.')
        return redirect('compras:facturas_recibidas_sii')

    evento = EventoAceptacionReclamoSII.objects.create(documento=documento, accion=accion, motivo=motivo, usuario=request.user)
    try:
        resultado = RegistroReclamoSII(request.empresa).registrar_evento(documento, accion)
        evento.codigo_respuesta = resultado['codigo']
        evento.descripcion_respuesta = resultado['descripcion']
        evento.respuesta_sii = resultado['respuesta']
        evento.fecha_respuesta = timezone.now()
        descripcion_normalizada = (resultado['descripcion'] or '').upper().replace('Ó', 'O')
        # El código 7 confirma que el mismo evento ya existe en el SII. Es un
        # resultado idempotente válido y debe cerrar la auditoría local como
        # aceptada, no presentarse al usuario como un rechazo.
        evento_ya_registrado = resultado['codigo'] == 7 or 'EVENTO REGISTRADO PREVIAMENTE' in descripcion_normalizada
        evento.estado = 'aceptado_sii' if resultado['codigo'] == 0 or evento_ya_registrado or 'ACCION COMPLETADA OK' in descripcion_normalizada else 'rechazado_sii'
        evento.save()
        if evento.estado == 'aceptado_sii':
            if evento_ya_registrado:
                messages.success(request, f'Evento {accion} confirmado: ya se encontraba registrado correctamente en el SII.')
            else:
                messages.success(request, f'Evento {accion} registrado ante el SII: {resultado["descripcion"]}')
        else:
            messages.error(request, f'El SII rechazó el evento ({resultado["codigo"]}): {resultado["descripcion"]}')
    except Exception as exc:
        evento.estado = 'error'
        evento.descripcion_respuesta = str(exc)
        evento.fecha_respuesta = timezone.now()
        evento.save()
        messages.error(request, f'Error al comunicar el evento al SII: {exc}')
    return redirect('compras:facturas_recibidas_sii')


@login_required
@requiere_empresa
@permission_required('compras.view_documentorecibidosii', raise_exception=True)
def descargar_xml_factura_sii(request, pk):
    """Descarga el XML original, aislado por empresa activa."""
    documento = get_object_or_404(DocumentoRecibidoSII, empresa=request.empresa, pk=pk)
    response = HttpResponse(documento.xml_original, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="factura_{documento.tipo_dte}_{documento.folio}.xml"'
    return response


@login_required
@requiere_empresa
@permission_required('compras.view_documentorecibidosii', raise_exception=True)
def ver_registro_rcv_xml(request, pk):
    """Vista HTML del registro RCV, con descarga del XML."""
    from lxml import etree
    documento = get_object_or_404(DocumentoRecibidoSII, empresa=request.empresa, pk=pk)
    raiz = etree.Element('RegistroCompraRCV', fuente='Servicio de Impuestos Internos', esDTEOriginal='false')
    valores = {
        'TipoDTE': documento.tipo_dte, 'Folio': documento.folio, 'RUTProveedor': documento.rut_emisor,
        'RazonSocial': documento.razon_social_emisor, 'FechaDocumento': documento.fecha_emision,
        'FechaRecepcionSII': documento.fecha_recepcion_sii, 'EstadoRCV': documento.estado_rcv,
        'TipoCompra': documento.tipo_compra_rcv, 'MontoNeto': documento.monto_neto,
        'MontoIVA': documento.monto_iva, 'MontoTotal': documento.monto_total,
    }
    for etiqueta, valor in valores.items():
        etree.SubElement(raiz, etiqueta).text = str(valor or '')
    contenido = etree.tostring(raiz, encoding='UTF-8', xml_declaration=True, pretty_print=True)
    if request.GET.get('raw') == '1':
        response = HttpResponse(contenido, content_type='application/xml; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="rcv_{documento.tipo_dte}_{documento.folio}.xml"'
        return response
    return render(request, 'compras/registro_rcv_xml.html', {
        'documento': documento,
        'xml_texto': contenido.decode('utf-8'),
    })


def _rut_clave(rut):
    return ''.join(c for c in str(rut or '').upper() if c.isalnum())


def _rut_pdf(rut):
    limpio = _rut_clave(rut)
    if len(limpio) < 2:
        return str(rut or '-')
    cuerpo, dv = limpio[:-1].lstrip('0') or '0', limpio[-1]
    partes = []
    while cuerpo:
        partes.append(cuerpo[-3:])
        cuerpo = cuerpo[:-3]
    return '%s-%s' % ('.'.join(reversed(partes)), dv)


def _clp_pdf(valor):
    try:
        n = int(Decimal(str(valor or 0)))
    except (TypeError, ValueError, Exception):
        n = 0
    return '$ {:,.0f}'.format(n).replace(',', '.')


def _qty_pdf(valor):
    try:
        n = Decimal(str(valor or 0))
    except Exception:
        return str(valor or '')
    if n == n.to_integral_value():
        return str(int(n))
    return format(n.normalize(), 'f')


def _proveedor_por_rut(empresa, rut):
    clave = _rut_clave(rut)
    if not clave:
        return None
    for cand in Proveedor.objects.filter(empresa=empresa):
        if _rut_clave(cand.rut) == clave:
            return cand
    return None


def _items_desde_xml_dte(xml_texto):
    if not (xml_texto or '').strip():
        return []
    from lxml import etree
    contenido = xml_texto.encode('utf-8') if isinstance(xml_texto, str) else xml_texto
    try:
        raiz = etree.fromstring(
            contenido,
            parser=etree.XMLParser(resolve_entities=False, no_network=True, recover=True),
        )
    except Exception:
        return []
    items = []
    for det in raiz.xpath('//*[local-name()="Detalle"]'):
        txt = lambda n, d='': (det.xpath('.//*[local-name()="%s"]/text()' % n) or [d])[0]
        nombre = (txt('NmbItem') or txt('DscItem') or 'Ítem').strip()
        codigo = (txt('VlrCodigo') or '').strip()
        try:
            cantidad = Decimal(str(txt('QtyItem', '1') or '1').replace(',', '.'))
        except Exception:
            cantidad = Decimal('1')
        try:
            precio = Decimal(str(txt('PrcItem', '0') or '0').replace(',', '.'))
        except Exception:
            precio = Decimal('0')
        try:
            total = Decimal(str(txt('MontoItem', '0') or '0').replace(',', '.'))
        except Exception:
            total = Decimal('0')
        if not total:
            total = (cantidad * precio).quantize(Decimal('1'))
        items.append({
            'nombre': nombre, 'codigo': codigo,
            'cantidad': cantidad, 'precio': precio, 'total': total,
        })
    return items


def _documento_compra_asociado(documento, proveedor=None):
    from documentos.models import DocumentoCompra
    folio = str(documento.folio or '').strip()
    if not folio:
        return None
    qs = DocumentoCompra.objects.filter(
        empresa=documento.empresa, estado_documento='activo',
    ).filter(
        Q(numero_documento=folio) | Q(numero_documento__iendswith=folio)
    ).select_related('proveedor').prefetch_related('items__articulo')
    clave = _rut_clave(documento.rut_emisor)
    coincidencias = []
    for compra in qs:
        numero = ''.join(c for c in str(compra.numero_documento or '') if c.isdigit())
        if numero.lstrip('0') != folio.lstrip('0'):
            continue
        if clave and _rut_clave(compra.proveedor.rut) != clave:
            continue
        coincidencias.append(compra)
    return coincidencias[0] if coincidencias else None


def _items_desde_documento_compra(compra):
    if not compra:
        return []
    items = []
    for linea in compra.items.all():
        articulo = linea.articulo
        items.append({
            'nombre': getattr(articulo, 'nombre', '') or 'Ítem',
            'codigo': getattr(articulo, 'codigo', '') or '',
            'cantidad': Decimal(linea.cantidad or 0),
            'precio': Decimal(linea.precio_unitario or 0),
            'total': Decimal(linea.subtotal or (linea.cantidad or 0) * (linea.precio_unitario or 0)),
        })
    return items


def _items_factura_rcv(documento, proveedor=None):
    """Prioridad: XML original del DTE, luego documento de compra interno. El RCV no trae ítems."""
    items = _items_desde_xml_dte(documento.xml_original)
    if items:
        return items, 'xml'
    compra = _documento_compra_asociado(documento, proveedor)
    items = _items_desde_documento_compra(compra)
    if items:
        return items, 'documento_compra'
    return [], ''


def _contexto_factura_rcv(request, documento):
    empresa = request.empresa
    proveedor = _proveedor_por_rut(empresa, documento.rut_emisor)
    items, origen_items = _items_factura_rcv(documento, proveedor)
    asunto_xml, cuerpo_xml, email_intercambio = _texto_solicitud_xml(request, documento, proveedor)
    from urllib.parse import quote
    return {
        'documento': documento,
        'empresa': empresa,
        'proveedor': proveedor,
        'items': items,
        'origen_items': origen_items,
        'emisor_nombre': (
            documento.razon_social_emisor
            or (proveedor.razon_social if proveedor else '')
            or (proveedor.nombre if proveedor else '')
            or 'Proveedor'
        ).strip(),
        'emisor_giro': (proveedor.giro if proveedor else '') or '',
        'emisor_direccion': ', '.join(
            p for p in ([proveedor.direccion, proveedor.comuna] if proveedor else []) if p
        ),
        'receptor_nombre': empresa.razon_social or empresa.nombre,
        'receptor_rut': _rut_pdf(empresa.rut),
        'receptor_giro': empresa.get_giro_dte() if hasattr(empresa, 'get_giro_dte') else (empresa.giro or ''),
        'receptor_direccion': empresa.get_direccion_dte() if hasattr(empresa, 'get_direccion_dte') else (empresa.direccion or ''),
        'receptor_comuna': empresa.get_comuna_dte() if hasattr(empresa, 'get_comuna_dte') else (empresa.comuna or ''),
        'receptor_ciudad': empresa.get_ciudad_dte() if hasattr(empresa, 'get_ciudad_dte') else (empresa.ciudad or ''),
        'rut_emisor_fmt': _rut_pdf(documento.rut_emisor),
        'email_proveedor': (proveedor.email if proveedor and proveedor.email else ''),
        'email_intercambio': email_intercambio or '',
        'mailto_xml': 'mailto:%s?subject=%s&body=%s' % (
            quote(proveedor.email if proveedor and proveedor.email else ''),
            quote(asunto_xml), quote(cuerpo_xml),
        ),
    }


def _generar_pdf_rcv(request, documento):
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

    ctx = _contexto_factura_rcv(request, documento)
    piedra = colors.HexColor('#5D4037')
    crema = colors.HexColor('#E8DCC8')
    fondo = colors.HexColor('#FAFAF8')
    borde = colors.HexColor('#D8CDC1')
    rojo = colors.HexColor('#C62828')
    gris = colors.HexColor('#6B625A')

    st_emisor = ParagraphStyle('RcvEmisor', fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=piedra)
    st_meta = ParagraphStyle('RcvMeta', fontName='Helvetica', fontSize=8, leading=11, textColor=gris)
    st_box = ParagraphStyle('RcvBox', fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=rojo, alignment=TA_CENTER)
    st_box_sm = ParagraphStyle('RcvBoxSm', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=rojo, alignment=TA_CENTER)
    st_label = ParagraphStyle('RcvLabel', fontName='Helvetica-Bold', fontSize=7, leading=9, textColor=piedra)
    st_val = ParagraphStyle('RcvVal', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.black)
    st_th = ParagraphStyle('RcvTh', fontName='Helvetica-Bold', fontSize=7, leading=9, textColor=piedra, alignment=TA_CENTER)
    st_td = ParagraphStyle('RcvTd', fontName='Helvetica', fontSize=8, leading=10, textColor=colors.black)
    st_td_r = ParagraphStyle('RcvTdR', fontName='Helvetica', fontSize=8, leading=10, alignment=TA_RIGHT)
    st_c = ParagraphStyle('RcvTdC', parent=st_td, alignment=TA_CENTER)
    st_nota = ParagraphStyle('RcvNota', fontName='Helvetica-Oblique', fontSize=7, leading=9, textColor=gris, alignment=TA_CENTER)
    st_obs = ParagraphStyle('RcvObs', fontName='Helvetica', fontSize=7.5, leading=10, textColor=gris)

    emisor_lineas = [
        Paragraph(ctx['emisor_nombre'], st_emisor),
        Paragraph('R.U.T.: %s' % ctx['rut_emisor_fmt'], st_meta),
    ]
    if ctx['emisor_giro']:
        emisor_lineas.append(Paragraph('Giro: %s' % ctx['emisor_giro'], st_meta))
    if ctx['emisor_direccion']:
        emisor_lineas.append(Paragraph(ctx['emisor_direccion'], st_meta))
    caja_dte = Table([
        [Paragraph('R.U.T.: %s' % ctx['rut_emisor_fmt'], st_box)],
        [Paragraph((documento.get_tipo_dte_display() or 'Documento tributario').upper(), st_box)],
        [Paragraph('N° %s' % documento.folio, ParagraphStyle('RcvFolio', parent=st_box, fontSize=14, leading=18))],
        [Paragraph('S.I.I. — CHILE', st_box_sm)],
        [Paragraph('Representación RCV', st_box_sm)],
    ], colWidths=[68*mm])
    caja_dte.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 2, rojo),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
    ]))
    cabecera = Table([[emisor_lineas, caja_dte]], colWidths=[110*mm, 70*mm])
    cabecera.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 8),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
    ]))

    fecha_doc = documento.fecha_emision.strftime('%d-%m-%Y') if documento.fecha_emision else '-'
    fecha_sii = timezone.localtime(documento.fecha_recepcion_sii).strftime('%d-%m-%Y %H:%M') if documento.fecha_recepcion_sii else '-'
    st_fecha = ParagraphStyle('RcvFecha', parent=st_val, alignment=TA_RIGHT)
    fechas = Table([[
        Paragraph('<b>Fecha de emisión:</b> %s &nbsp;&nbsp; <b>Recepción SII:</b> %s' % (fecha_doc, fecha_sii), st_fecha),
    ]], colWidths=[180*mm])
    fechas.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    receptor_datos = [
        [Paragraph('SEÑOR(ES)', st_label), Paragraph(ctx['receptor_nombre'], st_val),
         Paragraph('R.U.T.', st_label), Paragraph(ctx['receptor_rut'], st_val)],
        [Paragraph('GIRO', st_label), Paragraph(ctx['receptor_giro'] or '—', st_val),
         Paragraph('COMUNA', st_label), Paragraph(ctx['receptor_comuna'] or '—', st_val)],
        [Paragraph('DIRECCIÓN', st_label), Paragraph(ctx['receptor_direccion'] or '—', st_val),
         Paragraph('CIUDAD', st_label), Paragraph(ctx['receptor_ciudad'] or '—', st_val)],
    ]
    tabla_receptor = Table(receptor_datos, colWidths=[22*mm, 78*mm, 22*mm, 58*mm])
    tabla_receptor.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), crema),
        ('BACKGROUND', (2, 0), (2, -1), crema),
        ('BOX', (0, 0), (-1, -1), 0.6, borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, borde),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (1, 0), (1, -1), fondo),
        ('BACKGROUND', (3, 0), (3, -1), fondo),
    ]))

    filas_det = [[
        Paragraph('N°', st_th), Paragraph('DETALLE', st_th), Paragraph('CANT.', st_th),
        Paragraph('P. UNITARIO', st_th), Paragraph('TOTAL', st_th),
    ]]
    if ctx['items']:
        for i, item in enumerate(ctx['items'], 1):
            nom = item['nombre']
            if item.get('codigo'):
                nom = '%s<br/><font size="6" color="#6B625A">%s</font>' % (nom, item['codigo'])
            filas_det.append([
                Paragraph(str(i), st_c), Paragraph(nom, st_td),
                Paragraph(_qty_pdf(item['cantidad']), st_c),
                Paragraph(_clp_pdf(item['precio']), st_td_r),
                Paragraph(_clp_pdf(item['total']), st_td_r),
            ])
    else:
        filas_det.append([
            Paragraph('1', st_c),
            Paragraph('Montos según RCV del SII. Detalle no disponible: adjunte el XML del DTE o registre el documento de compra.', st_td),
            Paragraph('1', st_c),
            Paragraph(_clp_pdf(documento.monto_neto), st_td_r),
            Paragraph(_clp_pdf(documento.monto_neto), st_td_r),
        ])
    while len(filas_det) < 7:
        filas_det.append(['', '', '', '', ''])
    tabla_det = Table(filas_det, colWidths=[12*mm, 96*mm, 18*mm, 27*mm, 27*mm])
    tabla_det.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), crema),
        ('TEXTCOLOR', (0, 0), (-1, 0), piedra),
        ('BOX', (0, 0), (-1, -1), 0.6, borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, borde),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))

    origen_txt = ''
    if ctx['origen_items'] == 'xml':
        origen_txt = '<br/>Detalle extraído del XML original del DTE.'
    elif ctx['origen_items'] == 'documento_compra':
        origen_txt = '<br/>Detalle extraído del documento de compra interno.'
    obs_txt = (
        '<b>Observaciones RCV</b><br/>'
        'Sección: %s<br/>Tipo de compra: %s<br/>'
        'Fuente: Registro de Compras y Ventas del SII.%s'
        % (documento.estado_rcv or '—', documento.tipo_compra_rcv or '—', origen_txt)
    )
    caja_obs = Table([[Paragraph(obs_txt, st_obs)]], colWidths=[100*mm])
    caja_obs.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, borde),
        ('BACKGROUND', (0, 0), (-1, -1), fondo),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    st_tot_l = ParagraphStyle('RcvTotL', fontName='Helvetica', fontSize=8, leading=11, textColor=piedra)
    st_tot_v = ParagraphStyle('RcvTotV', fontName='Helvetica', fontSize=8, leading=11, alignment=TA_RIGHT, textColor=piedra)
    st_tot_b = ParagraphStyle('RcvTotB', fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.white)
    st_tot_bv = ParagraphStyle('RcvTotBV', fontName='Helvetica-Bold', fontSize=10, leading=13, alignment=TA_RIGHT, textColor=colors.white)
    filas_tot = [
        [Paragraph('Monto neto', st_tot_l), Paragraph(_clp_pdf(documento.monto_neto), st_tot_v)],
        [Paragraph('IVA', st_tot_l), Paragraph(_clp_pdf(documento.monto_iva), st_tot_v)],
        [Paragraph('TOTAL', st_tot_b), Paragraph(_clp_pdf(documento.monto_total), st_tot_bv)],
    ]
    tabla_tot = Table(filas_tot, colWidths=[42*mm, 36*mm])
    tabla_tot.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, borde),
        ('BACKGROUND', (0, 0), (-1, 1), fondo),
        ('BACKGROUND', (0, 2), (-1, 2), piedra),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    pie = Table([[caja_obs, tabla_tot]], colWidths=[102*mm, 78*mm])
    pie.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 4),
        ('LEFTPADDING', (1, 0), (1, 0), 4),
    ]))

    historia = [
        cabecera, Spacer(1, 3*mm),
        HRFlowable(width='100%', thickness=0.6, color=borde, spaceAfter=3*mm),
        fechas, Spacer(1, 3*mm), tabla_receptor, Spacer(1, 4*mm), tabla_det,
        Spacer(1, 5*mm), pie, Spacer(1, 8*mm),
        Paragraph(
            'Este PDF es una representación de consulta generada desde los datos del RCV. '
            'No reemplaza la representación impresa ni el XML firmado del DTE original emitido por el proveedor.',
            st_nota,
        ),
    ]
    salida = BytesIO()
    pdf = SimpleDocTemplate(
        salida, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm, topMargin=12*mm, bottomMargin=12*mm,
        title='Factura RCV %s-%s' % (documento.tipo_dte, documento.folio),
    )
    pdf.build(historia)
    response = HttpResponse(salida.getvalue(), content_type='application/pdf')
    disposition = 'attachment' if request.GET.get('dl') == '1' else 'inline'
    response['Content-Disposition'] = '%s; filename="factura_rcv_%s_%s.pdf"' % (disposition, documento.tipo_dte, documento.folio)
    return response


@login_required
@requiere_empresa
@permission_required('compras.view_documentorecibidosii', raise_exception=True)
def ver_registro_rcv_pdf(request, pk):
    """Vista HTML tipo factura, con PDF en ?raw=1."""
    documento = get_object_or_404(DocumentoRecibidoSII, empresa=request.empresa, pk=pk)
    if request.GET.get('raw') == '1':
        return _generar_pdf_rcv(request, documento)
    ctx = _contexto_factura_rcv(request, documento)
    return render(request, 'compras/registro_rcv_factura.html', ctx)


