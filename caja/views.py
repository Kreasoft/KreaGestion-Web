from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction, IntegrityError, models
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

from empresas.decorators import requiere_empresa
from .models import Caja, AperturaCaja, MovimientoCaja, VentaProcesada
from .forms import CajaForm, AperturaCajaForm, CierreCajaForm, ProcesarVentaForm, MovimientoCajaForm
from ventas.models import Venta, VentaDetalle, FormaPago
from inventario.models import Stock
# TODO: Implementar modelos de cuenta corriente para clientes en tesoreria
# from tesoreria.models import CuentaCorrienteCliente, MovimientoCuentaCorriente


# ========================================
# GESTIÓN DE CAJAS
# ========================================

@login_required
@requiere_empresa
@permission_required('caja.view_caja', raise_exception=True)
def caja_list(request):
    """Lista de cajas"""
    cajas = Caja.objects.filter(empresa=request.empresa).select_related('sucursal', 'estacion_trabajo', 'bodega')
    
    context = {
        'cajas': cajas,
    }
    return render(request, 'caja/caja_list.html', context)


@login_required
@requiere_empresa
@permission_required('caja.add_caja', raise_exception=True)
def caja_create(request):
    """Crear nueva caja"""
    if request.method == 'POST':
        form = CajaForm(request.POST, empresa=request.empresa)
        if form.is_valid():
            caja = form.save(commit=False)
            caja.empresa = request.empresa
            
            # Asignar automáticamente la primera sucursal disponible
            from empresas.models import Sucursal
            primera_sucursal = Sucursal.objects.filter(empresa=request.empresa).first()
            if primera_sucursal:
                caja.sucursal = primera_sucursal
            
            caja.save()
            messages.success(request, f'Caja "{caja.nombre}" creada exitosamente.')
            return redirect('caja:caja_list')
    else:
        form = CajaForm(empresa=request.empresa)
    
    context = {
        'form': form,
        'title': 'Crear Caja',
        'submit_text': 'Crear Caja',
    }
    return render(request, 'caja/caja_form.html', context)


@login_required
@requiere_empresa
@permission_required('caja.change_caja', raise_exception=True)
def caja_update(request, pk):
    """Editar caja"""
    caja = get_object_or_404(Caja, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        form = CajaForm(request.POST, instance=caja, empresa=request.empresa)
        if form.is_valid():
            form.save()
            messages.success(request, f'Caja "{caja.nombre}" actualizada exitosamente.')
            return redirect('caja:caja_list')
    else:
        form = CajaForm(instance=caja, empresa=request.empresa)
    
    context = {
        'form': form,
        'caja': caja,
        'title': 'Editar Caja',
        'submit_text': 'Guardar Cambios',
    }
    return render(request, 'caja/caja_form.html', context)


# ========================================
# APERTURA Y CIERRE DE CAJA
# ========================================

@login_required
@requiere_empresa
@permission_required('caja.view_aperturacaja', raise_exception=True)
def apertura_list(request):
    """Lista de aperturas de caja"""
    aperturas = AperturaCaja.objects.filter(
        caja__empresa=request.empresa
    ).select_related('caja', 'usuario_apertura', 'usuario_cierre').order_by('-fecha_apertura')
    
    # Filtros
    estado = request.GET.get('estado')
    if estado:
        aperturas = aperturas.filter(estado=estado)
    
    # Obtener cajas disponibles para abrir
    cajas_disponibles = Caja.objects.filter(
        empresa=request.empresa,
        activo=True
    ).exclude(
        id__in=AperturaCaja.objects.filter(estado='abierta').values_list('caja_id', flat=True)
    )
    
    context = {
        'aperturas': aperturas,
        'estado_filtro': estado,
        'cajas_disponibles': cajas_disponibles,
    }
    return render(request, 'caja/apertura_list.html', context)


@login_required
@requiere_empresa
@permission_required('caja.add_aperturacaja', raise_exception=True)
def apertura_create(request):
    """Abrir caja"""
    if request.method == 'POST':
        # Crear apertura manualmente desde el modal
        caja_id = request.POST.get('caja')
        monto_inicial = request.POST.get('monto_inicial', 0)
        observaciones = request.POST.get('observaciones_apertura', '')
        
        try:
            caja = Caja.objects.get(id=caja_id, empresa=request.empresa, activo=True)
            
            # Verificar que la caja no esté ya abierta
            if caja.get_apertura_activa():
                messages.error(request, f'La caja "{caja.nombre}" ya está abierta.')
                return redirect('caja:apertura_list')
            
            # Crear apertura
            apertura = AperturaCaja.objects.create(
                caja=caja,
                usuario_apertura=request.user,
                monto_inicial=monto_inicial,
                observaciones_apertura=observaciones,
                estado='abierta'
            )
            
            messages.success(request, f'Caja "{apertura.caja.nombre}" abierta exitosamente.')
            return redirect('caja:apertura_detail', pk=apertura.pk)
            
        except Caja.DoesNotExist:
            messages.error(request, 'La caja seleccionada no existe o no está disponible.')
            return redirect('caja:apertura_list')
        except Exception as e:
            messages.error(request, f'Error al abrir la caja: {str(e)}')
            return redirect('caja:apertura_list')
    else:
        # Si se accede por GET, mostrar el formulario tradicional
        form = AperturaCajaForm(empresa=request.empresa)
        context = {
            'form': form,
            'title': 'Abrir Caja',
            'submit_text': 'Abrir Caja',
        }
        return render(request, 'caja/apertura_form.html', context)


@login_required
@requiere_empresa
@permission_required('caja.view_aperturacaja', raise_exception=True)
def apertura_detail(request, pk):
    """Detalle de apertura de caja"""
    apertura = get_object_or_404(AperturaCaja, pk=pk, caja__empresa=request.empresa)
    
    # Obtener movimientos
    movimientos = apertura.movimientos.all().select_related('forma_pago', 'usuario', 'venta')
    
    # Obtener tickets pendientes del día ACTUAL (no del día de apertura)
    # Usar timezone.now() para consistencia con procesar_venta_buscar
    from django.utils import timezone
    hoy_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    tickets_pendientes = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='vale',
        estado='borrador',
        fecha_creacion__gte=hoy_inicio,
        fecha_creacion__lte=hoy_fin
    ).select_related('cliente', 'vendedor').order_by('-fecha_creacion')
    
    context = {
        'apertura': apertura,
        'movimientos': movimientos,
        'tickets_pendientes': tickets_pendientes,
    }
    return render(request, 'caja/apertura_detail.html', context)


@login_required
@requiere_empresa
@permission_required('caja.change_aperturacaja', raise_exception=True)
def apertura_cerrar(request, pk):
    """Cerrar caja"""
    apertura = get_object_or_404(AperturaCaja, pk=pk, caja__empresa=request.empresa)
    
    if apertura.estado == 'cerrada':
        messages.warning(request, 'Esta caja ya está cerrada.')
        return redirect('caja:apertura_detail', pk=apertura.pk)
    
    if request.method == 'POST':
        form = CierreCajaForm(request.POST)
        if form.is_valid():
            monto_contado = form.cleaned_data['monto_contado']
            observaciones = form.cleaned_data['observaciones_cierre']
            
            apertura.cerrar_caja(
                usuario=request.user,
                monto_contado=monto_contado,
                observaciones=observaciones
            )
            
            messages.success(request, f'Caja "{apertura.caja.nombre}" cerrada exitosamente. Puedes imprimir el informe de cierre desde el detalle de la caja.')
            return redirect('caja:apertura_detail', pk=apertura.pk)
    else:
        # Calcular totales actuales para mostrar
        apertura.calcular_totales()
        form = CierreCajaForm(initial={'monto_contado': apertura.monto_final})
    
    context = {
        'form': form,
        'apertura': apertura,
        'title': f'Cerrar Caja {apertura.caja.nombre}',
    }
    return render(request, 'caja/apertura_cerrar.html', context)


@login_required
@requiere_empresa
@permission_required('caja.view_aperturacaja', raise_exception=True)
def apertura_imprimir(request, pk):
    """Imprimir informe de cierre de caja"""
    try:
        apertura = AperturaCaja.objects.select_related('caja', 'caja__empresa').get(pk=pk, caja__empresa=request.empresa)
    except AperturaCaja.DoesNotExist:
        # Intentar obtener sin filtro de empresa para debug
        apertura = get_object_or_404(AperturaCaja.objects.select_related('caja', 'caja__empresa'), pk=pk)
        # Si llegamos aquí, existe pero no pertenece a la empresa del usuario
        messages.error(request, f'Esta apertura de caja no pertenece a tu empresa.')
        return redirect('caja:apertura_list')
    
    # Recalcular totales para asegurar datos actualizados
    apertura.calcular_totales()
    
    # Obtener ventas procesadas durante esta apertura
    ventas = VentaProcesada.objects.filter(
        apertura_caja=apertura
    ).select_related('venta_preventa', 'venta_final', 'usuario_proceso').order_by('fecha_proceso')
    
    # Agrupar ventas por forma de pago
    ventas_por_forma_pago = {}
    for venta_proc in ventas:
        venta_final = venta_proc.venta_final
        movimiento = venta_proc.movimiento_caja
        
        forma_pago_nombre = movimiento.forma_pago.nombre if movimiento.forma_pago else 'Sin especificar'
        if forma_pago_nombre not in ventas_por_forma_pago:
            ventas_por_forma_pago[forma_pago_nombre] = {
                'ventas': [],
                'total': Decimal('0.00'),
                'cantidad': 0
            }
        ventas_por_forma_pago[forma_pago_nombre]['ventas'].append(venta_proc)
        ventas_por_forma_pago[forma_pago_nombre]['total'] += venta_final.total if venta_final else Decimal('0.00')
        ventas_por_forma_pago[forma_pago_nombre]['cantidad'] += 1
    
    # Obtener movimientos de caja (ingresos/egresos manuales, no ventas)
    movimientos = MovimientoCaja.objects.filter(
        apertura_caja=apertura,
        tipo__in=['ingreso', 'retiro']  # Solo movimientos manuales
    ).order_by('fecha')
    
    # Calcular totales de movimientos
    ingresos_extra = movimientos.filter(tipo='ingreso').aggregate(
        total=models.Sum('monto')
    )['total'] or Decimal('0.00')
    
    egresos_extra = movimientos.filter(tipo='retiro').aggregate(
        total=models.Sum('monto')
    )['total'] or Decimal('0.00')
    
    # Calcular diferencia de caja si está cerrada
    diferencia_caja = Decimal('0.00')
    if apertura.estado == 'cerrada' and apertura.fecha_cierre:
        # Buscar la diferencia en las observaciones (temporal, mejor sería un campo específico)
        if 'Diferencia de caja:' in (apertura.observaciones_cierre or ''):
            try:
                import re
                match = re.search(r'Diferencia de caja: \$?([-\d,.]+)', apertura.observaciones_cierre)
                if match:
                    diferencia_caja = Decimal(match.group(1).replace(',', ''))
            except:
                pass
    
    context = {
        'apertura': apertura,
        'ventas': ventas,
        'ventas_por_forma_pago': ventas_por_forma_pago,
        'movimientos': movimientos,
        'ingresos_extra': ingresos_extra,
        'egresos_extra': egresos_extra,
        'diferencia_caja': diferencia_caja,
        'empresa': request.empresa,
    }
    
    return render(request, 'caja/apertura_informe_impreso.html', context)


@login_required
@requiere_empresa
def estado_caf_pos(request):
    """Vista AJAX para obtener el estado de CAF en formato JSON para el POS"""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        try:
            from facturacion_electronica.services import DTEService
            disponibilidad = DTEService.verificar_disponibilidad_folios(request.empresa)

            # Obtener detalles de CAFs activos
            from facturacion_electronica.models import ArchivoCAF
            cafs = ArchivoCAF.objects.filter(
                empresa=request.empresa,
                estado='activo'
            ).select_related()

            caf_info = {}
            for caf in cafs:
                tipo_doc = caf.tipo_documento
                if tipo_doc not in caf_info:
                    caf_info[tipo_doc] = []
                caf_info[tipo_doc].append({
                    'id': caf.id,
                    'tipo_documento': caf.get_tipo_documento_display(),
                    'folio_desde': caf.folio_desde,
                    'folio_hasta': caf.folio_hasta,
                    'folio_actual': caf.folio_actual,
                    'folios_disponibles': caf.folios_disponibles(),
                    'fecha_autorizacion': caf.fecha_autorizacion.strftime('%d/%m/%Y') if caf.fecha_autorizacion else '',
                    'dias_para_vencer': caf.dias_para_vencer() if caf.fecha_autorizacion else 0,
                    'esta_vigente': caf.esta_vigente()
                })

            return JsonResponse({
                'success': True,
                'disponibilidad': disponibilidad,
                'caf_detalles': caf_info,
                'empresa': {
                    'nombre': request.empresa.nombre,
                    'facturacion_electronica': request.empresa.facturacion_electronica,
                    'ambiente_sii': request.empresa.get_ambiente_sii_display() if request.empresa.facturacion_electronica else None
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    else:
        # Si no es AJAX, redirigir a la lista de CAF
        return redirect('facturacion_electronica:caf_list')


# ========================================
# PROCESAMIENTO DE VENTAS
# ========================================

@login_required
@requiere_empresa
@permission_required('caja.add_ventaprocesada', raise_exception=True)
def procesar_venta_buscar(request):
    """Buscar ticket para procesar"""
    # Obtener apertura activa
    apertura_activa = None
    for caja in Caja.objects.filter(empresa=request.empresa, activo=True):
        apertura = caja.get_apertura_activa()
        if apertura:
            apertura_activa = apertura
            break
    
    # Si no hay caja abierta, preparar formulario de apertura
    mostrar_modal_apertura = False
    form_apertura = None
    if not apertura_activa:
        mostrar_modal_apertura = True
        form_apertura = AperturaCajaForm(empresa=request.empresa)
    
    # Buscar ticket
    if request.method == 'POST':
        numero_ticket = request.POST.get('numero_ticket', '').strip()
        
        if numero_ticket:
            try:
                ticket = Venta.objects.get(
                    empresa=request.empresa,
                    numero_venta=numero_ticket,
                    tipo_documento='vale',
                    estado='borrador'
                )
                return redirect('caja:procesar_venta', ticket_id=ticket.pk)
            except Venta.DoesNotExist:
                messages.error(request, f'No se encontró el ticket #{numero_ticket} o ya fue procesado.')
        else:
            messages.error(request, 'Debe ingresar un número de ticket.')
    
    # Obtener tickets pendientes del día
    hoy_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    hoy_fin = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    tickets_pendientes = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='vale',
        estado='borrador',
        fecha_creacion__gte=hoy_inicio,
        fecha_creacion__lte=hoy_fin
    ).select_related('cliente', 'vendedor').order_by('-fecha_creacion')
    
    context = {
        'apertura_activa': apertura_activa,
        'tickets_pendientes': tickets_pendientes,
        'mostrar_modal_apertura': mostrar_modal_apertura,
        'form_apertura': form_apertura,
    }
    return render(request, 'caja/procesar_venta_buscar.html', context)


@login_required
@requiere_empresa
@permission_required('caja.add_ventaprocesada', raise_exception=True)
def procesar_venta(request, ticket_id):
    """Procesar un ticket (preventa) y convertirlo en documento tributario"""
    empresa = request.empresa  # Definir empresa localmente para evitar errores
    ticket = get_object_or_404(Venta, pk=ticket_id, empresa=empresa, tipo_documento='vale')
    
    # Validar que no sea Cotización o Vale no facturable
    if ticket.tipo_documento in ['cotizacion', 'vale_no_facturable']:
        messages.error(request, 'Los tickets de tipo Cotización y Vale no son facturables.')
        return redirect('caja:apertura_list')
    
    # Verificar que el ticket no esté ya procesado
    if VentaProcesada.objects.filter(venta_preventa=ticket).exists():
        messages.warning(request, 'Este ticket ya ha sido procesado.')
        return redirect('caja:apertura_list')
    
    # Obtener apertura activa
    apertura_activa = None
    for caja in Caja.objects.filter(empresa=request.empresa, activo=True):
        apertura = caja.get_apertura_activa()
        if apertura:
            apertura_activa = apertura
            break
    
    # Si no hay caja abierta, preparar formulario de apertura
    mostrar_modal_apertura = False
    form_apertura = None
    if not apertura_activa:
        mostrar_modal_apertura = True
        form_apertura = AperturaCajaForm(empresa=request.empresa)
    
    # Inicializar form para GET o POST con errores
    form = ProcesarVentaForm(empresa=request.empresa, ticket=ticket, initial={'ticket_id': ticket.id})
    
    if request.method == 'POST':
        print("=" * 50)
        print("POST RECIBIDO - Procesar Venta")
        print(f"Ticket ID: {ticket_id}")
        print(f"POST data: {request.POST}")
        print("=" * 50)
        
        # Procesar múltiples formas de pago
        formas_pago_dict = {}
        total_pagado = 0
        
        # Extraer todas las formas de pago del POST
        contador = 1
        while f'forma_pago_{contador}' in request.POST:
            forma_pago_id = request.POST.get(f'forma_pago_{contador}')
            monto_pago = request.POST.get(f'monto_pago_{contador}')
            
            if forma_pago_id and monto_pago:
                try:
                    monto = float(monto_pago)
                    if monto > 0:
                        formas_pago_dict[contador] = {
                            'forma_pago_id': forma_pago_id,
                            'monto': monto,
                            'numero_cheque': request.POST.get(f'numero_cheque_{contador}', ''),
                            'banco': request.POST.get(f'banco_{contador}', ''),
                            'fecha_cheque': request.POST.get(f'fecha_cheque_{contador}', None),
                        }
                        total_pagado += monto
                except ValueError:
                    pass
            contador += 1
        
        print(f"Formas de pago extraidas: {len(formas_pago_dict)}")
        print(f"Total pagado: ${total_pagado:,.0f}")
        print(f"Total ticket: ${float(ticket.total):,.0f}")
        
        # Convertir ticket.total a float para comparación precisa
        total_ticket = float(ticket.total)
        
        # Validar que hay al menos una forma de pago
        if not formas_pago_dict:
            print("ERROR: No hay formas de pago")
            messages.error(request, 'Debe ingresar al menos una forma de pago.')
        # Validar que el total pagado sea suficiente (sin tolerancia, debe ser exacto o mayor)
        elif total_pagado < total_ticket:
            print(f"ERROR: Total pagado insuficiente (diferencia: ${total_ticket - total_pagado:,.2f})")
            messages.error(request, f'El monto pagado (${total_pagado:,.0f}) es MENOR al total del documento (${total_ticket:,.0f}). Faltan ${(total_ticket - total_pagado):,.0f}.')
        else:
            print("Validaciones OK, procesando venta...")
            # Procesar venta
            tipo_documento = request.POST.get('tipo_documento')
            observaciones = request.POST.get('observaciones', '')
            
            print(f"Tipo documento: {tipo_documento}")
            print(f"Observaciones: {observaciones}")
            
            # VALIDAR FOLIOS DISPONIBLES ANTES DE CREAR LA VENTA
            if request.empresa.facturacion_electronica and tipo_documento in ['factura', 'boleta']:
                try:
                    from facturacion_electronica.services import DTEService
                    print(f"Verificando disponibilidad de folios para {tipo_documento}...")
                    
                    folios_disponibles = DTEService.verificar_disponibilidad_folios(request.empresa)
                    
                    if not folios_disponibles.get(tipo_documento, {}).get('disponible', False):
                        print(f"ERROR: No hay folios disponibles para {tipo_documento}")
                        tipo_doc_nombre = 'Factura' if tipo_documento == 'factura' else 'Boleta'
                        messages.error(request, f'No se puede procesar la venta: No hay folios CAF disponibles para {tipo_doc_nombre}. Debe cargar folios antes de continuar.')
                        # Retornar al formulario sin procesar
                        return render(request, 'caja/procesar_venta.html', {
                            'ticket': ticket,
                            'form': form,
                            'apertura_activa': apertura_activa,
                        })
                    
                    print(f"Folios disponibles OK para {tipo_documento}")
                    
                except Exception as e:
                    print(f"ERROR al verificar folios: {str(e)}")
                    messages.error(request, f'Error al verificar disponibilidad de folios: {str(e)}')
                    return render(request, 'caja/procesar_venta.html', {
                        'ticket': ticket,
                        'form': form,
                        'apertura_activa': apertura_activa,
                    })

            # Generar número FUERA de la transacción para evitar condiciones de carrera
            print(f"Generando número para {tipo_documento}...")
            
            # Buscar el número más alto existente para este tipo de documento
            ventas_existentes = Venta.objects.filter(
                empresa=request.empresa,
                tipo_documento=tipo_documento
            ).order_by('-numero_venta')
            
            # Iniciar desde 1
            numero = 1
            
            # Si hay ventas existentes, obtener el número más alto y sumar 1
            if ventas_existentes.exists():
                for venta in ventas_existentes[:20]:  # Revisar últimas 20
                    try:
                        num_actual = int(venta.numero_venta)
                        if num_actual >= numero:
                            numero = num_actual + 1
                    except ValueError:
                        continue
                print(f"   Número base calculado: {numero}")
            
            # Buscar un número disponible
            numero_venta = f"{numero:06d}"
            max_intentos = 1000
            
            for intento in range(max_intentos):
                if not Venta.objects.filter(
                    empresa=request.empresa,
                    tipo_documento=tipo_documento,
                    numero_venta=numero_venta
                ).exists():
                    break
                print(f"   #{numero_venta} existe, probando siguiente...")
                numero += 1
                numero_venta = f"{numero:06d}"
            
            print(f"   Numero generado: {numero_venta}")
            
            # Ahora crear la venta dentro de una transacción con manejo de IntegrityError
            max_reintentos = 5
            venta_creada_exitosamente = False
            
            for reintento in range(max_reintentos):
                try:
                    with transaction.atomic():
                        print(f"Iniciando transaccion atomica (intento {reintento + 1})...")
                        
                        # Usar la primera forma de pago como principal (para compatibilidad)
                        print(f"Obteniendo forma de pago ID: {formas_pago_dict[1]['forma_pago_id']}")
                        primera_forma_pago = FormaPago.objects.get(pk=formas_pago_dict[1]['forma_pago_id'])
                        print(f"   Forma de pago: {primera_forma_pago.nombre}")

                        # Crear venta final
                        print(f"Creando venta {tipo_documento} #{numero_venta}...")
                        venta_final = Venta.objects.create(
                        empresa=request.empresa,
                        numero_venta=numero_venta,
                        cliente=ticket.cliente,
                        vendedor=ticket.vendedor,
                        forma_pago=primera_forma_pago,
                        estacion_trabajo=ticket.estacion_trabajo,
                        tipo_documento=tipo_documento,
                        subtotal=ticket.subtotal,
                        descuento=ticket.descuento,
                        neto=ticket.neto,
                        iva=ticket.iva,
                        impuesto_especifico=ticket.impuesto_especifico,
                        total=ticket.total,
                        estado='confirmada',
                        usuario_creacion=request.user,
                        observaciones=f"Ticket #{ticket.numero_venta}. {observaciones}"
                    )
                    print(f"Venta creada: ID={venta_final.id}")

                    # Copiar detalles
                    detalles_count = ticket.ventadetalle_set.count()
                    print(f"Copiando {detalles_count} detalles...")
                    for detalle_ticket in ticket.ventadetalle_set.all():
                        VentaDetalle.objects.create(
                            venta=venta_final,
                            articulo=detalle_ticket.articulo,
                            cantidad=detalle_ticket.cantidad,
                            precio_unitario=detalle_ticket.precio_unitario,
                            precio_total=detalle_ticket.precio_total,
                            impuesto_especifico=detalle_ticket.impuesto_especifico
                        )
                    
                    # Registrar movimientos de caja (uno por cada forma de pago)
                    for idx, datos_pago in formas_pago_dict.items():
                        forma_pago = FormaPago.objects.get(pk=datos_pago['forma_pago_id'])
                        
                        descripcion = f"{venta_final.get_tipo_documento_display()} #{venta_final.numero_venta}"
                        if len(formas_pago_dict) > 1:
                            descripcion += f" (Pago {idx}/{len(formas_pago_dict)})"
                        
                        MovimientoCaja.objects.create(
                            apertura_caja=apertura_activa,
                            venta=venta_final,
                            tipo='venta',
                            forma_pago=forma_pago,
                            monto=datos_pago['monto'],
                            descripcion=descripcion,
                            usuario=request.user,
                            numero_cheque=datos_pago['numero_cheque'],
                            banco=datos_pago['banco'],
                            fecha_cheque=datos_pago['fecha_cheque'] if datos_pago['fecha_cheque'] else None
                        )
                    
                    # Calcular cambio
                    monto_cambio = total_pagado - float(ticket.total) if total_pagado > float(ticket.total) else 0
                    
                    # Crear registro de venta procesada (usar primer movimiento como referencia)
                    primer_movimiento = MovimientoCaja.objects.filter(
                        venta=venta_final
                    ).first()
                    
                    venta_procesada = VentaProcesada.objects.create(
                        venta_preventa=ticket,
                        venta_final=venta_final,
                        apertura_caja=apertura_activa,
                        movimiento_caja=primer_movimiento,
                        usuario_proceso=request.user,
                        monto_recibido=Decimal(str(total_pagado)),
                        monto_cambio=Decimal(str(monto_cambio)),
                        observaciones=observaciones
                    )
                    
                    # Descontar stock
                    if apertura_activa.caja.bodega:
                        descontar_stock_venta(venta_final, apertura_activa.caja.bodega)
                        venta_procesada.stock_descontado = True
                    
                    # Actualizar cuenta corriente si alguna forma de pago es crédito
                    for idx, datos_pago in formas_pago_dict.items():
                        forma_pago = FormaPago.objects.get(pk=datos_pago['forma_pago_id'])
                        if forma_pago.es_cuenta_corriente and ticket.cliente:
                            actualizar_cuenta_corriente_cliente(venta_final, ticket.cliente)
                            venta_procesada.cuenta_corriente_actualizada = True
                            break
                    
                    venta_procesada.save()

                    # GENERAR DTE SI FE ESTÁ ACTIVADA Y TIPO DE DOCUMENTO ES FACTURABLE
                    if request.empresa.facturacion_electronica and tipo_documento in ['factura', 'boleta']:
                        try:
                            from facturacion_electronica.services import DTEService
                            print(f"Generando DTE para {tipo_documento} #{numero_venta}...")

                            dte = DTEService.crear_dte_desde_venta(venta_final)
                            if dte:
                                print(f"DTE generado exitosamente:")
                                print(f"   Tipo: {dte.get_tipo_documento_display()} (Código: {dte.tipo_documento})")
                                print(f"   Folio: {dte.folio}")
                                print(f"   CAF: {dte.caf.folio_desde}-{dte.caf.folio_hasta}")
                                print(f"   Empresa: {dte.empresa.nombre}")
                                print(f"   Cliente: {dte.razon_social_receptor}")
                                print(f"   Monto: ${dte.monto_total}")

                                # Mensaje específico según el tipo de documento
                                if tipo_documento == 'boleta':
                                    mensaje_dte = f'Boleta Electronica N° {dte.folio} generada correctamente.'
                                else:
                                    mensaje_dte = f'Factura Electronica N° {dte.folio} generada correctamente.'

                                messages.success(request, mensaje_dte)

                                # Agregar información del DTE a la venta procesada
                                venta_procesada.dte_generado = dte
                                venta_procesada.save()

                            else:
                                print(f"No se pudo generar DTE - No hay folios disponibles para {tipo_documento}")
                                # Verificar disponibilidad de folios
                                tipo_doc_sii = DTEService.mapear_tipo_documento(tipo_documento)
                                folios_disponibles = DTEService.verificar_disponibilidad_folios(request.empresa)

                                if not folios_disponibles.get(tipo_documento, {}).get('disponible', False):
                                    messages.error(request, f'No se puede generar {tipo_documento}: No hay folios CAF disponibles para este tipo de documento.')
                                else:
                                    messages.warning(request, f'Error inesperado al generar {tipo_documento}. Verifique la configuración de facturación electrónica.')

                        except Exception as e:
                            print(f"ERROR al generar DTE: {str(e)}")
                            import traceback
                            traceback.print_exc()

                            # Mensaje más específico según el error
                            if "No hay folios disponibles" in str(e):
                                messages.error(request, f'No se puede generar {tipo_documento}: No hay folios CAF disponibles.')
                            elif "certificado" in str(e).lower():
                                messages.error(request, f'Error con certificado digital: {str(e)}')
                            else:
                                messages.warning(request, f'Error al generar {tipo_documento}: {str(e)}. Puede procesar la venta sin DTE.')
                    
                    # Actualizar estado del ticket
                    ticket.estado = 'confirmada'
                    ticket.save()
                    
                    # Recalcular totales de la apertura
                    apertura_activa.calcular_totales()
                    
                    # Mensaje de éxito con detalle de pagos
                    mensaje = f'{venta_final.get_tipo_documento_display()} #{venta_final.numero_venta} generada exitosamente.'
                    if len(formas_pago_dict) > 1:
                        mensaje += f' Pagado con {len(formas_pago_dict)} formas de pago.'
                    
                        print(f"Exito: {mensaje}")
                        messages.success(request, mensaje)
                        
                        if monto_cambio > 0:
                            messages.info(request, f'Cambio a entregar: ${monto_cambio:,.0f}')
                        
                        print(f"🖨️ Redirigiendo a impresión: /ventas/{venta_final.pk}/html/")

                    # Si llegamos aquí, la venta fue creada exitosamente
                    # Redirigir a impresión del documento
                    return redirect('ventas:venta_html', pk=venta_final.pk)
                
                except IntegrityError as e:
                    if 'UNIQUE constraint failed' in str(e) and 'numero_venta' in str(e):
                        print(f"Numero {numero_venta} ya existe (IntegrityError), incrementando...")
                        # Incrementar el número y reintentar
                        numero += 1
                        numero_venta = f"{numero:06d}"
                        print(f"   Nuevo numero: {numero_venta}")
                        if reintento == max_reintentos - 1:
                            raise Exception(f"No se pudo generar un número único después de {max_reintentos} intentos")
                        continue
                    else:
                        # Otro tipo de IntegrityError
                        raise
                
                except Exception as e:
                    print(f"💥 ERROR en intento {reintento + 1}: {type(e).__name__}: {str(e)}")
                    raise
            
            # Si llegamos aquí sin éxito, mostrar error
            if not venta_creada_exitosamente:
                print(f"💥 ERROR EN EXCEPCIÓN: {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Error al procesar la venta: {str(e)}')
    
    # Obtener detalles del ticket
    detalles = ticket.ventadetalle_set.all().select_related('articulo')
    
    # Verificar disponibilidad de folios si FE está activa
    disponibilidad_folios = None
    if empresa.facturacion_electronica:
        try:
            from facturacion_electronica.services import DTEService
            disponibilidad_folios = DTEService.verificar_disponibilidad_folios(empresa)
        except Exception as e:
            print(f"Error al verificar folios: {e}")
            disponibilidad_folios = {}

    context = {
        'form': form,
        'ticket': ticket,
        'empresa': request.empresa,  # Usar request.empresa para el contexto
        'detalles': detalles,
        'apertura_activa': apertura_activa,
        'disponibilidad_folios': disponibilidad_folios,
        'disponibilidad_folios_json': disponibilidad_folios,  # Para JavaScript
        'tipo_documento_planeado': ticket.tipo_documento_planeado,  # ← TIPO PLANEADO
        'title': f'Procesar Ticket #{ticket.numero_venta}',
        'mostrar_modal_apertura': mostrar_modal_apertura,
        'form_apertura': form_apertura,
    }
    return render(request, 'caja/procesar_venta.html', context)


# ========================================
# FUNCIONES AUXILIARES
# ========================================

def descontar_stock_venta(venta, bodega):
    """Descuenta el stock de los artículos vendidos"""
    for detalle in venta.ventadetalle_set.all():
        try:
            stock = Stock.objects.get(
                empresa=venta.empresa,
                bodega=bodega,
                articulo=detalle.articulo
            )
            
            if stock.cantidad >= detalle.cantidad:
                stock.cantidad -= detalle.cantidad
                stock.save()
            else:
                # Si no hay suficiente stock, descontar lo que haya
                stock.cantidad = Decimal('0.00')
                stock.save()
        except Stock.DoesNotExist:
            # Si no existe el stock, crearlo con cantidad 0
            Stock.objects.create(
                empresa=venta.empresa,
                bodega=bodega,
                articulo=detalle.articulo,
                cantidad=Decimal('0.00'),
                precio_promedio=detalle.precio_unitario
            )


def actualizar_cuenta_corriente_cliente(venta, cliente):
    """Actualiza la cuenta corriente del cliente con la venta a crédito"""
    try:
        from tesoreria.models import CuentaCorrienteCliente, MovimientoCuentaCorrienteCliente, DocumentoCliente
        from datetime import timedelta

        # Obtener o crear la cuenta corriente del cliente
        cuenta_corriente, created = CuentaCorrienteCliente.objects.get_or_create(
            empresa=venta.empresa,
            cliente=cliente,
            defaults={
                'limite_credito': 100000,  # Límite por defecto
                'dias_credito': 30  # 30 días por defecto
            }
        )

        if created:
            print(f"✓ Nueva cuenta corriente creada para {cliente.nombre}")

        # Crear o actualizar DocumentoCliente
        documento, doc_created = DocumentoCliente.objects.get_or_create(
            empresa=venta.empresa,
            numero_documento=venta.numero_venta,
            tipo_documento='factura' if venta.tipo_documento == 'factura' else 'boleta',
            defaults={
                'cliente': cliente,
                'fecha_emision': venta.fecha,
                'fecha_vencimiento': venta.fecha + timedelta(days=cuenta_corriente.dias_credito),
                'total': int(venta.total),
                'monto_pagado': 0,
                'saldo_pendiente': venta.total,
                'estado_pago': 'pendiente',
                'creado_por': venta.usuario_creacion
            }
        )
        
        if doc_created:
            print(f"✓ Documento creado: {documento.tipo_documento} {documento.numero_documento}")

        # Registrar el movimiento
        saldo_anterior = cuenta_corriente.saldo_total

        movimiento = MovimientoCuentaCorrienteCliente.objects.create(
            cuenta_corriente=cuenta_corriente,
            venta=venta,
            tipo_movimiento='debe',  # El cliente debe pagar
            monto=venta.total,
            saldo_anterior=saldo_anterior,
            saldo_nuevo=saldo_anterior + venta.total,
            estado='confirmado',
            registrado_por=venta.usuario_creacion
        )

        # Actualizar saldos de la cuenta corriente
        cuenta_corriente.saldo_total += venta.total
        cuenta_corriente.saldo_pendiente += venta.total
        cuenta_corriente.save()

        # Actualizar la venta con la cuenta corriente
        venta.observaciones += f"\n[CRÉDITO] Registrado en cuenta corriente - Movimiento #{movimiento.id}"
        venta.save()

        print(f"✓ Venta a crédito registrada: {cliente.nombre} - ${venta.total} - Movimiento #{movimiento.id}")

        return True

    except Exception as e:
        print(f"❌ Error al registrar venta a crédito: {e}")
        # Fallback: registrar en observaciones
        try:
            venta.observaciones += f"\n[CRÉDITO ERROR] No se pudo registrar en cuenta corriente: {str(e)} - Total: ${venta.total}"
            venta.save()
        except:
            pass
        return False


# ========================================
# MOVIMIENTOS MANUALES
# ========================================

@login_required
@requiere_empresa
@permission_required('caja.add_movimientocaja', raise_exception=True)
def movimiento_create(request, apertura_id):
    """Registrar movimiento manual (retiro/ingreso)"""
    apertura = get_object_or_404(AperturaCaja, pk=apertura_id, caja__empresa=request.empresa)
    
    if apertura.estado == 'cerrada':
        messages.warning(request, 'No se pueden registrar movimientos en una caja cerrada.')
        return redirect('caja:apertura_detail', pk=apertura.pk)
    
    if request.method == 'POST':
        form = MovimientoCajaForm(request.POST)
        if form.is_valid():
            movimiento = form.save(commit=False)
            movimiento.apertura_caja = apertura
            movimiento.usuario = request.user
            movimiento.save()
            
            # Recalcular totales
            apertura.calcular_totales()
            
            messages.success(request, 'Movimiento registrado exitosamente.')
            return redirect('caja:apertura_detail', pk=apertura.pk)
    else:
        form = MovimientoCajaForm()
    
    context = {
        'form': form,
        'apertura': apertura,
        'title': 'Registrar Movimiento',
    }
    return render(request, 'caja/movimiento_form.html', context)
