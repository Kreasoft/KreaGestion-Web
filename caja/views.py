from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction, IntegrityError, models
from django.utils import timezone
from decimal import Decimal
from datetime import datetime
import json

from core.decorators import requiere_empresa, requiere_permiso
from .models import Caja, AperturaCaja, MovimientoCaja, VentaProcesada
from .forms import CajaForm, AperturaCajaForm, CierreCajaForm, ProcesarVentaForm, MovimientoCajaForm
from ventas.models import Venta, VentaDetalle, FormaPago
from inventario.models import Stock, Inventario
from facturacion_electronica.dte_generator import DTEXMLGenerator
from facturacion_electronica.firma_electronica import FirmadorDTE
from facturacion_electronica.pdf417_generator import PDF417Generator
from facturacion_electronica.models import DocumentoTributarioElectronico
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
    
    # Obtener movimientos manuales (ingresos/egresos) - siempre, incluso en POST
    movimientos_manuales = MovimientoCaja.objects.filter(
        apertura_caja=apertura,
        tipo__in=['ingreso', 'retiro']
    ).select_related('usuario', 'forma_pago').order_by('-fecha')
    
    # Calcular totales de movimientos manuales
    total_ingresos = sum(m.monto for m in movimientos_manuales.filter(tipo='ingreso')) or Decimal('0.00')
    total_egresos = sum(m.monto for m in movimientos_manuales.filter(tipo='retiro')) or Decimal('0.00')
    
    context = {
        'form': form,
        'apertura': apertura,
        'title': f'Cerrar Caja {apertura.caja.nombre}',
        'movimientos_manuales': movimientos_manuales,
        'total_ingresos': total_ingresos,
        'total_egresos': total_egresos,
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
    
    # Obtener ventas procesadas durante esta apertura (excluyendo guías y cotizaciones)
    ventas = VentaProcesada.objects.filter(
        apertura_caja=apertura
    ).exclude(
        venta_final__tipo_documento__in=['guia', 'cotizacion']
    ).select_related('venta_preventa', 'venta_final', 'usuario_proceso').order_by('fecha_proceso')
    
    # Agrupar ventas por forma de pago
    ventas_por_forma_pago = {}
    for venta_proc in ventas:
        venta_final = venta_proc.venta_final
        
        #movimiento = venta_proc.movimiento_caja

        mov = venta_proc.movimiento_caja

        if mov and mov.forma_pago:
            forma_pago_nombre = mov.forma_pago.nombre
        elif mov:
            forma_pago_nombre = 'Movimiento sin forma de pago'
        else:
            forma_pago_nombre = 'Sin movimiento de caja'
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
    #movimientos = MovimientoCaja.objects.filter(
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

            # Obtener detalles de CAFs que estén activos, vigentes y con folios disponibles
            from facturacion_electronica.models import ArchivoCAF
            from django.db.models import F
            
            cafs = ArchivoCAF.objects.filter(
                empresa=request.empresa,
                estado='activo',
                folios_utilizados__lt=F('cantidad_folios')
            ).select_related()

            # Filtrar por vigencia en Python para asegurar la lógica correcta
            cafs = [caf for caf in cafs if caf.esta_vigente()]

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
@requiere_permiso('caja.add_ventaprocesada', mensaje='No tienes permisos para procesar ventas. Contacta al administrador.', redirect_url='caja:apertura_list')
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
@requiere_permiso('caja.add_ventaprocesada', mensaje='No tienes permisos para procesar ventas. Contacta al administrador.', redirect_url='caja:apertura_list')
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
        
        # Obtener tipo de documento (fallback al planeado o boleta)
        tipo_documento = request.POST.get('tipo_documento') or ticket.tipo_documento_planeado or 'boleta'
        print(f"[DEBUG] Tipo documento: {tipo_documento}")
        
        # Obtener vendedor seleccionado
        vendedor_id = request.POST.get('vendedor_id')
        if vendedor_id:
            from ventas.models import Vendedor
            try:
                vendedor_seleccionado = Vendedor.objects.get(id=vendedor_id, empresa=request.empresa)
                print(f"[DEBUG] Vendedor seleccionado: {vendedor_seleccionado.nombre}")
            except Vendedor.DoesNotExist:
                vendedor_seleccionado = ticket.vendedor
                print(f"[DEBUG] Vendedor no encontrado, usando del ticket: {vendedor_seleccionado.nombre}")
        else:
            vendedor_seleccionado = ticket.vendedor
            print(f"[DEBUG] Sin vendedor en POST, usando del ticket: {vendedor_seleccionado.nombre}")
        
        # Obtener vehículo y chofer si el sistema de despacho está activo
        vehiculo_seleccionado = ticket.vehiculo
        chofer_seleccionado = ticket.chofer
        
        print(f"[DEBUG] Sistema de despacho activo: {request.empresa.usa_sistema_despacho}")
        if request.empresa.usa_sistema_despacho:
            vehiculo_id = request.POST.get('vehiculo_id', '').strip()
            chofer_id = request.POST.get('chofer_id', '').strip()
            print(f"[DEBUG] Vehiculo ID recibido: '{vehiculo_id}' (tipo: {type(vehiculo_id)})")
            print(f"[DEBUG] Chofer ID recibido: '{chofer_id}' (tipo: {type(chofer_id)})")
            
            # Verificar si hay vehículos y choferes disponibles
            try:
                from pedidos.models_transporte import Vehiculo, Chofer
                vehiculos_disponibles = Vehiculo.objects.filter(empresa=request.empresa, activo=True).exists()
                choferes_disponibles = Chofer.objects.filter(empresa=request.empresa, activo=True).exists()
                print(f"[DEBUG] Vehículos disponibles: {vehiculos_disponibles}, Choferes disponibles: {choferes_disponibles}")
            except:
                vehiculos_disponibles = False
                choferes_disponibles = False
            
            # Validar que se hayan seleccionado SOLO PARA FACTURAS (opcional para guias y boletas)
            # Solo validar si hay vehículos/choferes disponibles en el sistema
            if tipo_documento == 'factura' and vehiculos_disponibles and choferes_disponibles and (not vehiculo_id or not chofer_id):
                print(f"[ERROR] Validación fallida: Factura requiere vehículo y chofer. Vehiculo: '{vehiculo_id}', Chofer: '{chofer_id}'")
                messages.error(request, 'Debe seleccionar movil y chofer para procesar facturas.')
                form = ProcesarVentaForm(empresa=request.empresa, ticket=ticket, initial={'ticket_id': ticket.id})
                from ventas.models import Vendedor
                vendedores = Vendedor.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
                try:
                    from pedidos.models_transporte import Vehiculo, Chofer
                    vehiculos = Vehiculo.objects.filter(empresa=request.empresa, activo=True).order_by('patente')
                    choferes = Chofer.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
                except:
                    vehiculos = []
                    choferes = []
                print("[DEBUG] Retornando formulario con error de validación")
                return render(request, 'caja/procesar_venta.html', {
                    'ticket': ticket,
                    'form': form,
                    'apertura_activa': apertura_activa,
                    'empresa': request.empresa,
                    'vendedores': vendedores,
                    'vehiculos': vehiculos,
                    'choferes': choferes
                })
            elif tipo_documento == 'factura' and (not vehiculos_disponibles or not choferes_disponibles):
                print(f"[WARN] Sistema de despacho activo pero no hay vehículos/choferes disponibles. Continuando sin validación.")
                # No validar si no hay vehículos/choferes disponibles
            
            # Obtener objetos de vehículo y chofer solo si se proporcionaron
            print(f"[DEBUG] Validando vehículo y chofer: vehiculo_id='{vehiculo_id}', chofer_id='{chofer_id}'")
            if vehiculo_id and chofer_id:
                try:
                    from pedidos.models_transporte import Vehiculo, Chofer
                    vehiculo_seleccionado = Vehiculo.objects.get(id=vehiculo_id, empresa=request.empresa)
                    chofer_seleccionado = Chofer.objects.get(id=chofer_id, empresa=request.empresa)
                    print(f"[OK] Sistema de despacho: Vehiculo {vehiculo_seleccionado.patente}, Chofer {chofer_seleccionado.nombre}")
                except Exception as e:
                    print(f"[WARN] Error al obtener vehiculo/chofer: {e}")
                    # No mostrar error si son opcionales (guias/boletas)
                    if tipo_documento == 'factura':
                        messages.error(request, f'Error al obtener datos de despacho: {e}')
            else:
                print("[INFO] Sin datos de despacho (opcional para guias/boletas)")
        else:
            print("[DEBUG] Sistema de despacho NO activo, saltando validación de vehículo/chofer")
        
        # Las guías de despacho NO requieren pago (son documentos de traslado)
        print(f"[DEBUG] Validando tipo documento: {tipo_documento}")
        if tipo_documento == 'guia':
            print("Tipo documento: GUÍA - No requiere validación de pago")
            # Las guías se procesan sin pago
            formas_pago_dict = {}  # Sin formas de pago
            total_pagado = 0
        
        # Validar pagos solo para documentos que NO sean guías
        validacion_pagos_ok = True
        if tipo_documento != 'guia':
            print(f"[DEBUG] Validando pagos para {tipo_documento}...")
            # Validar que hay al menos una forma de pago
            if not formas_pago_dict:
                print("ERROR: No hay formas de pago")
                messages.error(request, 'Debe ingresar al menos una forma de pago.')
                validacion_pagos_ok = False
            # Validar que el total pagado sea suficiente (sin tolerancia, debe ser exacto o mayor)
            elif total_pagado < total_ticket:
                print(f"ERROR: Total pagado insuficiente (diferencia: ${total_ticket - total_pagado:,.2f})")
                messages.error(request, f'El monto pagado (${total_pagado:,.0f}) es MENOR al total del documento (${total_ticket:,.0f}). Faltan ${(total_ticket - total_pagado):,.0f}.')
                validacion_pagos_ok = False
            else:
                print(f"[DEBUG] Validación de pagos OK: ${total_pagado:,.0f} >= ${total_ticket:,.0f}")
        
        # Si hay errores de validación, retornar el formulario con los errores
        if not validacion_pagos_ok:
            print("[DEBUG] Errores de validación detectados, retornando formulario...")
            from ventas.models import Vendedor
            vendedores = Vendedor.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
            try:
                from pedidos.models_transporte import Vehiculo, Chofer
                vehiculos = Vehiculo.objects.filter(empresa=request.empresa, activo=True).order_by('patente')
                choferes = Chofer.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
            except:
                vehiculos = []
                choferes = []
            return render(request, 'caja/procesar_venta.html', {
                'ticket': ticket,
                'form': form,
                'apertura_activa': apertura_activa,
                'empresa': request.empresa,
                'vendedores': vendedores,
                'vehiculos': vehiculos,
                'choferes': choferes
            })
        
        # Procesar si es guía O si las validaciones de pago pasaron
        print(f"[DEBUG] Evaluando si procesar: tipo_documento='{tipo_documento}', es_guia={tipo_documento == 'guia'}, formas_pago={bool(formas_pago_dict)}, total_pagado={total_pagado}, total_ticket={total_ticket}")
        if tipo_documento == 'guia' or (formas_pago_dict and total_pagado >= total_ticket):
            print("Validaciones OK, procesando venta...")
            # Procesar venta
            tipo_documento = tipo_documento
            observaciones = request.POST.get('observaciones', '')
            
            print(f"Tipo documento: {tipo_documento}")
            print(f"Observaciones: {observaciones}")
            
            # PRECHEQUEOS FE: Para boleta/factura/guía, exigir FE activa y certificado antes de continuar
            if tipo_documento in ['factura', 'boleta', 'guia']:
                print("[DEBUG] VERIFICANDO CONFIGURACION FE...")
                fe_activa = getattr(request.empresa, 'facturacion_electronica', False)
                print(f"   FE Activa: {fe_activa}")
                cert_ok = hasattr(request.empresa, 'certificado_digital') and bool(getattr(request.empresa, 'certificado_digital'))
                print(f"   Certificado OK: {cert_ok}")
                
                if not fe_activa:
                    print("[ERROR] FE NO ACTIVA - Devolviendo error")
                    messages.error(request, 'La empresa no tiene Facturacion Electronica activada. No se puede emitir DTE.')
                    return render(request, 'caja/procesar_venta.html', {
                        'ticket': ticket,
                        'form': form,
                        'apertura_activa': apertura_activa,
                    })
                if not cert_ok:
                    print("[ERROR] CERTIFICADO NO CONFIGURADO - Devolviendo error")
                    messages.error(request, 'No hay certificado digital configurado para la empresa. Configure el certificado para emitir DTE.')
                    return render(request, 'caja/procesar_venta.html', {
                        'ticket': ticket,
                        'form': form,
                        'apertura_activa': apertura_activa,
                    })

                # Validar contraseña/certificado ANTES de continuar
                # TEMPORALMENTE DESHABILITADO PARA TESTING
                print("[WARN] VALIDACION DE CERTIFICADO DESHABILITADA (MODO TESTING)")
                print("   Para habilitar, corrige la contraseña del certificado en la configuracion de la empresa")
                
                # DESCOMENTAR CUANDO TENGAS LA CONTRASEÑA CORRECTA:
                # print("[DEBUG] VALIDANDO CERTIFICADO DIGITAL...")
                # try:
                #     from facturacion_electronica.firma_electronica import FirmadorDTE
                #     print("   Importando FirmadorDTE... OK")
                #     print(f"   Certificado path: {request.empresa.certificado_digital.path}")
                #     print("   Creando instancia FirmadorDTE...")
                #     firmador = FirmadorDTE(request.empresa.certificado_digital.path, request.empresa.password_certificado or '')
                #     print("   [OK] Certificado validado correctamente")
                # except ValueError as e_cert:
                #     print(f"[ERROR] ERROR AL VALIDAR CERTIFICADO: {e_cert}")
                #     messages.error(
                #         request,
                #         f'Certificado digital rechazado: {e_cert}. No se puede procesar la venta hasta corregirlo.'
                #     )
                #     return render(request, 'caja/procesar_venta.html', {
                #         'ticket': ticket,
                #         'form': form,
                #         'apertura_activa': apertura_activa,
                #     })
                # except Exception as e_cert_general:
                #     print(f"[ERROR] ERROR INESPERADO AL VALIDAR CERTIFICADO: {type(e_cert_general).__name__}: {e_cert_general}")
                #     import traceback
                #     traceback.print_exc()
                #     messages.error(
                #         request,
                #         f'Error al validar certificado: {e_cert_general}'
                #     )
                #     return render(request, 'caja/procesar_venta.html', {
                #         'ticket': ticket,
                #         'form': form,
                #         'apertura_activa': apertura_activa,
                #     })
            
            print("[OK] PRECHEQUEOS COMPLETADOS - Continuando...")

            # VALIDAR FOLIOS DISPONIBLES Y OBTENER FOLIO DEL CAF
            folio_caf = None
            if tipo_documento in ['factura', 'boleta', 'guia']:
                try:
                    from facturacion_electronica.models import ArchivoCAF
                    
                    # Mapear tipo de documento a código SII
                    tipo_dte_map = {
                        'factura': '33',
                        'boleta': '39',
                        'guia': '52',
                    }
                    tipo_dte = tipo_dte_map.get(tipo_documento)
                    
                    print(f"Buscando CAF para {tipo_documento} (tipo DTE: {tipo_dte})...")
                    
                    # Buscar CAF disponible y con folios (la vigencia se valida después para debug)
                    caf = ArchivoCAF.objects.filter(
                        empresa=request.empresa,
                        tipo_documento=tipo_dte,
                        estado='activo',
                        folios_utilizados__lt=models.F('cantidad_folios')  # Folios disponibles
                    ).order_by('fecha_autorizacion').first() # Usar el más antiguo primero

                    # --- DEBUG VIGENCIA ---
                    if caf:
                        print(f"DEBUG - CAF encontrado (ID: {caf.id}). Verificando vigencia en Python...")
                        esta_vigente = caf.esta_vigente()
                        print(f"DEBUG - caf.esta_vigente() retorna: {esta_vigente}")
                        if not esta_vigente:
                            print("DEBUG - El CAF encontrado NO está vigente según el método del modelo. Se descarta.")
                            caf = None # Descartar CAF si no está vigente
                    # --- FIN DEBUG ---
                    
                    # --- INICIO DEBUG FOLIOS ---
                    print("="*80)
                    print("DEBUG: Verificación de Folios CAF")
                    print(f"  - Empresa: {request.empresa.nombre} (ID: {request.empresa.id})")
                    print(f"  - Sucursal Activa: {getattr(request, 'sucursal_activa', 'N/A')}")
                    print(f"  - Tipo Documento Buscado (DTE): {tipo_dte}")

                    # Listar TODOS los CAFs para esta EMPRESA para ver qué hay en la BD
                    todos_caf_empresa = ArchivoCAF.objects.filter(empresa=request.empresa)
                    print(f"  - Total CAFs en esta EMPRESA: {todos_caf_empresa.count()}")
                    for c in todos_caf_empresa:
                        print(f"    -> CAF ID {c.id}: Tipo {c.tipo_documento}, Estado '{c.estado}', Folios Disp: {c.folios_disponibles()}, Vigente: {c.esta_vigente()}")

                    # Resultado de la búsqueda específica
                    print(f"  - Búsqueda específica: empresa={request.empresa.id}, tipo_documento='{tipo_dte}', estado='activo'")
                    if caf:
                        print(f"  - RESULTADO: ENCONTRADO -> CAF ID {caf.id} con {caf.folios_disponibles()} folios disponibles.")
                    else:
                        print("  - RESULTADO: NO ENCONTRADO.")
                    print("="*80)
                    # --- FIN DEBUG FOLIOS ---
                    
                    if not caf:
                        tipo_doc_nombre = {'factura': 'Factura', 'boleta': 'Boleta', 'guia': 'Guía de Despacho'}[tipo_documento]
                        messages.error(request, f'No se puede procesar: No hay folios CAF disponibles para {tipo_doc_nombre}. Debe cargar folios antes de continuar.')
                        return render(request, 'caja/procesar_venta.html', {
                            'ticket': ticket,
                            'form': form,
                            'apertura_activa': apertura_activa,
                        })
                    
                    # Verificar vigencia
                    if not caf.esta_vigente():
                        messages.error(request, f'El CAF de {tipo_documento} ha vencido. Debe cargar un nuevo CAF.')
                        return render(request, 'caja/procesar_venta.html', {
                            'ticket': ticket,
                            'form': form,
                            'apertura_activa': apertura_activa,
                        })
                    
                    # Verificar si hay folios disponibles (sin consumir)
                    if caf.folios_disponibles() <= 0:
                        raise ValueError("El CAF seleccionado no tiene folios disponibles.")
                    
                    # El folio se obtendrá y consumirá dentro del DTEService para asegurar atomicidad
                    folio_caf = caf.folio_actual + 1 # Simular para la lógica que sigue
                    print(f"[OK] Verificacion de folios OK. Proximo folio a usar: {folio_caf}")
                    
                except Exception as e:
                    print(f"ERROR al obtener folio CAF: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    messages.error(request, f'Error al obtener folio: {str(e)}')
                    return render(request, 'caja/procesar_venta.html', {
                        'ticket': ticket,
                        'form': form,
                        'apertura_activa': apertura_activa,
                    })

            # Generar número de venta
            if folio_caf:
                # Si hay folio CAF, usar ese número
                numero = folio_caf
                print(f"Usando folio CAF: {numero}")
            else:
                # Si no hay CAF (documentos no electrónicos), generar correlativo
                print(f"Generando número correlativo para {tipo_documento}...")
                
                # Buscar el número más alto existente (a nivel empresa)
                ventas_existentes = Venta.objects.filter(
                    empresa=request.empresa
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
                    numero_venta=numero_venta
                ).exists():
                    break
                print(f"   #{numero_venta} existe, probando siguiente...")
                numero += 1
                numero_venta = f"{numero:06d}"
            
            print(f"   Numero generado: {numero_venta}")
            
            # Ahora crear la venta dentro de una transacción con manejo de IntegrityError
            max_reintentos = 20
            venta_creada_exitosamente = False
            
            for reintento in range(max_reintentos):
                try:
                    with transaction.atomic():
                        print(f"Iniciando transaccion atomica (intento {reintento + 1})...")
                        
                        # Usar la primera forma de pago como principal (solo si NO es guía)
                        primera_forma_pago = None
                        if tipo_documento != 'guia' and formas_pago_dict:
                            print(f"Obteniendo forma de pago ID: {formas_pago_dict[1]['forma_pago_id']}")
                            primera_forma_pago = FormaPago.objects.get(pk=formas_pago_dict[1]['forma_pago_id'])
                            print(f"   Forma de pago: {primera_forma_pago.nombre}")
                        else:
                            print("Guía de despacho - Sin forma de pago")

                        # Crear venta final
                        print(f"Creando venta {tipo_documento} #{numero_venta}...")
                        venta_final = Venta.objects.create(
                        empresa=request.empresa,
                        numero_venta=numero_venta,
                        cliente=ticket.cliente,
                        vendedor=vendedor_seleccionado,
                        vehiculo=vehiculo_seleccionado,
                        chofer=chofer_seleccionado,
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
                    
                    # Registrar movimientos de caja (solo si NO es guía)
                    # Las guías no generan movimientos de caja porque no hay pago
                    if tipo_documento != 'guia':
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
                    
                    # Calcular cambio (solo si NO es guía)
                    monto_cambio = total_pagado - float(ticket.total) if total_pagado > float(ticket.total) else 0
                    
                    # Crear registro de venta procesada
                    # Para guías, no hay movimiento de caja
                    primer_movimiento = None
                    if tipo_documento != 'guia':
                        primer_movimiento = MovimientoCaja.objects.filter(
                            venta=venta_final
                        ).first()
                    
                    venta_procesada = VentaProcesada.objects.create(
                        venta_preventa=ticket,
                        venta_final=venta_final,
                        apertura_caja=apertura_activa,
                        movimiento_caja=primer_movimiento,  # None para guías
                        usuario_proceso=request.user,
                        monto_recibido=Decimal(str(total_pagado)),
                        monto_cambio=Decimal(str(monto_cambio)),
                        observaciones=observaciones
                    )
                    
                    # Descontar stock (solo si NO es guía)
                    # Las guías son documentos de traslado, no de venta
                    if tipo_documento != 'guia' and apertura_activa.caja.bodega:
                        # Deshabilitar temporalmente el signal para evitar duplicados
                        from django.db.models.signals import post_save
                        from ventas.signals import actualizar_stock_venta
                        post_save.disconnect(actualizar_stock_venta, sender=Venta)
                        
                        try:
                            # Descontar stock y crear movimientos de inventario
                            descontar_stock_venta_completo(venta_final, apertura_activa.caja.bodega)
                            venta_procesada.stock_descontado = True
                        finally:
                            # Re-conectar el signal
                            post_save.connect(actualizar_stock_venta, sender=Venta)
                    
                    # Actualizar cuenta corriente si alguna forma de pago es crédito (solo si NO es guía)
                    if tipo_documento != 'guia':
                        for idx, datos_pago in formas_pago_dict.items():
                            forma_pago = FormaPago.objects.get(pk=datos_pago['forma_pago_id'])
                            if forma_pago.es_cuenta_corriente and ticket.cliente:
                                actualizar_cuenta_corriente_cliente(venta_final, ticket.cliente)
                                venta_procesada.cuenta_corriente_actualizada = True
                            break
                    
                    venta_procesada.save()

                    # GENERAR DTE SI FE ESTÁ ACTIVADA O CIERRE DIRECTO ACTIVO, Y TIPO DE DOCUMENTO ES FACTURABLE
                    print(
                        f"[POS] Flags cierre_directo={request.session.get('pos_cierre_directo', False)} "
                        f"enviar_sii_directo={request.session.get('pos_enviar_sii_directo', True)} "
                        f"flujo={request.session.get('pos_flujo_directo', '')} tipo_doc={tipo_documento} "
                        f"FE_activa={request.empresa.facturacion_electronica}"
                    )
                    cierre_directo_flag = request.session.get('pos_cierre_directo', False)
                    if tipo_documento in ['factura', 'boleta', 'guia']:
                        try:
                            # --- INICIO: Lógica de generación de DTE corregida ---
                            print(f"Generando DTE para {tipo_documento} #{numero_venta}...")
                            
                            # El folio ya fue validado y la variable 'caf' contiene el CAF correcto.
                            # La variable 'numero_venta' contiene el folio a utilizar.
                            # La variable 'tipo_dte' contiene el código SII del documento.

                            # Crear el objeto DTE en la base de datos
                            dte = DocumentoTributarioElectronico.objects.create(
                                empresa=request.empresa,
                                tipo_dte=tipo_dte,
                                folio=numero_venta,
                                fecha_emision=venta_final.fecha,
                                usuario_creacion=request.user,
                                estado_sii='NoEnviado',
                                caf_utilizado=caf,
                                monto_neto=int(venta_final.neto),
                                monto_iva=int(venta_final.iva),
                                monto_exento=0, # Asumimos no exento por ahora
                                monto_total=int(venta_final.total),
                                rut_receptor=ticket.cliente.rut if ticket.cliente else '66666666-6',
                                razon_social_receptor=ticket.cliente.nombre if ticket.cliente else 'Cliente Genérico',
                                giro_receptor=getattr(ticket.cliente, 'giro', '') if ticket.cliente else '',
                                direccion_receptor=ticket.cliente.direccion if ticket.cliente else '',
                                comuna_receptor=ticket.cliente.comuna if ticket.cliente else '',
                                rut_emisor=request.empresa.rut,
                                razon_social_emisor=request.empresa.razon_social,
                                giro_emisor=getattr(request.empresa, 'giro', ''),
                            )
                            
                            # Asociar la venta al DTE para poder generar el XML
                            # El generador espera una relación 'orden_despacho', la usamos de forma genérica.
                            dte.orden_despacho.add(venta_final)
                            dte.save()
                            
                            # Generar hoja de ruta automáticamente si aplica
                            if tipo_documento == 'factura' and venta_final.cliente and venta_final.vehiculo and venta_final.chofer:
                                try:
                                    from pedidos.utils_hoja_ruta import generar_hoja_ruta_automatica
                                    hoja_ruta = generar_hoja_ruta_automatica(dte, venta_final, request.empresa)
                                    if hoja_ruta:
                                        print(f"[OK] Hoja de ruta generada automáticamente: {hoja_ruta.numero_ruta}")
                                except Exception as e_hr:
                                    print(f"[WARN] Error al generar hoja de ruta automática: {e_hr}")
                                    import traceback
                                    traceback.print_exc()

                            # --- PROCESAMIENTO COMPLETO DEL DTE ---
                            empresa = request.empresa
                            # 1. Generar XML
                            generator = DTEXMLGenerator(empresa, dte, dte.tipo_dte, dte.folio, dte.caf_utilizado)
                            xml_sin_firmar = generator.generar_xml_desde_dte()

                            # 2. Firmar XML
                            firmador = FirmadorDTE(empresa.certificado_digital.path, empresa.password_certificado)
                            xml_firmado = firmador.firmar_xml(xml_sin_firmar)

                            # 3. Generar TED
                            primer_item_nombre = venta_final.ventadetalle_set.first().articulo.nombre if venta_final.ventadetalle_set.exists() else 'Venta POS'
                            dte_data = {'rut_emisor': dte.rut_emisor, 'tipo_dte': dte.tipo_dte, 'folio': dte.folio, 'fecha_emision': dte.fecha_emision.strftime('%Y-%m-%d'), 'rut_receptor': dte.rut_receptor, 'razon_social_receptor': dte.razon_social_receptor, 'monto_total': dte.monto_total, 'item_1': primer_item_nombre}
                            caf_data = {'rut_emisor': dte.caf_utilizado.empresa.rut, 'razon_social': dte.caf_utilizado.empresa.razon_social_sii or dte.caf_utilizado.empresa.razon_social, 'tipo_documento': dte.caf_utilizado.tipo_documento, 'folio_desde': dte.caf_utilizado.folio_desde, 'folio_hasta': dte.caf_utilizado.folio_hasta, 'fecha_autorizacion': dte.caf_utilizado.fecha_autorizacion.strftime('%Y-%m-%d'), 'modulo': 'MODULO_PLACEHOLDER', 'exponente': 'EXPONENTE_PLACEHOLDER', 'firma': dte.caf_utilizado.firma_electronica}
                            ted_xml = firmador.generar_ted(dte_data, caf_data)

                            # 4. Generar datos para PDF417
                            pdf417_data = firmador.generar_datos_pdf417(ted_xml)

                            # 5. Actualizar DTE
                            dte.xml_dte = xml_sin_firmar
                            dte.xml_firmado = xml_firmado
                            dte.timbre_electronico = ted_xml
                            dte.datos_pdf417 = pdf417_data
                            dte.estado_sii = 'generado'
                            dte.save()

                            # 6. Generar imagen del timbre
                            PDF417Generator.guardar_pdf417_en_dte(dte)
                            
                            venta_procesada.dte_generado = dte
                            venta_procesada.save()
                            messages.success(request, f'{dte.get_tipo_dte_display()} N° {dte.folio} generada con timbre SII.')

                        except Exception as e:
                            print(f"[ERROR] ERROR inesperado al generar DTE: {str(e)}")
                            import traceback
                            traceback.print_exc()
                            messages.warning(request, f'Error al generar DTE: {str(e)}. La venta se proceso correctamente.')
                    
                    # Limpiar banderas de sesión de cierre directo (si existen)
                    try:
                        if 'pos_cierre_directo' in request.session:
                            request.session.pop('pos_cierre_directo')
                        if 'pos_flujo_directo' in request.session:
                            request.session.pop('pos_flujo_directo')
                        if 'pos_enviar_sii_directo' in request.session:
                            request.session.pop('pos_enviar_sii_directo')
                    except Exception as e:
                        print(f"Error limpiando flags de sesión: {e}")

                    # Actualizar estado del ticket
                    ticket.estado = 'confirmada'
                    ticket.save()
                    
                    # Recalcular totales de la apertura (solo si NO es guía)
                    if tipo_documento != 'guia':
                        apertura_activa.calcular_totales()
                    
                    # Mensaje de éxito
                    if tipo_documento == 'guia':
                        msg = f'Exito: Guía de Despacho #{venta_final.numero_venta} generada exitosamente.'
                    else:
                        msg = f'Exito: {venta_final.get_tipo_documento_display()} #{venta_final.numero_venta} generada exitosamente. Cambio: ${monto_cambio:,.0f}'
                    messages.success(request, msg)
                    
                    print("="*80)
                    print("[OK] VENTA PROCESADA EXITOSAMENTE")
                    print(f"   Venta Final ID: {venta_final.id}")
                    print(f"   Número: {venta_final.numero_venta}")
                    print(f"   Tipo: {venta_final.tipo_documento}")
                    print(f"   Total: ${venta_final.total}")
                    print(f"   DTE Generado: {venta_procesada.dte_generado}")
                    print("="*80)
                    
                    venta_creada_exitosamente = True

                                        # --- INICIO: Bloque para impresión automática ---
                    # Determinar la URL de impresión y renderizar la página intermedia
                    doc_url = ""
                    from django.urls import reverse
                    dte_generado = venta_procesada.dte_generado

                    print(f"[DEBUG] Preparando redireccion...")
                    print(f"   DTE Generado: {dte_generado}")
                    
                    if dte_generado:
                        doc_url = reverse('facturacion_electronica:ver_factura_electronica', args=[dte_generado.pk])
                        doc_url += "?auto=1"
                        print(f"   URL DTE: {doc_url}")
                    else:
                        doc_url = reverse('ventas:venta_html', args=[venta_final.pk]) + "?auto=1"
                        print(f"   URL Venta: {doc_url}")

                    print(f"[DEBUG] Redirigiendo a la URL del documento: {doc_url}")
                    return redirect(doc_url)
                    # --- FIN: Bloque para impresión automática ---
                    
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
                    print(f"[ERROR] ERROR en intento {reintento + 1}: {type(e).__name__}: {str(e)}")
                    raise
            
            # Si llegamos aqui sin exito, mostrar error
            if not venta_creada_exitosamente:
                print(f"[ERROR] ERROR EN EXCEPCION: {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Error al procesar la venta: {str(e)}')
    
    # Obtener detalles del ticket
    detalles = ticket.ventadetalle_set.all().select_related('articulo')
    
    # Verificar disponibilidad de folios si FE está activa
    disponibilidad_folios = None
    disponibilidad_folios_json = '{}'
    if empresa.facturacion_electronica:
        try:
            from facturacion_electronica.services import DTEService
            disponibilidad_folios = DTEService.verificar_disponibilidad_folios(empresa)
            disponibilidad_folios_json = json.dumps(disponibilidad_folios)
            print(f"DEBUG - Disponibilidad de folios: {disponibilidad_folios}")
        except Exception as e:
            print(f"Error al verificar folios: {e}")
            disponibilidad_folios = {}
            disponibilidad_folios_json = '{}'

    # Obtener lista de vendedores activos
    from ventas.models import Vendedor
    vendedores = Vendedor.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
    
    # Obtener lista de vehículos y choferes si el sistema de despacho está activo
    vehiculos = []
    choferes = []
    if empresa.usa_sistema_despacho:
        try:
            from pedidos.models_transporte import Vehiculo, Chofer
            vehiculos = Vehiculo.objects.filter(empresa=request.empresa, activo=True).order_by('patente')
            choferes = Chofer.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
        except Exception as e:
            print(f"Error al cargar vehículos/choferes: {e}")
    
    context = {
        'form': form,
        'ticket': ticket,
        'apertura_activa': apertura_activa,
        'mostrar_modal_apertura': mostrar_modal_apertura,
        'form_apertura': form_apertura,
        'tipo_documento_planeado': ticket.tipo_documento_planeado,
        'disponibilidad_folios': disponibilidad_folios,
        'disponibilidad_folios_json': disponibilidad_folios_json,
        'empresa': empresa,
        'vendedores': vendedores,
        'vehiculos': vehiculos,
        'choferes': choferes
    }
    
    return render(request, 'caja/procesar_venta.html', context)


# ========================================
# FUNCIONES AUXILIARES
# ========================================

def descontar_stock_venta(venta, bodega):
    """Descuenta el stock de los artículos vendidos (solo actualiza stock, no crea movimientos)"""
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


def descontar_stock_venta_completo(venta, bodega):
    """Descuenta el stock y crea movimientos de inventario, evitando duplicados"""
    
    for detalle in venta.ventadetalle_set.all():
        articulo = detalle.articulo
        
        # Solo procesar si el artículo tiene control de stock
        if not articulo.control_stock:
            continue
        
        # Verificar si ya existe un movimiento de inventario para esta venta y artículo
        movimiento_existente = Inventario.objects.filter(
            empresa=venta.empresa,
            bodega_origen=bodega,
            articulo=articulo,
            tipo_movimiento='salida',
            numero_documento=venta.numero_venta,
            estado='confirmado'
        ).first()
        
        if movimiento_existente:
            # Si ya existe, solo actualizar el stock si es necesario, pero no crear otro movimiento
            print(f"[INFO] Movimiento de inventario ya existe para venta {venta.numero_venta}, artículo {articulo.nombre}. Saltando creación duplicada.")
            continue
        
        # Actualizar stock
        try:
            stock = Stock.objects.get(
                empresa=venta.empresa,
                bodega=bodega,
                articulo=articulo
            )
            
            if stock.cantidad >= detalle.cantidad:
                stock.cantidad -= detalle.cantidad
            else:
                stock.cantidad = Decimal('0.00')
            stock.save()
        except Stock.DoesNotExist:
            stock = Stock.objects.create(
                empresa=venta.empresa,
                bodega=bodega,
                articulo=articulo,
                cantidad=Decimal('0.00'),
                precio_promedio=detalle.precio_unitario
            )
        
        # Crear movimiento de inventario
        Inventario.objects.create(
            empresa=venta.empresa,
            bodega_origen=bodega,
            articulo=articulo,
            tipo_movimiento='salida',
            cantidad=detalle.cantidad,
            precio_unitario=detalle.precio_unitario,
            descripcion=f'Venta {venta.numero_venta} - {venta.get_tipo_documento_display()}',
            numero_documento=venta.numero_venta,
            estado='confirmado',
            creado_por=venta.usuario_creacion
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
            print(f"[OK] Nueva cuenta corriente creada para {cliente.nombre}")

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
            print(f"[OK] Documento creado: {documento.tipo_documento} {documento.numero_documento}")

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

        print(f"[OK] Venta a credito registrada: {cliente.nombre} - ${venta.total} - Movimiento #{movimiento.id}")

        return True

    except Exception as e:
        print(f"[ERROR] Error al registrar venta a credito: {e}")
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
