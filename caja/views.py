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
    
    # Obtener TODOS los tickets facturables pendientes (no solo del día actual)
    # CRÍTICO: Corregir tickets invertidos primero
    from django.utils import timezone
    from django.db.models import Q
    from datetime import timedelta
    
    # CORRECCIÓN: Primero corregir TODOS los tickets invertidos sin restricción de fecha
    tickets_invertidos = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento__in=['boleta', 'factura', 'guia'],
        tipo_documento_planeado='vale',
        facturado=False,
        estado__in=['borrador', 'confirmada']
    )
    
    if tickets_invertidos.exists():
        for ticket in tickets_invertidos:
            tipo_original = ticket.tipo_documento
            ticket.tipo_documento = 'vale'
            ticket.tipo_documento_planeado = tipo_original
            ticket.save()
    
    # Corregir tickets sin tipo_documento_planeado válido
    tickets_a_corregir = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='vale',
        facturado=False,
        estado__in=['borrador', 'confirmada']
    ).filter(
        Q(tipo_documento_planeado__isnull=True) | 
        Q(tipo_documento_planeado='') |
        Q(tipo_documento_planeado='vale')
    )
    if tickets_a_corregir.exists():
        tickets_a_corregir.update(tipo_documento_planeado='boleta')
    
    # CONSULTA SIMPLIFICADA AL MÁXIMO: Solo condiciones esenciales
    # NO restringir por fecha, NO restringir por estado, solo facturado=False
    tickets_pendientes = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='vale',
        facturado=False
    ).exclude(
        tipo_documento_planeado='vale'
    ).exclude(
        tipo_documento_planeado__isnull=True
    ).exclude(
        tipo_documento_planeado=''
    ).select_related('cliente', 'vendedor', 'estacion_trabajo').order_by('-fecha_creacion')[:500]  # Limitar a 500 para rendimiento
    
    # Debug simplificado (sin usar métodos de queryset después de slice)
    print(f"[DEBUG APERTURA_DETAIL] Tickets pendientes cargados (máximo 500)")
    
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
    
    # Obtener ventas procesadas durante esta apertura
    # Solo incluir: boletas, facturas, notas de crédito y débito
    # Excluir: vales facturables, guías y cotizaciones
    ventas = VentaProcesada.objects.filter(
        apertura_caja=apertura,
        venta_final__tipo_documento__in=['boleta', 'factura']
    ).exclude(
        venta_final__tipo_documento__in=['vale', 'guia', 'cotizacion']
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
    
    # Obtener movimientos de caja (ingresos/egresos manuales y devoluciones)
    movimientos = MovimientoCaja.objects.filter(
        apertura_caja=apertura,
        tipo__in=['ingreso', 'retiro', 'devolucion']  # Movimientos manuales y devoluciones
    ).order_by('fecha')
    
    # Obtener devoluciones (notas de crédito, devoluciones de dinero)
    devoluciones = movimientos.filter(tipo='devolucion').select_related('forma_pago', 'venta', 'usuario')
    
    # Calcular totales de movimientos
    ingresos_extra = movimientos.filter(tipo='ingreso').aggregate(
        total=models.Sum('monto')
    )['total'] or Decimal('0.00')
    
    egresos_extra = movimientos.filter(tipo='retiro').aggregate(
        total=models.Sum('monto')
    )['total'] or Decimal('0.00')
    
    # Calcular total de devoluciones (notas de crédito, devoluciones de dinero)
    total_devoluciones = devoluciones.aggregate(
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
        'devoluciones': devoluciones,
        'total_devoluciones': total_devoluciones,
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
                # Buscar vale que no haya sido facturado aún - LÓGICA SIMPLE
                ticket = Venta.objects.filter(
                    empresa=request.empresa,
                    numero_venta=numero_ticket,
                    tipo_documento='vale',
                    facturado=False  # Solo vales NO facturados
                ).first()
                
                if ticket:
                    return redirect('caja:procesar_venta', ticket_id=ticket.pk)
                else:
                    messages.error(request, f'No se encontró el ticket #{numero_ticket} o ya fue procesado.')
            except Exception as e:
                messages.error(request, f'Error al buscar el ticket #{numero_ticket}: {str(e)}')
        else:
            messages.error(request, 'Debe ingresar un número de ticket.')
    
    # CORRECCIÓN: Primero corregir TODOS los tickets invertidos sin restricción de fecha
    from django.db.models import Q
    from datetime import timedelta
    
    tickets_invertidos = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento__in=['boleta', 'factura', 'guia'],
        tipo_documento_planeado='vale',
        facturado=False,
        estado__in=['borrador', 'confirmada']
    )
    
    if tickets_invertidos.exists():
        for ticket in tickets_invertidos:
            tipo_original = ticket.tipo_documento
            ticket.tipo_documento = 'vale'
            ticket.tipo_documento_planeado = tipo_original
            ticket.save()
    
    # Corregir tickets sin tipo_documento_planeado válido
    tickets_a_corregir = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='vale',
        facturado=False,
        estado__in=['borrador', 'confirmada']
    ).filter(
        Q(tipo_documento_planeado__isnull=True) | 
        Q(tipo_documento_planeado='') |
        Q(tipo_documento_planeado='vale')
    )
    if tickets_a_corregir.exists():
        tickets_a_corregir.update(tipo_documento_planeado='boleta')
    
    # CONSULTA SIMPLIFICADA AL MÁXIMO: Solo condiciones esenciales
    # NO restringir por fecha, NO restringir por estado, solo facturado=False
    tickets_pendientes = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='vale',
        facturado=False
    ).exclude(
        tipo_documento_planeado='vale'
    ).exclude(
        tipo_documento_planeado__isnull=True
    ).exclude(
        tipo_documento_planeado=''
    ).select_related('cliente', 'vendedor', 'estacion_trabajo').order_by('-fecha_creacion')[:500]  # Limitar a 500 para rendimiento
    
    # Debug: información de depuración
    todos_los_vales = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='vale'
    )
    
    # Verificar también si hay VentaProcesada asociados
    vales_con_procesada = []
    for v in todos_los_vales:
        if VentaProcesada.objects.filter(venta_preventa=v).exists():
            vales_con_procesada.append(v.id)
    
    # Debug: imprimir información de depuración simplificada
    print("=" * 80)
    print(f"[DEBUG PROCESAR VENTA BUSCAR] Empresa: {request.empresa.nombre} (ID: {request.empresa.id})")
    print(f"[DEBUG] Total vales: {todos_los_vales.count()}")
    print(f"[DEBUG] Vales NO facturados (facturado=False): {todos_los_vales.filter(facturado=False).count()}")
    print(f"[DEBUG] Vales facturados (facturado=True): {todos_los_vales.filter(facturado=True).count()}")
    print(f"[DEBUG] Vales con VentaProcesada asociada: {len(vales_con_procesada)}")
    print(f"[DEBUG] Vales pendientes encontrados: {tickets_pendientes.count()}")
    
    # Mostrar detalles de los primeros vales para depuración
    if todos_los_vales.exists():
        print("\n[DEBUG] Primeros vales del día:")
        for v in todos_los_vales[:10]:
            tiene_procesada = VentaProcesada.objects.filter(venta_preventa=v).exists()
            print(f"  - Vale #{v.numero_venta}: facturado={v.facturado}, estado={v.estado}, tipo_planeado={v.tipo_documento_planeado}, tiene_procesada={tiene_procesada}, estacion={v.estacion_trabajo.nombre if v.estacion_trabajo else 'N/A'}")
    
    if tickets_pendientes.exists():
        print("\n[DEBUG] Vales pendientes que aparecerán en la lista:")
        for v in tickets_pendientes[:5]:
            tiene_procesada = VentaProcesada.objects.filter(venta_preventa=v).exists()
            print(f"  - Vale #{v.numero_venta}: facturado={v.facturado}, tipo_planeado={v.tipo_documento_planeado}, tiene_procesada={tiene_procesada}")
    else:
        print("\n[DEBUG] ⚠️ NO HAY VALES PENDIENTES")
        vales_no_facturados = todos_los_vales.filter(facturado=False)
        if vales_no_facturados.exists():
            print(f"  → Hay {vales_no_facturados.count()} vales con facturado=False pero no aparecen")
            print("  → Verificando si tienen VentaProcesada asociada...")
            for v in vales_no_facturados[:5]:
                tiene_procesada = VentaProcesada.objects.filter(venta_preventa=v).exists()
                print(f"    - Vale #{v.numero_venta}: tiene_procesada={tiene_procesada}")
    print("=" * 80)
    
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
    
    # DEBUG: Verificar sesión al inicio
    print("=" * 80)
    print(f"[CAJA PROCESAR_VENTA] INICIO - Ticket ID: {ticket_id}")
    print(f"  Método: {request.method}")
    print(f"  pos_estacion_id en sesión: {request.session.get('pos_estacion_id', 'NO DEFINIDO')}")
    print(f"  pos_enviar_sii_directo en sesión: {request.session.get('pos_enviar_sii_directo', 'NO DEFINIDO')}")
    print(f"  pos_cierre_directo en sesión: {request.session.get('pos_cierre_directo', 'NO DEFINIDO')}")
    print("=" * 80)
    
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
        
        # Obtener configuración de la estación ANTES de decidir el tipo de documento
        estacion_id = request.session.get('pos_estacion_id')
        cierre_directo_flag = False
        enviar_sii_directo_flag = False
        
        if estacion_id:
            try:
                from ventas.models import EstacionTrabajo
                estacion = EstacionTrabajo.objects.get(id=estacion_id, empresa=request.empresa)
                estacion.refresh_from_db()
                cierre_directo_flag = bool(estacion.cierre_directo)
                enviar_sii_directo_flag = bool(estacion.enviar_sii_directo)
            except EstacionTrabajo.DoesNotExist:
                cierre_directo_flag = request.session.get('pos_cierre_directo', False)
                enviar_sii_directo_flag = request.session.get('pos_enviar_sii_directo', False)
        else:
            cierre_directo_flag = request.session.get('pos_cierre_directo', False)
            enviar_sii_directo_flag = request.session.get('pos_enviar_sii_directo', False)
        
        print("=" * 80)
        print(f"[CAJA POST] CONFIGURACIÓN INICIAL:")
        print(f"  Estación ID: {estacion_id}")
        print(f"  cierre_directo: {cierre_directo_flag}")
        print(f"  enviar_sii_directo: {enviar_sii_directo_flag}")
        
        # CRÍTICO: La caja SIEMPRE usa el tipo_documento_planeado del vale
        # La caja NO permite cambiar el tipo de documento, solo procesa y cobra
        # REFRESCAR el ticket desde la BD para asegurar que tenemos el valor más actualizado
        ticket.refresh_from_db()
        tipo_documento = ticket.tipo_documento_planeado or 'boleta'
        tipo_documento_original = ticket.tipo_documento or 'vale'  # Tipo original del ticket
        
        # VALIDACIÓN CRÍTICA: Asegurar que tipo_documento sea válido
        # IMPORTANTE: Solo validar y corregir si es necesario, pero NO guardar aquí
        # porque podría afectar otros campos como facturado o fecha_creacion
        tipos_validos = ['factura', 'boleta', 'guia', 'cotizacion']
        if tipo_documento not in tipos_validos:
            print(f"[ERROR CRÍTICO] tipo_documento_planeado inválido: '{tipo_documento}', corrigiendo a 'boleta'")
            tipo_documento = 'boleta'
            # Solo actualizar en memoria, se guardará después cuando se procese la venta
            ticket.tipo_documento_planeado = 'boleta'
            # NO guardar aquí para evitar problemas con facturado o fecha_creacion
        
        print(f"  → Ticket ID: {ticket.id}")
        print(f"  → Ticket número: {ticket.numero_venta}")
        print(f"  → tipo_documento_planeado (BD): '{ticket.tipo_documento_planeado}'")
        print(f"  → Tipo documento (desde vale): '{tipo_documento}' (NO se puede cambiar en caja)")
        print(f"  → Tipo documento original: '{tipo_documento_original}'")
        print("=" * 80)
        
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
        
        # CRÍTICO: En la CAJA, los vales facturables SÍ requieren pago
        # Solo las guías de despacho NO requieren pago (son documentos de traslado)
        print(f"[DEBUG] Validando tipo documento: tipo_documento={tipo_documento}, tipo_documento_original={tipo_documento_original}")
        
        # ==============================================================================
        # DEFINICIÓN DE ESCENARIOS (HILOS INDEPENDIENTES)
        # ==============================================================================
        
        # DETECTAR SI ESTAMOS EN EL MÓDULO DE CAJA
        # Si hay una apertura activa, significa que estamos procesando desde el módulo de caja
        es_modulo_caja = apertura_activa is not None
        
        # 1. ESCENARIO GUÍA (Guía de Despacho)
        # Documento de traslado, no requiere pago, genera DTE 52
        es_guia = (tipo_documento_original == 'guia' or tipo_documento == 'guia')
        
        # 2. ESCENARIO POS VALE (Solo Ticket)
        # Estación POS sin cierre directo ni envío SII. Solo genera vale para cobrar después.
        # NO requiere pago, NO genera DTE.
        # CRÍTICO: NO considerar como POS Vale si estamos en el módulo de caja
        es_pos_vale = (not es_guia) and (not es_modulo_caja) and (not cierre_directo_flag and not enviar_sii_directo_flag)
        
        # 3. ESCENARIO VENTA FINAL (Caja o POS Directo)
        # Caja procesando vale O Estación POS con cierre directo.
        # SÍ requiere pago, SÍ genera DTE (Factura/Boleta).
        es_venta_final = (not es_guia) and (not es_pos_vale)
        
        print(f"[ESCENARIO DETECTADO]")
        print(f"  - Es Módulo Caja: {es_modulo_caja}")
        print(f"  - Es Guía: {es_guia}")
        print(f"  - Es POS Vale (Solo Ticket): {es_pos_vale}")
        print(f"  - Es Venta Final (Caja/POS Directo): {es_venta_final}")
        
        # ==============================================================================
        # VALIDACIÓN DE PAGOS SEGÚN ESCENARIO
        # ==============================================================================
        
        validacion_pagos_ok = True
        
        if es_guia:
            print("[VALIDACIÓN] Escenario GUÍA: No requiere validación de pagos.")
            # Limpiar formas de pago por si acaso
            formas_pago_dict = {}
            total_pagado = 0
            
        elif es_pos_vale:
            print("[VALIDACIÓN] Escenario POS VALE: No requiere validación de pagos (se cobra en caja).")
            # Permitir guardar sin pagos
            
        elif es_venta_final:
            print("[VALIDACIÓN] Escenario VENTA FINAL: SÍ requiere validación de pagos.")
            # Validar que hay al menos una forma de pago
            if not formas_pago_dict:
                print("ERROR: No hay formas de pago en Venta Final")
                messages.error(request, 'Debe ingresar al menos una forma de pago.')
                validacion_pagos_ok = False
            # Validar que el total pagado sea suficiente
            elif total_pagado < total_ticket:
                print(f"ERROR: Total pagado insuficiente (diferencia: ${total_ticket - total_pagado:,.2f})")
                messages.error(request, f'El monto pagado (${total_pagado:,.0f}) es MENOR al total del documento (${total_ticket:,.0f}). Faltan ${(total_ticket - total_pagado):,.0f}.')
                validacion_pagos_ok = False
            else:
                print(f"[OK] Validación de pagos correcta: ${total_pagado:,.0f} >= ${total_ticket:,.0f}")
        
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
        
        # Procesar venta si las validaciones pasaron
        if validacion_pagos_ok:
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

            # IMPORTANTE: El número de venta se obtiene del folio CAF si se va a generar DTE.
            # Si NO se va a generar DTE (modo vale), usar un correlativo simple temporal.
            # El folio real se asigna dentro del bloque de generación de DTE usando FolioService.
            
            # Ahora crear la venta dentro de una transacción con manejo de IntegrityError
            max_reintentos = 20
            venta_creada_exitosamente = False
            
            for reintento in range(max_reintentos):
                try:
                    with transaction.atomic():
                        print(f"Iniciando transaccion atomica (intento {reintento + 1})...")
                        
                        # Para vales y casos sin DTE, generar un número temporal DENTRO de la transacción
                        # para evitar race conditions
                        from django.db.models import Max
                        
                        max_numero = Venta.objects.filter(
                            empresa=request.empresa,
                            tipo_documento=tipo_documento  # Filtrar por el mismo tipo de documento
                        ).select_for_update().aggregate(
                            max_numero=Max('numero_venta')
                        )['max_numero']
                        
                        numero_temp = 1
                        if max_numero:
                            try:
                                numero_temp = int(max_numero) + 1
                            except (ValueError, TypeError):
                                numero_temp = 1
                        
                        # Agregar timestamp para mayor unicidad en caso de colisión
                        import time
                        timestamp_suffix = int(time.time() * 1000) % 1000
                        numero_venta_temporal = f"T{numero_temp:05d}{timestamp_suffix:03d}"
                        print(f"Número temporal para la venta: {numero_venta_temporal} (se reemplazará con folio CAF si se genera DTE)")
                        
                        # Usar la primera forma de pago como principal (solo si NO es guía y hay formas de pago)
                        primera_forma_pago = None
                        if tipo_documento != 'guia' and formas_pago_dict:
                            print(f"Obteniendo forma de pago ID: {formas_pago_dict[1]['forma_pago_id']}")
                            primera_forma_pago = FormaPago.objects.get(pk=formas_pago_dict[1]['forma_pago_id'])
                            print(f"   Forma de pago: {primera_forma_pago.nombre}")
                        elif tipo_documento == 'guia':
                            print("Guía de despacho - Sin forma de pago")
                        elif tipo_documento == 'vale' and not cierre_directo_flag and not enviar_sii_directo_flag:
                            print("Vale facturable - Sin forma de pago (se procesará después en caja)")
                        else:
                            print("Sin forma de pago")

                        # Crear venta final
                        
                        # Determinar tipos de documento según escenario
                        tipo_doc_crear = tipo_documento
                        tipo_doc_planeado_crear = tipo_documento
                        
                        if es_pos_vale:
                            print("[CREACIÓN] Escenario POS VALE: Creando documento tipo 'vale'")
                            tipo_doc_crear = 'vale'
                            tipo_doc_planeado_crear = tipo_documento # Mantener el planeado (boleta/factura)
                        elif es_guia:
                            print("[CREACIÓN] Escenario GUÍA: Creando documento tipo 'guia'")
                            tipo_doc_crear = 'guia'
                            tipo_doc_planeado_crear = 'guia'
                        else:
                            print(f"[CREACIÓN] Escenario VENTA FINAL: Creando documento tipo '{tipo_documento}'")
                            # Validar que sea un tipo válido de venta final
                            if tipo_doc_crear not in ['factura', 'boleta', 'guia']:
                                print(f"[WARN] Tipo '{tipo_doc_crear}' inválido para venta final, corrigiendo a 'boleta'")
                                tipo_doc_crear = 'boleta'
                                tipo_doc_planeado_crear = 'boleta'
                        
                        print(f"Creando venta #{numero_venta_temporal}...")
                        print(f"   - Tipo Documento: {tipo_doc_crear}")
                        print(f"   - Tipo Planeado: {tipo_doc_planeado_crear}")
                        
                        venta_final = Venta.objects.create(
                        empresa=request.empresa,
                        numero_venta=numero_venta_temporal,  # Se actualizará con el folio CAF si se genera DTE
                        cliente=ticket.cliente,
                        vendedor=vendedor_seleccionado,
                        vehiculo=vehiculo_seleccionado,
                        chofer=chofer_seleccionado,
                        forma_pago=primera_forma_pago,
                        estacion_trabajo=ticket.estacion_trabajo,
                        tipo_documento=tipo_doc_crear,
                        tipo_documento_planeado=tipo_doc_planeado_crear,
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
                        print(f"[CRÍTICO] Venta creada: ID={venta_final.id}, tipo_documento='{venta_final.tipo_documento}'")
                        
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
                    
                    # ==============================================================================
                    # REGISTRO DE MOVIMIENTOS Y VENTA PROCESADA SEGÚN ESCENARIO
                    # ==============================================================================
                    
                    primer_movimiento = None
                    monto_recibido = Decimal('0')
                    monto_cambio = Decimal('0')
                    
                    if es_guia:
                        print("[PROCESO] Escenario GUÍA: No se registran movimientos de caja.")
                        # No crear movimientos
                        
                    elif es_pos_vale:
                        print("[PROCESO] Escenario POS VALE: No se registran movimientos de caja (pendiente de pago).")
                        # No crear movimientos
                        
                    elif es_venta_final:
                        print("[PROCESO] Escenario VENTA FINAL: Registrando movimientos de caja...")
                        
                        # 1. Registrar movimientos de caja
                        if formas_pago_dict:
                            for idx, datos_pago in formas_pago_dict.items():
                                forma_pago = FormaPago.objects.get(pk=datos_pago['forma_pago_id'])
                                
                                descripcion = f"{venta_final.get_tipo_documento_display()} #{venta_final.numero_venta}"
                                if len(formas_pago_dict) > 1:
                                    descripcion += f" (Pago {idx}/{len(formas_pago_dict)})"
                                
                                mov = MovimientoCaja.objects.create(
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
                                
                                if not primer_movimiento:
                                    primer_movimiento = mov
                            
                            print(f"[OK] Movimientos registrados.")
                        
                        # 2. Calcular cambio
                        monto_recibido = Decimal(str(total_pagado))
                        if total_pagado > float(ticket.total):
                            monto_cambio = Decimal(str(total_pagado - float(ticket.total)))
                        
                        # 3. Actualizar cuenta corriente si aplica
                        for idx, datos_pago in formas_pago_dict.items():
                            forma_pago = FormaPago.objects.get(pk=datos_pago['forma_pago_id'])
                            if forma_pago.es_cuenta_corriente and ticket.cliente:
                                actualizar_cuenta_corriente_cliente(venta_final, ticket.cliente)
                                break

                    # Crear registro de VentaProcesada (común para todos, pero con datos diferentes)
                    venta_procesada = VentaProcesada.objects.create(
                        venta_preventa=ticket,
                        venta_final=venta_final,
                        apertura_caja=apertura_activa,
                        movimiento_caja=primer_movimiento,
                        usuario_proceso=request.user,
                        monto_recibido=monto_recibido,
                        monto_cambio=monto_cambio,
                        observaciones=observaciones
                    )
                    
                    if es_venta_final and primer_movimiento and primer_movimiento.forma_pago.es_cuenta_corriente:
                        venta_procesada.cuenta_corriente_actualizada = True
                    
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
                    
                    venta_procesada.save()

                    # ==============================================================================
                    # GENERACIÓN DE DTE SEGÚN ESCENARIO
                    # ==============================================================================
                    
                    debe_generar_dte = False
                    
                    if es_guia:
                        print("[DTE] Escenario GUÍA: Generando DTE Guía de Despacho (52)...")
                        debe_generar_dte = True
                        
                    elif es_pos_vale:
                        print("[DTE] Escenario POS VALE: NO se genera DTE (solo ticket/vale).")
                        debe_generar_dte = False
                        
                    elif es_venta_final:
                        print("[DTE] Escenario VENTA FINAL: Generando DTE Factura/Boleta...")
                        # Verificar que la empresa tenga FE activa
                        if request.empresa.facturacion_electronica:
                            debe_generar_dte = True
                        else:
                            print("[WARN] Empresa sin FE activa, no se genera DTE.")
                            debe_generar_dte = False
                    
                    print(f"  → ¿Debe generar DTE?: {debe_generar_dte}")
                    print("=" * 80)
                    
                    # Variable para guardar el DTE creado (fuera del try para que esté disponible después)
                    dte_creado = None
                    
                    # Calcular mostrar_formas_pago ANTES del bloque try para que esté disponible en caso de error
                    # NO mostrar formas de pago para vales (se cobran al procesar en caja)
                    if tipo_documento == 'vale':
                        mostrar_formas_pago = False
                    else:
                        mostrar_formas_pago = (cierre_directo_flag or enviar_sii_directo_flag) or tipo_documento in ['factura', 'boleta']
                    
                    # Inicializar disponibilidad_folios ANTES del bloque try para que esté disponible en caso de error
                    disponibilidad_folios = None
                    if request.empresa.facturacion_electronica:
                        try:
                            from facturacion_electronica.dte_service import DTEService
                            disponibilidad_folios = DTEService.verificar_disponibilidad_folios(request.empresa)
                        except Exception as e:
                            print(f"[WARN] Error al verificar disponibilidad de folios: {e}")
                            disponibilidad_folios = {}
                    
                    if debe_generar_dte:
                        print("=" * 80)
                        print("[⚠️] ENTRANDO AL BLOQUE DE GENERACIÓN DE DTE")
                        print(f"  debe_generar_dte = {debe_generar_dte}")
                        print("=" * 80)
                        
                        # Mapear tipo de documento a código SII
                        tipo_dte_map = {
                            'factura': '33',
                            'boleta': '39',
                            'guia': '52',
                        }
                        tipo_dte = tipo_dte_map.get(tipo_documento)
                        
                        if not tipo_dte:
                            raise ValueError(f"Tipo de documento '{tipo_documento}' no válido para DTE")
                        
                        try:
                            # =================================================================
                            # PASO 1: OBTENER FOLIO DEL CAF USANDO FolioService
                            # =================================================================
                            print(f"[FOLIO] Obteniendo folio del CAF para tipo DTE {tipo_dte}...")
                            from facturacion_electronica.services import FolioService
                            from empresas.models import Sucursal
                            
                            # Obtener sucursal para asignación de folios
                            sucursal_facturacion = request.sucursal_activa if hasattr(request, 'sucursal_activa') and request.sucursal_activa else None
                            if not sucursal_facturacion:
                                sucursal_facturacion = Sucursal.objects.filter(empresa=request.empresa, es_principal=True).first()
                            if not sucursal_facturacion:
                                sucursal_facturacion = Sucursal.objects.filter(empresa=request.empresa).first()
                            
                            if not sucursal_facturacion:
                                raise ValueError("No se encontró sucursal para asignar folios. Debe existir al menos una sucursal activa.")
                            
                            print(f"[FOLIO] Sucursal para folios: {sucursal_facturacion.nombre}")
                            
                            # CRÍTICO: Obtener el folio Y el CAF desde FolioService
                            # Esto asegura que el folio esté dentro del rango autorizado
                            # NOTA: obtener_siguiente_folio retorna (folio, caf) - 2 valores
                            folio_dte, caf_obtenido = FolioService.obtener_siguiente_folio(
                                empresa=request.empresa,
                                tipo_documento=tipo_dte,
                                sucursal=sucursal_facturacion
                            )
                            
                            if folio_dte is None or caf_obtenido is None:
                                raise ValueError(f"No se pudo obtener folio para tipo DTE {tipo_dte}. Verifique que haya un CAF activo y con folios disponibles.")
                            
                            print(f"[FOLIO] Folio obtenido: {folio_dte}")
                            print(f"[FOLIO] CAF utilizado: ID {caf_obtenido.id}, Rango: {caf_obtenido.folio_desde}-{caf_obtenido.folio_hasta}")
                            
                            # ACTUALIZAR el número de venta con el folio real del CAF
                            numero_venta_real = str(folio_dte)
                            venta_final.numero_venta = numero_venta_real
                            venta_final.save(update_fields=['numero_venta'])
                            print(f"[FOLIO] Venta actualizada con número {numero_venta_real}")
                            
                            # =================================================================
                            # PASO 2: CREAR EL DTE CON EL FOLIO CORRECTO
                            # =================================================================
                            # --- INICIO: Lógica de generación de DTE corregida ---
                            print(f"Generando DTE para {tipo_documento} con folio #{folio_dte}...")
                            
                            # Usar el CAF obtenido desde FolioService (ya validado y con folio asignado)
                            caf = caf_obtenido

                            # Crear el objeto DTE en la base de datos
                            dte = DocumentoTributarioElectronico.objects.create(
                                empresa=request.empresa,
                                tipo_dte=tipo_dte,
                                folio=folio_dte,  # ← USAR EL FOLIO DEL CAF, NO numero_venta
                                fecha_emision=venta_final.fecha,
                                usuario_creacion=request.user,
                                estado_sii='NoEnviado',
                                caf_utilizado=caf,  # CAF ya viene validado y con folio asignado desde FolioService
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
                                vehiculo=vehiculo_seleccionado if 'vehiculo_seleccionado' in locals() else None,
                                chofer=chofer_seleccionado if 'chofer_seleccionado' in locals() else None,
                                vendedor=vendedor_seleccionado if 'vendedor_seleccionado' in locals() else None,
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

                            # 3. Generar TED (usar DTEBox si está habilitado, sino generar localmente)
                            ted_xml = None
                            if empresa.dtebox_habilitado:
                                print(f"[DTE] Usando DTEBox para timbraje offline...")
                                try:
                                    from facturacion_electronica.dtebox_service import DTEBoxService
                                    dtebox = DTEBoxService(empresa)
                                    resultado = dtebox.timbrar_dte(xml_firmado)
                                    
                                    if resultado['success']:
                                        ted_xml = resultado['ted']
                                        print(f"[DTE] ✅ TED obtenido desde DTEBox")
                                    else:
                                        print(f"[DTE] ⚠️ Error en DTEBox: {resultado['error']}")
                                        print(f"[DTE] Fallback: Generando TED localmente...")
                                        # Fallback a generación local
                                        primer_item_nombre = venta_final.ventadetalle_set.first().articulo.nombre if venta_final.ventadetalle_set.exists() else 'Venta POS'
                                        dte_data = {'rut_emisor': dte.rut_emisor, 'tipo_dte': dte.tipo_dte, 'folio': dte.folio, 'fecha_emision': dte.fecha_emision.strftime('%Y-%m-%d'), 'rut_receptor': dte.rut_receptor, 'razon_social_receptor': dte.razon_social_receptor, 'monto_total': dte.monto_total, 'item_1': primer_item_nombre}
                                        caf_data = {'rut_emisor': dte.caf_utilizado.empresa.rut, 'razon_social': dte.caf_utilizado.empresa.razon_social_sii or dte.caf_utilizado.empresa.razon_social, 'tipo_documento': dte.caf_utilizado.tipo_documento, 'folio_desde': dte.caf_utilizado.folio_desde, 'folio_hasta': dte.caf_utilizado.folio_hasta, 'fecha_autorizacion': dte.caf_utilizado.fecha_autorizacion.strftime('%Y-%m-%d'), 'modulo': 'MODULO_PLACEHOLDER', 'exponente': 'EXPONENTE_PLACEHOLDER', 'firma': dte.caf_utilizado.firma_electronica}
                                        ted_xml = firmador.generar_ted(dte_data, caf_data)
                                except Exception as e_dtebox:
                                    print(f"[DTE] ⚠️ Error al inicializar DTEBox: {str(e_dtebox)}")
                                    print(f"[DTE] Fallback: Generando TED localmente...")
                                    # Fallback a generación local
                                    primer_item_nombre = venta_final.ventadetalle_set.first().articulo.nombre if venta_final.ventadetalle_set.exists() else 'Venta POS'
                                    dte_data = {'rut_emisor': dte.rut_emisor, 'tipo_dte': dte.tipo_dte, 'folio': dte.folio, 'fecha_emision': dte.fecha_emision.strftime('%Y-%m-%d'), 'rut_receptor': dte.rut_receptor, 'razon_social_receptor': dte.razon_social_receptor, 'monto_total': dte.monto_total, 'item_1': primer_item_nombre}
                                    caf_data = {'rut_emisor': dte.caf_utilizado.empresa.rut, 'razon_social': dte.caf_utilizado.empresa.razon_social_sii or dte.caf_utilizado.empresa.razon_social, 'tipo_documento': dte.caf_utilizado.tipo_documento, 'folio_desde': dte.caf_utilizado.folio_desde, 'folio_hasta': dte.caf_utilizado.folio_hasta, 'fecha_autorizacion': dte.caf_utilizado.fecha_autorizacion.strftime('%Y-%m-%d'), 'modulo': 'MODULO_PLACEHOLDER', 'exponente': 'EXPONENTE_PLACEHOLDER', 'firma': dte.caf_utilizado.firma_electronica}
                                    ted_xml = firmador.generar_ted(dte_data, caf_data)
                            else:
                                # Generación local (método original)
                                print(f"[DTE] Generando TED localmente...")
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
                            
                            # CRÍTICO: Asignar DTE a venta_procesada y guardar INMEDIATAMENTE
                            venta_procesada.dte_generado = dte
                            venta_procesada.save()
                            
                            print(f"[OK] DTE creado: ID={dte.id}, Folio={dte.folio}, Tipo={dte.get_tipo_dte_display()}")
                            
                            # Guardar referencia del DTE para usar después (NO refrescar desde BD)
                            dte_creado = dte  # Usar directamente el objeto creado
                            
                            # CRÍTICO: En la CAJA, SIEMPRE enviar al SII cuando se genera un DTE
                            # Porque es el proceso final de facturación (el cliente ya pagó y debe recibir documento válido)
                            procesando_desde_caja = True  # Esta función solo se llama desde la caja
                            
                            print("=" * 80)
                            print(f"[CAJA] VERIFICANDO ENVÍO AL SII:")
                            print(f"  Procesando desde: CAJA (siempre enviar al SII)")
                            print(f"  FE activa: {request.empresa.facturacion_electronica}")
                            
                            # En la caja SIEMPRE enviar al SII porque:
                            # 1. El cliente ya pagó
                            # 2. Es el documento tributario final que debe ser válido
                            # 3. Es el flujo completo de facturación
                            debe_enviar_sii = procesando_desde_caja and request.empresa.facturacion_electronica
                            
                            print(f"  → DECISIÓN: {'ENVIARÁ' if debe_enviar_sii else 'NO ENVIARÁ'} al SII")
                            if not request.empresa.facturacion_electronica:
                                print(f"    Razón: Facturación electrónica no está activa")
                            print("=" * 80)
                            
                            if debe_enviar_sii:
                                print(f"[✓] ENVIANDO DTE AL SII EN SEGUNDO PLANO...")
                                try:
                                    # Usar envío en background (threading)
                                    from facturacion_electronica.background_sender import get_background_sender
                                    
                                    sender = get_background_sender()
                                    if sender.enviar_dte(dte.id, request.empresa.id):
                                        print(f"[OK] ✅ DTE agregado a la cola de envío (background)")
                                        if tipo_documento == 'guia':
                                            messages.success(request, f'✅ Guía de Despacho N° {dte.folio} generada y enviándose al SII. Puede tardar unos segundos.')
                                        else:
                                            messages.success(request, f'✅ {dte.get_tipo_dte_display()} N° {dte.folio} generada y enviándose al SII. Puede tardar unos segundos.')
                                    else:
                                        print(f"[ERROR] ❌ No se pudo agregar DTE a la cola")
                                        messages.warning(request, f'⚠️ {dte.get_tipo_dte_display()} N° {dte.folio} generada con timbre, pero no se pudo iniciar el envío automático.')
                                        
                                except Exception as e_envio:
                                    print(f"[ERROR] ❌ Error al iniciar envío en background: {e_envio}")
                                    import traceback
                                    traceback.print_exc()
                                    messages.warning(request, f'⚠️ {dte.get_tipo_dte_display()} N° {dte.folio} generada con timbre, pero hubo un error al iniciar el envío automático.')
                            else:
                                print(f"[✗] NO se enviará al SII - FE no está activa")
                                messages.success(request, f'{dte.get_tipo_dte_display()} N° {dte.folio} generada con timbre.')

                        except Exception as e:
                            print(f"[ERROR] ERROR CRÍTICO al generar DTE: {str(e)}")
                            import traceback
                            traceback.print_exc()
                            # CRÍTICO: NO continuar si hay error - mostrar error y volver al formulario
                            messages.error(request, f'ERROR CRÍTICO al generar DTE: {str(e)}. La venta NO se procesó completamente.')
                            # Guardar venta_procesada sin DTE para que se pueda reintentar
                            venta_procesada.save()
                            # Retornar al formulario para que el usuario pueda reintentar
                            return render(request, 'caja/procesar_venta.html', {
                                'ticket': ticket,
                                'form': form,
                                'apertura_activa': apertura_activa,
                                'mostrar_formas_pago': mostrar_formas_pago,
                                'disponibilidad_folios': disponibilidad_folios,
                            })
                    
                    # NO limpiar las banderas de sesión - deben persistir durante toda la sesión del POS
                    # Las configuraciones de la estación deben mantenerse hasta que se cambie de estación o se cierre el POS

                    else:
                        # NO se genera DTE - Solo se procesa como ticket/vale facturable
                        print("=" * 80)
                        print("[INFO] NO se generará DTE - Solo ticket/vale facturable")
                        print(f"  Configuración: cierre_directo={cierre_directo_flag}, enviar_sii_directo={enviar_sii_directo_flag}")
                        print(f"  FE activa: {request.empresa.facturacion_electronica}")
                        print(f"  Tipo documento: {tipo_documento}")
                        print(f"  → NO se generará DTE porque ambos flags están desactivados")
                        print("=" * 80)
                        messages.info(request, f'Ticket #{venta_final.numero_venta} procesado como vale facturable. El DTE se generará cuando se configure para emitir documentos.')
                    
                    # Actualizar estado del ticket y marcarlo como facturado
                    ticket.estado = 'confirmada'
                    ticket.facturado = True  # ← Marcar como facturado para que no aparezca más en la lista
                    ticket.save()
                    
                    # Recalcular totales de la apertura (solo si NO es guía)
                    if tipo_documento != 'guia':
                        apertura_activa.calcular_totales()
                    
                    # Mensaje de éxito
                    if not debe_generar_dte:
                        # Solo ticket/vale facturable, sin DTE
                        msg = f'Éxito: Ticket #{venta_final.numero_venta} procesado como vale facturable. Cambio: ${monto_cambio:,.0f}'
                    elif tipo_documento == 'guia':
                        msg = f'Éxito: Guía de Despacho #{venta_final.numero_venta} generada exitosamente.'
                    else:
                        msg = f'Éxito: {venta_final.get_tipo_documento_display()} #{venta_final.numero_venta} generada exitosamente. Cambio: ${monto_cambio:,.0f}'
                    messages.success(request, msg)
                    
                    print("="*80)
                    print("[OK] VENTA PROCESADA EXITOSAMENTE")
                    print(f"   Venta Final ID: {venta_final.id}")
                    print(f"   Número: {venta_final.numero_venta}")
                    print(f"   Tipo: {venta_final.tipo_documento}")
                    print(f"   Total: ${venta_final.total}")
                    print(f"   DTE Generado: {venta_procesada.dte_generado if debe_generar_dte else 'NO (solo ticket/vale facturable)'}")
                    print("="*80)
                    
                    venta_creada_exitosamente = True

                    # --- LÓGICA SIMPLE: Si se generó DTE, mostrar DTE. Si no, mostrar vale ---
                    from django.urls import reverse
                    
                    # Usar directamente el DTE que acabamos de crear (si existe)
                    dte_para_mostrar = None
                    if debe_generar_dte and dte_creado:
                        dte_para_mostrar = dte_creado
                        print(f"[REDIRECCION] Usando DTE creado: ID={dte_creado.id}, Folio={dte_creado.folio}")
                    else:
                        # Fallback: refrescar desde BD solo si no tenemos el objeto
                        venta_procesada.refresh_from_db()
                        dte_para_mostrar = venta_procesada.dte_generado
                        if dte_para_mostrar:
                            print(f"[REDIRECCION] Usando DTE desde BD: ID={dte_para_mostrar.id}")
                        else:
                            print(f"[REDIRECCION] NO hay DTE disponible")
                    
                    print(f"[REDIRECCION] venta_final.id: {venta_final.id}, numero: {venta_final.numero_venta}")
                    print(f"[REDIRECCION] tipo_documento_original: {tipo_documento_original}")
                    print(f"[REDIRECCION] tipo_documento (final): {tipo_documento}")
                    print(f"[REDIRECCION] debe_generar_dte: {debe_generar_dte}")
                    print(f"[REDIRECCION] dte_para_mostrar: {dte_para_mostrar}")
                    
                    # LÓGICA CORREGIDA DE REDIRECCIÓN:
                    # PRIORIDAD 1: Si se GENERÓ DTE → Mostrar documento tributario con timbre
                    # PRIORIDAD 2: Si NO se generó DTE → Mostrar vale/ticket
                    
                    if dte_para_mostrar:
                        # DTE GENERADO → Mostrar documento tributario electrónico con timbre
                        # Esto aplica para:
                        # 1. CAJA procesando vales facturables (✅ ESTE ES EL CASO QUE ESTABA FALLANDO)
                        # 2. POS con cierre directo
                        caja_url = reverse('caja:procesar_venta_buscar')
                        doc_url = reverse('facturacion_electronica:ver_factura_electronica', args=[dte_para_mostrar.pk])
                        doc_url += f"?auto=1&from_caja=1&return_url={caja_url}"
                        print(f"[OK] ✅ DTE GENERADO - Redirigiendo a documento tributario")
                        print(f"     DTE ID: {dte_para_mostrar.pk}")
                        print(f"     Folio: {dte_para_mostrar.folio}")
                        print(f"     Tipo: {dte_para_mostrar.get_tipo_dte_display()}")
                        return redirect(doc_url)
                    else:
                        # NO SE GENERÓ DTE → Mostrar ticket/vale
                        # Esto solo aplica para POS sin cierre directo (vales facturables pendientes de caja)
                        pos_url = reverse('ventas:pos_view')
                        vale_url = reverse('ventas:vale_html', args=[venta_final.pk])
                        vale_url += f"?auto=1&return_url={pos_url}"
                        print(f"[OK] 📄 SIN DTE - Redirigiendo a ticket/vale")
                        print(f"     Vale ID: {venta_final.pk}")
                        print(f"     Número: {venta_final.numero_venta}")
                        print(f"     (Se facturará después en caja)")
                        return redirect(vale_url)
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
    
    # Obtener configuración de la estación para el template
    estacion_id = request.session.get('pos_estacion_id')
    cierre_directo_flag = False
    enviar_sii_directo_flag = False
    
    if estacion_id:
        try:
            from ventas.models import EstacionTrabajo
            estacion = EstacionTrabajo.objects.get(id=estacion_id, empresa=request.empresa)
            estacion.refresh_from_db()
            cierre_directo_flag = bool(estacion.cierre_directo)
            enviar_sii_directo_flag = bool(estacion.enviar_sii_directo)
        except EstacionTrabajo.DoesNotExist:
            cierre_directo_flag = request.session.get('pos_cierre_directo', False)
            enviar_sii_directo_flag = request.session.get('pos_enviar_sii_directo', False)
    else:
        cierre_directo_flag = request.session.get('pos_cierre_directo', False)
        enviar_sii_directo_flag = request.session.get('pos_enviar_sii_directo', False)
    
    # Determinar si mostrar formas de pago
    # CRÍTICO: En la CAJA, SIEMPRE debemos mostrar formas de pago para cobrar vales facturables
    # Solo NO mostrar formas de pago para Guías de Despacho (documentos de traslado sin cobro)
    tipo_doc_planeado = ticket.tipo_documento_planeado or 'boleta'
    tipo_doc_actual = ticket.tipo_documento or 'vale'
    
    # DETECTAR SI ESTAMOS EN EL MÓDULO DE CAJA
    # Si hay una apertura activa, significa que estamos procesando desde el módulo de caja
    es_modulo_caja = apertura_activa is not None
    
    # LÓGICA CORREGIDA:
    # 1. Guías de despacho → NO requieren pago (documentos de traslado)
    # 2. MÓDULO DE CAJA → SIEMPRE mostrar formas de pago (excepto guías) porque estamos facturando y cobrando
    # 3. POS sin cierre directo (solo vale) → NO requieren pago aquí (se cobra después en caja)
    # 4. POS con cierre directo → SÍ requieren pago
    
    if tipo_doc_planeado == 'guia':
        # Las guías de despacho NO requieren pago (son documentos de traslado)
        mostrar_formas_pago = False
        print(f"[DEBUG] Guía de despacho detectada - NO mostrar formas de pago")
    elif es_modulo_caja:
        # MÓDULO DE CAJA: Siempre mostrar formas de pago (excepto guías que ya fueron filtradas arriba)
        # Cuando estamos en caja, estamos facturando documentos, por lo tanto debemos cobrar
        mostrar_formas_pago = True
        print(f"[DEBUG] MÓDULO DE CAJA detectado (apertura activa existe) - SÍ mostrar formas de pago")
    elif not cierre_directo_flag and not enviar_sii_directo_flag:
        # POS sin cierre directo: Solo genera vale facturable (se cobra después en caja)
        mostrar_formas_pago = False
        print(f"[DEBUG] POS modo vale (sin cierre directo) - NO mostrar formas de pago")
    else:
        # POS con cierre directo → SÍ mostrar formas de pago
        mostrar_formas_pago = True
        print(f"[DEBUG] POS con cierre directo - SÍ mostrar formas de pago")
    
    print(f"[DEBUG] mostrar_formas_pago: {mostrar_formas_pago}")
    print(f"  - es_modulo_caja (apertura_activa existe): {es_modulo_caja}")
    print(f"  - cierre_directo_flag: {cierre_directo_flag}")
    print(f"  - enviar_sii_directo_flag: {enviar_sii_directo_flag}")
    print(f"  - tipo_documento (actual del ticket): {tipo_doc_actual}")
    print(f"  - tipo_documento_planeado: {tipo_doc_planeado}")
    print(f"  - Es vale facturable: {tipo_doc_actual == 'vale'}")
    print(f"  - Se mostrará sección de pago: {mostrar_formas_pago}")
    
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
        'choferes': choferes,
        'mostrar_formas_pago': mostrar_formas_pago,
        'cierre_directo_flag': cierre_directo_flag,
        'enviar_sii_directo_flag': enviar_sii_directo_flag,
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
