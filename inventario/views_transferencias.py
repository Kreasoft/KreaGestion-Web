from utilidades.utils import clean_id
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.db import transaction
from django.utils import timezone
from datetime import timedelta, datetime
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.files.base import ContentFile
from decimal import Decimal
import re
from .models import TransferenciaInventario, Inventario, Stock
from .forms import TransferenciaInventarioForm
from core.decorators import requiere_empresa
from bodegas.models import Bodega
from articulos.models import Articulo
from facturacion_electronica.models import ArchivoCAF, DocumentoTributarioElectronico
from facturacion_electronica.services import DTEService
from django.db import IntegrityError
import json


@login_required
@requiere_empresa
def transferencia_list(request):
    """Lista todas las transferencias de inventario"""
    transferencias = TransferenciaInventario.objects.filter(
        empresa=request.empresa
    ).select_related(
        'bodega_origen', 'bodega_destino', 'creado_por'
    ).prefetch_related('detalles').order_by('-fecha_transferencia')
    
    # Filtros
    estado = request.GET.get('estado')
    if estado:
        transferencias = transferencias.filter(estado=estado)
    
    bodega_origen_id = request.GET.get('bodega_origen')
    if bodega_origen_id:
        transferencias = transferencias.filter(bodega_origen_id=bodega_origen_id)
    
    bodega_destino_id = request.GET.get('bodega_destino')
    if bodega_destino_id:
        transferencias = transferencias.filter(bodega_destino_id=bodega_destino_id)
    
    search = request.GET.get('search')
    if search:
        transferencias = transferencias.filter(
            Q(numero_folio__icontains=search) |
            Q(observaciones__icontains=search)
        )

    # Rango de fechas (por defecto últimos 30 días)
    fecha_hasta_str = request.GET.get('hasta')
    fecha_desde_str = request.GET.get('desde')
    hoy = timezone.now().date()
    fecha_hasta = hoy
    fecha_desde = hoy - timedelta(days=30)
    try:
        if fecha_desde_str:
            fecha_desde = datetime.fromisoformat(fecha_desde_str).date()
        if fecha_hasta_str:
            fecha_hasta = datetime.fromisoformat(fecha_hasta_str).date()
    except Exception:
        # Si el parse falla, mantener defaults
        pass

    # Aplicar filtro por fecha (incluye ambos extremos)
    transferencias = transferencias.filter(
        fecha_transferencia__date__gte=fecha_desde,
        fecha_transferencia__date__lte=fecha_hasta
    )
    
    # Paginación
    paginator = Paginator(transferencias, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    total_transferencias = transferencias.count()
    pendientes = transferencias.filter(estado='pendiente').count()
    confirmadas = transferencias.filter(estado='confirmado').count()
    canceladas = transferencias.filter(estado='cancelado').count()
    
    # Obtener bodegas para filtros
    bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True)
    
    context = {
        'page_obj': page_obj,
        'bodegas': bodegas,
        'total_transferencias': total_transferencias,
        'pendientes': pendientes,
        'confirmadas': confirmadas,
        'canceladas': canceladas,
        'titulo': 'Transferencias de Inventario',
        'fecha_desde': fecha_desde.isoformat(),
        'fecha_hasta': fecha_hasta.isoformat(),
    }
    
    return render(request, 'inventario/transferencia_list.html', context)


@login_required
@requiere_empresa
def transferencia_create(request):
    """Crear o editar transferencia de inventario"""
    # Verificar si es edición (aceptar edit por GET o POST)
    edit_id = request.GET.get('edit') or request.POST.get('edit')
    transferencia_edit = None
    if edit_id:
        transferencia_edit = get_object_or_404(
            TransferenciaInventario,
            pk=edit_id,
            empresa=request.empresa,
            estado='confirmado'  # Solo se pueden editar transferencias confirmadas
        )
    
    if request.method == 'POST':
        # Sanitizar posibles separadores no numéricos en IDs (e.g., NBSP en "2\xa0023")
        post = request.POST.copy()
        for key in ('bodega_origen', 'bodega_destino'):
            if post.get(key):
                post[key] = re.sub(r"\D+", "", str(post[key]))

        # Si es edición, pasar la instancia al formulario para actualizar
        if transferencia_edit:
            form = TransferenciaInventarioForm(post, instance=transferencia_edit, empresa=request.empresa)
        else:
            form = TransferenciaInventarioForm(post, empresa=request.empresa)
        
        # Obtener los artículos del formulario
        articulos_data = request.POST.get('articulos_json', '[]')
        
        try:
            articulos = json.loads(articulos_data)
            
            if not articulos:
                messages.error(request, 'Debe agregar al menos un artículo a la transferencia.')
                return render(request, 'inventario/transferencia_form.html', {
                    'form': form,
                    'articulos': Articulo.objects.filter(empresa=request.empresa, activo=True),
                    'bodegas': Bodega.objects.filter(empresa=request.empresa, activa=True),
                    'transferencia_edit': transferencia_edit,
                    'articulos_edit': '[]',
                    'titulo': 'Nueva Transferencia de Inventario'
                })
            
            if form.is_valid():
                # VALIDACIÓN CRÍTICA: Bodegas diferentes
                bodega_origen = form.cleaned_data.get('bodega_origen')
                bodega_destino = form.cleaned_data.get('bodega_destino')
                
                if bodega_origen == bodega_destino:
                    messages.error(request, '❌ ERROR: La bodega de origen y destino no pueden ser la misma. Una transferencia debe ser entre bodegas diferentes.')
                    return render(request, 'inventario/transferencia_form.html', {
                        'form': form,
                        'articulos': Articulo.objects.filter(empresa=request.empresa, activo=True),
                        'bodegas': Bodega.objects.filter(empresa=request.empresa, activa=True),
                        'transferencia_edit': transferencia_edit,
                        'articulos_edit': json.dumps(articulos),
                        'titulo': 'Nueva Transferencia de Inventario'
                    })
                
                # VALIDACIÓN: Fecha obligatoria
                fecha_transferencia = form.cleaned_data.get('fecha_transferencia')
                if not fecha_transferencia:
                    messages.error(request, '❌ ERROR: Debe especificar una fecha de transferencia válida.')
                    return render(request, 'inventario/transferencia_form.html', {
                        'form': form,
                        'articulos': Articulo.objects.filter(empresa=request.empresa, activo=True),
                        'bodegas': Bodega.objects.filter(empresa=request.empresa, activa=True),
                        'transferencia_edit': transferencia_edit,
                        'articulos_edit': json.dumps(articulos),
                        'titulo': 'Nueva Transferencia de Inventario'
                    })
                
                with transaction.atomic():
                    # Crear/actualizar la transferencia sin guardar aún
                    transferencia = form.save(commit=False)
                    transferencia.empresa = request.empresa
                    transferencia.creado_por = request.user

                    # Si es creación, generar número de folio automático
                    if not transferencia.pk or not transferencia.numero_folio:
                        ultimo_folio = TransferenciaInventario.objects.filter(
                            empresa=request.empresa
                        ).order_by('-id').first()
                        if ultimo_folio and ultimo_folio.numero_folio:
                            try:
                                ultimo_numero = int(ultimo_folio.numero_folio.split('-')[-1])
                                nuevo_numero = ultimo_numero + 1
                            except:
                                nuevo_numero = 1
                        else:
                            nuevo_numero = 1
                        transferencia.numero_folio = f"TRANS-{nuevo_numero:06d}"

                    # Si se proporcionó fecha personalizada, usarla
                    fecha_transferencia = form.cleaned_data.get('fecha_transferencia')
                    if fecha_transferencia:
                        transferencia.fecha_transferencia = fecha_transferencia

                    transferencia.save()

                    # Si es edición: revertir stock y borrar detalles anteriores
                    if transferencia_edit:
                        for detalle_ant in transferencia.detalles.all():
                            # Revertir stock en bodega origen (sumar)
                            stock_origen = Stock.objects.get(
                                empresa=request.empresa,
                                bodega=transferencia.bodega_origen,
                                articulo=detalle_ant.articulo
                            )
                            stock_origen.cantidad += detalle_ant.cantidad
                            stock_origen.save()

                            # Revertir stock en bodega destino (restar)
                            stock_destino = Stock.objects.get(
                                empresa=request.empresa,
                                bodega=transferencia.bodega_destino,
                                articulo=detalle_ant.articulo
                            )
                            stock_destino.cantidad -= detalle_ant.cantidad
                            stock_destino.save()

                        # Borrar movimientos anteriores
                        transferencia.detalles.all().delete()

                    # VALIDAR ARTÍCULOS: Cada artículo debe tener datos completos
                    for idx, item in enumerate(articulos, 1):
                        # Validar ID de artículo
                        raw_id = item.get('articulo_id')
                        if not raw_id:
                            raise ValueError(f"❌ Item #{idx}: Debe seleccionar un artículo válido.")
                        
                        # Validar cantidad
                        cantidad_str = item.get('cantidad')
                        if not cantidad_str or cantidad_str == '0':
                            raise ValueError(f"❌ Item #{idx}: Debe especificar una cantidad mayor a 0.")
                    
                    # Crear los detalles de la transferencia (nuevos)
                    for item in articulos:
                        raw_id = item.get('articulo_id')
                        try:
                            articulo_id = int(re.sub(r"\D+", "", str(raw_id)))
                        except Exception:
                            raise ValueError(f"ID de artículo inválido: {raw_id}")
                        
                        try:
                            articulo = Articulo.objects.get(id=articulo_id, empresa=request.empresa, activo=True)
                        except Articulo.DoesNotExist:
                            raise ValueError(f"El artículo con ID {articulo_id} no existe o no está activo.")
                        
                        cantidad = Decimal(str(item['cantidad']))
                        
                        # Verificar stock disponible en bodega origen
                        try:
                            stock_origen = Stock.objects.get(
                                empresa=request.empresa,
                                bodega=transferencia.bodega_origen,
                                articulo=articulo
                            )
                            
                            if stock_origen.cantidad < cantidad:
                                raise ValueError(
                                    f'Stock insuficiente para {articulo.nombre}. '
                                    f'Disponible: {stock_origen.cantidad}, Solicitado: {cantidad}'
                                )
                        except Stock.DoesNotExist:
                            raise ValueError(
                                f'No hay stock disponible de {articulo.nombre} en la bodega origen.'
                            )
                        
                        # Usar precio de venta del artículo para valorizar
                        try:
                            precio_venta = Decimal(str(articulo.precio_venta)) if articulo.precio_venta else Decimal('0')
                        except (ValueError, TypeError):
                            precio_venta = Decimal('0')
                        
                        # Crear movimiento de inventario
                        Inventario.objects.create(
                            empresa=request.empresa,
                            transferencia=transferencia,
                            bodega_origen=transferencia.bodega_origen,
                            bodega_destino=transferencia.bodega_destino,
                            articulo=articulo,
                            tipo_movimiento='transferencia',
                            cantidad=cantidad,
                            precio_unitario=precio_venta,
                            estado='confirmado',
                            creado_por=request.user,
                            descripcion=f'Transferencia {transferencia.numero_folio}'
                        )
                        
                        # Actualizar stock en bodega origen (restar)
                        stock_origen.cantidad -= cantidad
                        stock_origen.save()
                        
                        # Actualizar stock en bodega destino (sumar)
                        stock_destino, created = Stock.objects.get_or_create(
                            empresa=request.empresa,
                            bodega=transferencia.bodega_destino,
                            articulo=articulo,
                            defaults={
                                'cantidad': 0,
                                'precio_promedio': stock_origen.precio_promedio
                            }
                        )
                        
                        if not created:
                            # Calcular nuevo precio promedio
                            if stock_destino.cantidad > 0:
                                total_actual = stock_destino.cantidad * stock_destino.precio_promedio
                                total_nuevo = cantidad * stock_origen.precio_promedio
                                stock_destino.precio_promedio = (
                                    (total_actual + total_nuevo) / (stock_destino.cantidad + cantidad)
                                )
                        
                        stock_destino.cantidad += cantidad
                        stock_destino.save()
                    
                    # Mensaje según operación
                    if transferencia_edit:
                        messages.success(
                            request,
                            f'Transferencia {transferencia.numero_folio} actualizada exitosamente.'
                        )
                    else:
                        messages.success(
                            request, 
                            f'Transferencia {transferencia.numero_folio} creada exitosamente.'
                        )
                    return redirect('inventario:transferencia_detail', pk=transferencia.pk)
                    
        except ValueError as e:
            messages.error(request, str(e))
        except json.JSONDecodeError:
            messages.error(request, 'Error al procesar los artículos.')
        except Exception as e:
            messages.error(request, f'Error al crear la transferencia: {str(e)}')
        # Al haber error no se hace return; se preservan datos del formulario más abajo
    else:
        if transferencia_edit:
            # Cargar datos de la transferencia a editar
            form = TransferenciaInventarioForm(
                instance=transferencia_edit,
                empresa=request.empresa
            )
        else:
            form = TransferenciaInventarioForm(empresa=request.empresa)
    
    # Obtener artículos y bodegas para el formulario
    articulos = Articulo.objects.filter(empresa=request.empresa, activo=True)
    bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True)
    
    # Preparar datos de artículos: en edición desde la transferencia; en POST con error preservar lo enviado
    articulos_edit = []
    if transferencia_edit and request.method != 'POST':
        for detalle in transferencia_edit.detalles.all():
            articulos_edit.append({
                'articulo_id': detalle.articulo.id,
                'codigo': detalle.articulo.codigo,
                'nombre': detalle.articulo.nombre,
                'cantidad': float(detalle.cantidad),
                'precio_venta': float(detalle.precio_unitario)
            })
    elif request.method == 'POST':
        articulos_data = request.POST.get('articulos_json', '[]')
        try:
            articulos_edit = json.loads(articulos_data)
        except json.JSONDecodeError:
            articulos_edit = []
    
    context = {
        'form': form,
        'articulos': articulos,
        'bodegas': bodegas,
        'transferencia_edit': transferencia_edit,
        'articulos_edit': json.dumps(articulos_edit) if articulos_edit else '[]',
        'titulo': f'Editar Transferencia {transferencia_edit.numero_folio}' if transferencia_edit else 'Nueva Transferencia de Inventario'
    }
    
    return render(request, 'inventario/transferencia_form.html', context)


@login_required
@requiere_empresa
def transferencia_detail(request, pk):
    """Ver detalle de una transferencia"""
    transferencia = get_object_or_404(
        TransferenciaInventario, 
        pk=pk, 
        empresa=request.empresa
    )
    
    # Obtener los detalles de la transferencia
    detalles = transferencia.detalles.all().select_related('articulo')
    
    # Calcular totales
    total_articulos = detalles.count()
    total_cantidad = sum(detalle.cantidad for detalle in detalles)
    subtotal = sum(detalle.total for detalle in detalles)
    
    # Calcular IVA (19%)
    iva = subtotal * Decimal('0.19')
    total_con_iva = subtotal + iva
    
    context = {
        'transferencia': transferencia,
        'detalles': detalles,
        'total_articulos': total_articulos,
        'total_cantidad': total_cantidad,
        'subtotal': subtotal,
        'iva': iva,
        'total_con_iva': total_con_iva,
        'titulo': f'Transferencia {transferencia.numero_folio}'
    }
    
    return render(request, 'inventario/transferencia_detail.html', context)


@login_required
@requiere_empresa
def transferencia_cancelar(request, pk):
    """Cancelar una transferencia y revertir los movimientos"""
    transferencia = get_object_or_404(
        TransferenciaInventario, 
        pk=pk, 
        empresa=request.empresa
    )
    
    if transferencia.estado == 'cancelado':
        messages.warning(request, 'Esta transferencia ya está cancelada.')
        return redirect('inventario:transferencia_detail', pk=pk)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Revertir los movimientos de stock
                for detalle in transferencia.detalles.all():
                    # Devolver stock a bodega origen
                    stock_origen = Stock.objects.get(
                        empresa=request.empresa,
                        bodega=transferencia.bodega_origen,
                        articulo=detalle.articulo
                    )
                    stock_origen.cantidad += detalle.cantidad
                    stock_origen.save()
                    
                    # Quitar stock de bodega destino
                    stock_destino = Stock.objects.get(
                        empresa=request.empresa,
                        bodega=transferencia.bodega_destino,
                        articulo=detalle.articulo
                    )
                    stock_destino.cantidad -= detalle.cantidad
                    stock_destino.save()
                    
                    # Actualizar estado del movimiento
                    detalle.estado = 'cancelado'
                    detalle.save()
                
                # Actualizar estado de la transferencia
                transferencia.estado = 'cancelado'
                transferencia.save()
                
                messages.success(
                    request, 
                    f'Transferencia {transferencia.numero_folio} cancelada exitosamente.'
                )
                return redirect('inventario:transferencia_detail', pk=pk)
                
        except Exception as e:
            messages.error(request, f'Error al cancelar la transferencia: {str(e)}')
            return redirect('inventario:transferencia_detail', pk=pk)
    
    context = {
        'transferencia': transferencia,
        'titulo': f'Cancelar Transferencia {transferencia.numero_folio}'
    }
    
    return render(request, 'inventario/transferencia_confirm_cancel.html', context)


@login_required
@requiere_empresa
def api_stock_disponible(request):
    """API para obtener el stock disponible de un artículo en una bodega.
    Acepta cantidad_ya_en_lista (opcional) para descontar lo ya agregado a la transferencia del mismo artículo.
    """
    articulo_id = clean_id(request.GET.get('articulo_id'))
    bodega_id = clean_id(request.GET.get('bodega_id'))
    cantidad_ya_en_lista = request.GET.get('cantidad_ya_en_lista', '0')
    
    if not articulo_id or not bodega_id:
        return JsonResponse({'error': 'Parámetros faltantes'}, status=400)
    
    try:
        cantidad_reservada = Decimal(str(cantidad_ya_en_lista))
    except (ValueError, TypeError):
        cantidad_reservada = Decimal('0')
    
    try:
        stock = Stock.objects.get(
            empresa=request.empresa,
            bodega_id=bodega_id,
            articulo_id=articulo_id
        )
        disponible = max(Decimal('0'), stock.cantidad - cantidad_reservada)
        return JsonResponse({
            'stock_disponible': float(disponible),
            'stock_en_bodega': float(stock.cantidad),
            'precio_promedio': float(stock.precio_promedio)
        })
    except Stock.DoesNotExist:
        return JsonResponse({
            'stock_disponible': 0,
            'stock_en_bodega': 0,
            'precio_promedio': 0
        })


@login_required
@requiere_empresa
def transferencia_imprimir_guia(request, pk):
    """Imprimir guía de despacho electrónica"""
    transferencia = get_object_or_404(
        TransferenciaInventario,
        pk=pk,
        empresa=request.empresa
    )
    
    if not transferencia.guia_despacho:
        messages.error(request, 'Esta transferencia no tiene guía de despacho asociada')
        return redirect('inventario:transferencia_detail', pk=pk)
    
    dte = transferencia.guia_despacho
    
    # Obtener detalles de la transferencia
    detalles = transferencia.detalles.all().select_related('articulo', 'articulo__unidad_medida')
    
    # Calcular totales
    subtotal = sum(detalle.total for detalle in detalles)
    iva = subtotal * Decimal('0.19')
    total = subtotal + iva
    
    context = {
        'guia': dte,  # Usar 'guia' como nombre de variable para el template
        'dte': dte,
        'transferencia': transferencia,
        'detalles': detalles,
        'subtotal': subtotal,
        'iva': iva,
        'total': total,
        'empresa': request.empresa,
    }
    
    return render(request, 'inventario/guia_despacho_html.html', context)


@login_required
@requiere_empresa
@require_POST
def transferencia_generar_guia(request, pk):
    """Generar guía de despacho electrónica para una transferencia"""
    try:
        transferencia = get_object_or_404(
            TransferenciaInventario,
            pk=pk,
            empresa=request.empresa,
            estado='confirmado'
        )
        
        # Verificar si ya tiene guía
        if transferencia.guia_despacho:
            return JsonResponse({
                'success': False,
                'error': 'Esta transferencia ya tiene una guía de despacho asociada'
            })
        
        # Obtener sucursal (casa matriz por defecto)
        from empresas.models import Sucursal
        from facturacion_electronica.services import FolioService
        
        sucursal = Sucursal.objects.filter(empresa=request.empresa, es_principal=True).first()
        if not sucursal:
            sucursal = Sucursal.objects.filter(empresa=request.empresa).first()
        
        if not sucursal:
            return JsonResponse({
                'success': False,
                'error': 'No se encontró sucursal para la empresa'
            })
        
        # USAR FolioService CENTRALIZADO para asignación de folios
        with transaction.atomic():
            # NOTA: obtener_siguiente_folio retorna (folio, caf) - 2 valores
            folio, caf = FolioService.obtener_siguiente_folio(
                empresa=request.empresa,
                tipo_documento='52',
                sucursal=sucursal
            )
            
            if not caf or not folio:
                return JsonResponse({
                    'success': False,
                    'error': f'No hay CAF activo disponible para Guías de Despacho (52) en sucursal {sucursal.nombre}. Por favor, cargue un CAF tipo 52.'
                })
            
            # Verificar que el CAF esté vigente
            if not caf.esta_vigente():
                return JsonResponse({
                    'success': False,
                    'error': 'El CAF de Guías de Despacho ha vencido'
                })
            
            # Calcular totales
            detalles = transferencia.detalles.all()
            subtotal = sum(detalle.total for detalle in detalles)
            iva = subtotal * Decimal('0.19')
            total = subtotal + iva
            
            # Generar DTE completo con timbre usando el servicio
            try:
                from facturacion_electronica.dte_service import DTEService as DTEServiceReal
                from facturacion_electronica.dte_generator import DTEXMLGenerator
                from facturacion_electronica.firma_electronica import FirmadorDTE
                from facturacion_electronica.pdf417_generator import PDF417Generator
                
                # Preparar datos para el generador de XML
                # Crear objeto temporal tipo venta para el generador
                class TransferenciaWrapper:
                    def __init__(self, transferencia, subtotal, iva, total):
                        self.empresa = transferencia.empresa
                        self.cliente = None
                        self.tipo_documento = '52'
                        self.fecha_emision = timezone.now().date()
                        # IndTraslado obligatorio para guías: 5 = Traslado interno (transferencias entre sucursales)
                        self.tipo_traslado = '5'
                        self.tipo_despacho = '5'
                        # Receptor (es la misma empresa para traslado interno)
                        self.rut_receptor = transferencia.empresa.rut
                        self.razon_social_receptor = transferencia.empresa.nombre
                        self.giro_receptor = transferencia.empresa.giro
                        self.direccion_receptor = transferencia.empresa.direccion
                        self.comuna_receptor = transferencia.empresa.comuna
                        self.ciudad_receptor = transferencia.empresa.ciudad
                        # Montos (usar nombres exactos esperados por el generador)
                        self.monto_neto = subtotal
                        self.monto_exento = Decimal('0')
                        self.monto_iva = iva
                        self.monto_total = total
                        self.descuento = Decimal('0')
                        self.items = transferencia.detalles
                        
                venta_wrapper = TransferenciaWrapper(transferencia, subtotal, iva, total)
                
                # 1. Generar XML del DTE
                generator = DTEXMLGenerator(request.empresa, venta_wrapper, '52', folio, caf)
                xml_sin_firmar = generator.generar_xml()
                
                # 2. Firmar el XML
                firmador = FirmadorDTE(
                    request.empresa.certificado_digital.path,
                    request.empresa.password_certificado
                )
                xml_firmado = firmador.firmar_xml(xml_sin_firmar)
                
                # 3. Generar TED (Timbre Electrónico)
                ted_xml = None
                pdf417_data = None
                
                # Intentar usar DTEBox para timbrar si está habilitado
                if getattr(request.empresa, 'dtebox_habilitado', False):
                    try:
                        from facturacion_electronica.dtebox_service import DTEBoxService
                        dtebox = DTEBoxService(request.empresa)
                        print(f"Solicitando timbre a DTEBox para Guía {folio}...")
                        res_dtebox = dtebox.timbrar_dte(xml_firmado, '52')
                        if res_dtebox['success'] and res_dtebox.get('ted'):
                            ted_xml = res_dtebox['ted']
                            print("✅ Timbre obtenido exitosamente desde DTEBox")
                    except Exception as e_dtebox:
                        print(f"⚠️ Error al timbrar con DTEBox: {e_dtebox}. Intentando local...")

                # Si no se obtuvo de DTEBox, generar localmente
                if not ted_xml:
                    print("Generando timbre localmente (Offline)...")
                    dte_data = {
                        'rut_emisor': request.empresa.rut,
                        'tipo_dte': '52',
                        'folio': folio,
                        'fecha_emision': timezone.now().date().strftime('%Y-%m-%d'),
                        'rut_receptor': request.empresa.rut,
                        'razon_social_receptor': request.empresa.nombre,
                        'monto_total': int(total),
                        'item_1': 'Guía de Despacho Electrónica',
                    }
                    
                    # Extraer datos reales del CAF
                    datos_caf = {'modulo': '', 'exponente': ''}
                    try:
                        # Usar el método existente en DTEService para parsear el CAF
                        service_temp = DTEServiceReal(request.empresa)
                        datos_parsed = service_temp._parsear_datos_caf(caf)
                        datos_caf['modulo'] = datos_parsed.get('M', 'MODULO_ERROR')
                        datos_caf['exponente'] = datos_parsed.get('E', 'EXPONENTE_ERROR')
                    except Exception as e_caf:
                        print(f"Error parseando CAF: {e_caf}")
                        datos_caf['modulo'] = 'ERROR'
                        datos_caf['exponente'] = 'ERROR'

                    caf_data = {
                        'rut_emisor': request.empresa.rut,
                        'razon_social': request.empresa.razon_social_sii or request.empresa.razon_social,
                        'tipo_documento': '52',
                        'folio_desde': caf.folio_desde,
                        'folio_hasta': caf.folio_hasta,
                        'fecha_autorizacion': caf.fecha_autorizacion.strftime('%Y-%m-%d'),
                        'modulo': datos_caf['modulo'],
                        'exponente': datos_caf['exponente'],
                        'firma': caf.firma_electronica,
                    }
                    
                    ted_xml = firmador.generar_ted(dte_data, caf_data)
                
                # Generar datos PDF417 (siempre necesario para la imagen)
                pdf417_data = firmador.generar_datos_pdf417(ted_xml)
                
                # 4. Crear DTE en BD
                dte = DocumentoTributarioElectronico.objects.create(
                    empresa=request.empresa,
                    caf_utilizado=caf,
                    tipo_dte='52',
                    folio=folio,
                    fecha_emision=timezone.now().date(),
                    tipo_traslado='5',  # Traslado interno
                    usuario_creacion=request.user,
                    # Emisor
                    rut_emisor=request.empresa.rut,
                    razon_social_emisor=request.empresa.razon_social_sii or request.empresa.razon_social,
                    giro_emisor=request.empresa.giro_sii or request.empresa.giro or '',
                    direccion_emisor=request.empresa.direccion_casa_matriz or request.empresa.direccion or '',
                    comuna_emisor=request.empresa.comuna_casa_matriz or request.empresa.comuna or '',
                    # Receptor (usar datos de la empresa para traslado interno)
                    rut_receptor=request.empresa.rut,
                    razon_social_receptor=request.empresa.nombre,
                    giro_receptor=request.empresa.giro or '',
                    direccion_receptor=request.empresa.direccion or '',
                    comuna_receptor=request.empresa.comuna or '',
                    ciudad_receptor=request.empresa.ciudad or '',
                    # Montos
                    monto_neto=subtotal.quantize(Decimal('1')),
                    monto_exento=Decimal('0'),
                    monto_iva=iva.quantize(Decimal('1')),
                    monto_total=total.quantize(Decimal('1')),
                    # XML y Timbre
                    xml_dte=xml_sin_firmar,
                    xml_firmado=xml_firmado,
                    timbre_electronico=ted_xml,
                    datos_pdf417=pdf417_data,
                    # Estado
                    estado_sii='generado'
                )
                
                # 5. Generar imagen PDF417
                PDF417Generator.guardar_pdf417_en_dte(dte)
                
                print(f"✅ Guía de Despacho generada con timbre: Folio {folio}")
                
            except Exception as e:
                import traceback
                print(f"❌ Error generando DTE con timbre: {e}")
                traceback.print_exc()
                
                # Crear DTE básico sin timbre
                dte = DocumentoTributarioElectronico.objects.create(
                    empresa=request.empresa,
                    caf_utilizado=caf,
                    tipo_dte='52',
                    folio=folio,
                    fecha_emision=timezone.now().date(),
                    tipo_traslado='5',
                    usuario_creacion=request.user,
                    rut_emisor=request.empresa.rut,
                    razon_social_emisor=request.empresa.razon_social_sii or request.empresa.razon_social,
                    rut_receptor=request.empresa.rut,
                    razon_social_receptor=request.empresa.nombre,
                    monto_neto=subtotal.quantize(Decimal('1')),
                    monto_exento=Decimal('0'),
                    monto_iva=iva.quantize(Decimal('1')),
                    monto_total=total.quantize(Decimal('1')),
                    estado_sii='generado'
                )
                # Intentar guardar un PDF417 placeholder para visualización
                try:
                    dte.timbre_electronico = 'DOCUMENTO SIN TIMBRE - PLACEHOLDER'
                    dte.save(update_fields=['timbre_electronico'])
                    from facturacion_electronica.pdf417_generator import PDF417Generator
                    PDF417Generator.guardar_pdf417_en_dte(dte)
                except Exception as e2:
                    print(f"⚠️ No se pudo generar timbre placeholder: {e2}")
            
            # Asociar guía a la transferencia
            transferencia.guia_despacho = dte
            transferencia.save()
            
            return JsonResponse({
                'success': True,
                'folio': folio,
                'message': f'Guía de Despacho N° {folio} generada exitosamente'
            })
            
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error al generar la guía: {str(e)}'
        })
