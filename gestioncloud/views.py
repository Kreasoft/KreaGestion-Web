from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.decorators import requiere_empresa
from articulos.models import Articulo
from clientes.models import Cliente
from inventario.models import Stock, Inventario
from ventas.models import Venta, VentaDetalle
from bodegas.models import Bodega
from empresas.models import Empresa, Sucursal
from django.db.models import Sum, Q, F, Count, DateField
from django.db.models.functions import Coalesce, TruncDate, ExtractMonth, ExtractYear
from django.utils import timezone
from datetime import datetime, time, timedelta

@login_required
@requiere_empresa
def dashboard(request):
    """Dashboard principal con estadísticas reales filtradas por sucursal"""

    # Cambios rápidos del tablero ejecutivo. La empresa continúa aislada por
    # sesión y la bodega seleccionada siempre se valida contra esa empresa.
    if request.method == 'POST' and request.POST.get('dashboard_selector'):
        from django.shortcuts import redirect
        if request.POST.get('dashboard_selector') == 'empresa' and request.user.is_superuser:
            try:
                nueva_empresa = Empresa.objects.get(pk=request.POST.get('empresa_id'))
                request.session['empresa_activa_id'] = nueva_empresa.id
                request.session['empresa_activa'] = nueva_empresa.id
                request.session.pop('dashboard_bodega_id', None)
                request.session.modified = True
                response = redirect('dashboard')
                response.set_cookie('empresa_activa_id', nueva_empresa.id, max_age=30*24*60*60, httponly=True, samesite='Lax')
                return response
            except (Empresa.DoesNotExist, ValueError, TypeError):
                pass
        elif request.POST.get('dashboard_selector') == 'bodega':
            bodega_id = request.POST.get('bodega_id', '')
            if bodega_id:
                bodega_valida = Bodega.objects.filter(pk=bodega_id, empresa=request.empresa, activa=True).first()
                if bodega_valida:
                    request.session['dashboard_bodega_id'] = bodega_valida.id
            else:
                request.session.pop('dashboard_bodega_id', None)
            request.session.modified = True
            return redirect('dashboard')
        elif request.POST.get('dashboard_selector') == 'fondo':
            fondo = request.POST.get('fondo', 'foto')
            request.session['dashboard_fondo'] = fondo if fondo in ('foto', 'suave') else 'foto'
            request.session.modified = True
            return redirect('dashboard')
        elif request.POST.get('dashboard_selector') == 'menu':
            layout = request.POST.get('menu_layout', 'lateral')
            if layout not in ('lateral', 'superior'):
                layout = 'lateral'
            request.session['menu_layout'] = layout
            request.session.modified = True
            response = redirect('dashboard')
            response.set_cookie('menu_layout', layout, max_age=30*24*60*60, samesite='Lax')
            return response
    
    # --- Ruteo por tipo de usuario ---
    try:
        tipo_usuario = request.user.perfil.tipo_usuario
    except:
        tipo_usuario = 'administrador'
        
    if tipo_usuario == 'vendedor':
        return dashboard_vendedor(request)
    elif tipo_usuario == 'cajero':
        return dashboard_cajero(request)
    
    # Obtener todas las sucursales de la empresa
    sucursales = Sucursal.objects.filter(empresa=request.empresa, estado='activa').order_by('nombre')
    
    # Manejar cambio de sucursal
    sucursal_id = request.GET.get('sucursal', '')
    if sucursal_id:
        if sucursal_id == 'todas':
            # Limpiar sucursal de la sesión
            if 'sucursal_filtro_id' in request.session:
                del request.session['sucursal_filtro_id']
            # Redirect para que el middleware actualice
            from django.shortcuts import redirect
            return redirect('dashboard')
        else:
            try:
                sucursal_seleccionada = Sucursal.objects.get(id=sucursal_id, empresa=request.empresa)
                # Guardar en sesión con el nombre correcto
                request.session['sucursal_filtro_id'] = sucursal_seleccionada.id
                # Redirect para que el middleware actualice
                from django.shortcuts import redirect
                return redirect('dashboard')
            except Sucursal.DoesNotExist:
                sucursal_seleccionada = None
    
    # Obtener sucursal del middleware (ya actualizada)
    sucursal_seleccionada = getattr(request, 'sucursal_activa', None)
    bodegas_dashboard = Bodega.objects.filter(empresa=request.empresa, activa=True).order_by('nombre')
    bodega_seleccionada = None
    bodega_sesion_id = request.session.get('dashboard_bodega_id')
    if bodega_sesion_id:
        bodega_seleccionada = bodegas_dashboard.filter(pk=bodega_sesion_id).first()
        if not bodega_seleccionada:
            request.session.pop('dashboard_bodega_id', None)
    
    # Calcular estadísticas reales
    total_articulos = Articulo.objects.filter(empresa=request.empresa, activo=True).count()
    
    # Clientes activos
    total_clientes = Cliente.objects.filter(empresa=request.empresa, estado='activo').count()
    
    # --- Cálculo de Estado de Stock Basado en Movimientos (Lógica de Kardex) ---
    movimientos_query = Inventario.objects.filter(empresa=request.empresa, estado='confirmado')

    # Lógica de cálculo de stock: Suma directa de todos los movimientos (positivos y negativos).
    if bodega_seleccionada:
        movimientos_query = movimientos_query.filter(
            Q(bodega_origen=bodega_seleccionada) | Q(bodega_destino=bodega_seleccionada)
        )
    elif sucursal_seleccionada:
        bodegas_sucursal_ids = Bodega.objects.filter(empresa=request.empresa, sucursal=sucursal_seleccionada).values_list('id', flat=True)
        # Se consideran todos los movimientos que entran o salen de las bodegas de la sucursal.
        movimientos_query = movimientos_query.filter(
            Q(bodega_origen_id__in=bodegas_sucursal_ids) | Q(bodega_destino_id__in=bodegas_sucursal_ids)
        )

    # La suma de cantidades (positivas y negativas) da el stock neto.
    stock_calculado = movimientos_query.values('articulo_id').annotate(stock_neto=Sum('cantidad'))
    stock_map = {item['articulo_id']: item['stock_neto'] for item in stock_calculado}

    # Obtener todos los artículos activos con sus umbrales de stock
    articulos = Articulo.objects.filter(empresa=request.empresa, activo=True).values('id', 'stock_minimo', 'stock_maximo')

    stock_normal = 0
    stock_bajo = 0
    stock_sin = 0
    stock_sobre = 0

    for art in articulos:
        cantidad_actual = float(stock_map.get(art['id'], 0) or 0)
        stock_min = float(art['stock_minimo'] or 0)
        stock_max = float(art['stock_maximo'] or 0)

        if cantidad_actual <= 0:
            stock_sin += 1
        elif stock_max > 0 and cantidad_actual >= stock_max:
            stock_sobre += 1
        elif cantidad_actual <= stock_min:
            stock_bajo += 1
        else:
            stock_normal += 1
    
    # Ventas de los últimos 30 días: por fecha de venta (DateField) O fecha de creación (DateTime)
    inicio_periodo = (timezone.now() - timedelta(days=30)).date()
    ventas_query = Venta.objects.filter(
        empresa=request.empresa,
        estado__in=['confirmada', 'borrador']
    ).filter(
        Q(fecha__gte=inicio_periodo) | Q(fecha_creacion__date__gte=inicio_periodo)
    )
    
    # Filtrar ventas por sucursal si está seleccionada
    if sucursal_seleccionada:
        ventas_query = ventas_query.filter(sucursal=sucursal_seleccionada)
    
    ventas_mes = ventas_query.aggregate(total=Sum('total'))['total'] or 0

    # Indicadores ejecutivos del dashboard alternativo. Se basan solo en
    # ventas confirmadas para no inflar resultados con borradores.
    hoy = timezone.localdate()
    ventas_confirmadas = Venta.objects.filter(
        empresa=request.empresa,
        estado='confirmada',
    )
    if sucursal_seleccionada:
        ventas_confirmadas = ventas_confirmadas.filter(sucursal=sucursal_seleccionada)
    ventas_30_confirmadas = ventas_confirmadas.filter(
        Q(fecha__gte=inicio_periodo) | Q(fecha_creacion__date__gte=inicio_periodo)
    )
    resumen_ventas = ventas_30_confirmadas.aggregate(total=Sum('total'), cantidad=Count('id'))
    ventas_30_total = resumen_ventas['total'] or 0
    ventas_30_cantidad = resumen_ventas['cantidad'] or 0
    ticket_promedio = ventas_30_total / ventas_30_cantidad if ventas_30_cantidad else 0
    ventas_hoy = ventas_confirmadas.filter(
        Q(fecha=hoy) | Q(fecha_creacion__date=hoy)
    ).aggregate(total=Sum('total'))['total'] or 0
    inicio_anterior = inicio_periodo - timedelta(days=30)
    fin_anterior = inicio_periodo - timedelta(days=1)
    ventas_anterior = ventas_confirmadas.filter(
        Q(fecha__range=(inicio_anterior, fin_anterior)) |
        Q(fecha_creacion__date__range=(inicio_anterior, fin_anterior))
    ).aggregate(total=Sum('total'))['total'] or 0
    variacion_ventas = float((ventas_30_total - ventas_anterior) * 100 / ventas_anterior) if ventas_anterior else (100.0 if ventas_30_total else 0.0)

    from pedidos.models import OrdenPedido
    from pedidos.views import total_saldo_por_despachar
    from tesoreria.models import DocumentoCliente
    OrdenPedido.sincronizar_estados_por_despacho(empresa=request.empresa)
    # Abiertos = con cantidad aún por despachar (incluye borrador si tiene saldo).
    pedidos_pendientes_qs = OrdenPedido.con_saldo_pendiente(empresa=request.empresa)
    if bodega_seleccionada:
        pedidos_pendientes_qs = pedidos_pendientes_qs.filter(bodega=bodega_seleccionada)
    pedidos_pendientes = pedidos_pendientes_qs.count()
    monto_pedidos_pendientes = total_saldo_por_despachar(pedidos_pendientes_qs)
    cuentas_cobrar_qs = DocumentoCliente.objects.filter(
        empresa=request.empresa,
        estado_pago__in=['pendiente', 'parcial', 'vencido'],
    )
    cuentas_por_cobrar = cuentas_cobrar_qs.aggregate(total=Sum('saldo_pendiente'))['total'] or 0
    documentos_vencidos = cuentas_cobrar_qs.filter(estado_pago='vencido').count()
    
    # Clientes nuevos este mes
    # CORRECCIÓN CRÍTICA: Se define inicio_mes aquí para la tarjeta de clientes nuevos.
    inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        clientes_nuevos_mes = Cliente.objects.filter(
            empresa=request.empresa,
            # CORRECCIÓN CRÍTICA: Usar inicio_periodo, no inicio_mes que ya no existe.
        fecha_creacion__gte=inicio_periodo
        ).count()
    except:
        clientes_nuevos_mes = 0
    
    # --- Top 5 productos más vendidos (Lógica Robusta de 2 Pasos) ---
    top_productos_query = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__estado__in=['confirmada', 'borrador']
    ).filter(
        Q(venta__fecha__gte=inicio_periodo) | Q(venta__fecha_creacion__date__gte=inicio_periodo)
    )
    if sucursal_seleccionada:
        top_productos_query = top_productos_query.filter(venta__sucursal=sucursal_seleccionada)

    # 1. Agrupar solo por ID y obtener el ranking
    top_ids_qs = (
        top_productos_query
        .values('articulo_id')
        .annotate(cantidad_total=Sum('cantidad'))
        .order_by('-cantidad_total')[:5]
    )

    # 2. Obtener los detalles de los artículos del Top 5
    top_ids = [item['articulo_id'] for item in top_ids_qs]
    cantidad_map = {item['articulo_id']: item['cantidad_total'] for item in top_ids_qs}

    articulos_top = Articulo.objects.filter(id__in=top_ids).values('id', 'codigo', 'nombre')
    
    # 3. Construir la lista final, ordenando según el ranking de ventas
    articulos_map = {art['id']: art for art in articulos_top}
    top_productos = []
    for articulo_id in top_ids:
        articulo_info = articulos_map.get(articulo_id)
        if articulo_info:
            top_productos.append({
                'codigo': articulo_info['codigo'],
                'nombre': articulo_info['nombre'],
                'cantidad': float(cantidad_map.get(articulo_id, 0))
            })


    # Serie de ventas mensuales del año seleccionado
    anio_actual = hoy.year
    try:
        anio_chart = int(request.GET.get('anio') or anio_actual)
    except (TypeError, ValueError):
        anio_chart = anio_actual
    if anio_chart < 2000 or anio_chart > anio_actual + 1:
        anio_chart = anio_actual

    fecha_venta_expr = Coalesce(
        F('fecha'),
        TruncDate('fecha_creacion'),
        output_field=DateField(),
    )
    anios_chart = set(range(anio_actual - 5, anio_actual + 1))
    anios_chart.add(anio_chart)
    anios_chart.update(
        ventas_confirmadas.annotate(anio=ExtractYear(fecha_venta_expr))
        .exclude(anio__isnull=True)
        .values_list('anio', flat=True)
        .distinct()
    )
    anios_chart = sorted((int(a) for a in anios_chart if a), reverse=True)

    ventas_mes_qs = (
        ventas_confirmadas
        .annotate(fecha_venta=fecha_venta_expr)
        .filter(fecha_venta__year=anio_chart)
        .annotate(mes=ExtractMonth('fecha_venta'))
        .values('mes')
        .annotate(total=Sum('total'))
    )
    montos_mes = {int(item['mes']): float(item['total'] or 0) for item in ventas_mes_qs if item['mes']}
    meses_es = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    labels = meses_es
    data = [montos_mes.get(mes, 0.0) for mes in range(1, 13)]

    # Ventas por categoría del mes
    ventas_categoria_query = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__estado__in=['confirmada', 'borrador']
    ).filter(
        Q(venta__fecha__gte=inicio_periodo) | Q(venta__fecha_creacion__date__gte=inicio_periodo)
    )
    
    # Filtrar por sucursal si está seleccionada
    if sucursal_seleccionada:
        ventas_categoria_query = ventas_categoria_query.filter(venta__sucursal=sucursal_seleccionada)
    
    ventas_por_categoria = (
        ventas_categoria_query
        .values('articulo__categoria__nombre')
        .annotate(total=Sum('precio_total'))
        .order_by('-total')[:5]
    )
    
    categorias_labels = []
    categorias_data = []
    for item in ventas_por_categoria:
        nombre_cat = item['articulo__categoria__nombre'] or 'Sin categoría'
        categorias_labels.append(nombre_cat)
        categorias_data.append(float(item['total']) if item['total'] else 0)
    
    
    import json
    
    # Verificar si el usuario puede cambiar de sucursal manualmente
    puede_filtrar_sucursal = getattr(request, 'puede_cambiar_sucursal', False)
    
    context = {
        'total_articulos': total_articulos,
        'total_clientes': total_clientes,
        'stock_bajo': stock_bajo, # Se mantiene para la tarjeta de resumen
        'stock_data': [stock_normal, stock_bajo, stock_sin, stock_sobre],
        'ventas_mes': ventas_mes,
        'ventas_hoy': ventas_hoy,
        'ventas_30_total': ventas_30_total,
        'ventas_30_cantidad': ventas_30_cantidad,
        'ticket_promedio': ticket_promedio,
        'variacion_ventas': variacion_ventas,
        'pedidos_pendientes': pedidos_pendientes,
        'monto_pedidos_pendientes': monto_pedidos_pendientes,
        'cuentas_por_cobrar': cuentas_por_cobrar,
        'documentos_vencidos': documentos_vencidos,
        'clientes_nuevos_mes': clientes_nuevos_mes,
        'top_productos': json.dumps(top_productos),  # Convertir a JSON
        'ventas_series_labels': labels,
        'ventas_series_data': data,
        'anio_chart': anio_chart,
        'anios_chart': anios_chart,
        'categorias_labels': categorias_labels,
        'categorias_data': categorias_data,
        # Filtro de sucursal
        'puede_filtrar_sucursal': puede_filtrar_sucursal,
        'sucursales': sucursales if puede_filtrar_sucursal else [],
        'sucursal_seleccionada': sucursal_seleccionada,
        'sucursal_id': str(sucursal_seleccionada.id) if sucursal_seleccionada else '',
        'empresas_dashboard': Empresa.objects.all().order_by('nombre') if request.user.is_superuser else [],
        'bodegas_dashboard': bodegas_dashboard,
        'bodega_seleccionada': bodega_seleccionada,
        'dashboard_fondo': request.session.get('dashboard_fondo', 'foto'),
        'ultimas_ventas': list(
            ventas_confirmadas.select_related('cliente').order_by('-fecha', '-id')[:5]
        ),
    }
    # Logs de diagnóstico (últimos 30 días + sucursal activa)
    try:
        ventas_count = ventas_query.count()
        ventas_total = float(ventas_query.aggregate(total=Sum('total'))['total'] or 0)
        productos_distintos = top_productos_query.values('articulo_id').distinct().count()
        categorias_distintas = ventas_categoria_query.values('articulo__categoria_id').distinct().count()
        sucs = list(Sucursal.objects.filter(empresa=request.empresa).values('id','nombre','estado'))
    except Exception as e:
        pass

    # Oficial: Centro Ejecutivo. El anterior queda en /dashboard-clasico/
    if request.resolver_match.url_name == 'dashboard_clasico':
        template_name = 'dashboard.html'
    else:
        template_name = 'dashboard_moderno.html'
    return render(request, template_name, context)

def _dte_de_venta(venta):
    try:
        return venta.dte
    except Exception:
        return None


def _etiqueta_reimpresion_venta(venta):
    """Tipo fiscal y folio CAF (o número interno) para una venta del vendedor."""
    dte = _dte_de_venta(venta)
    if dte and dte.folio:
        tipo = _TIPO_DTE_CORTO.get(str(dte.tipo_dte), dte.get_tipo_dte_display())
        return tipo, dte.folio
    codigo = (getattr(venta, 'tipo_documento', None) or '')
    if codigo == 'ticket':
        codigo = getattr(venta, 'tipo_documento_planeado', None) or 'boleta'
    tipo = _TIPO_VENTA_CORTO.get(codigo) or 'Boleta'
    return tipo, venta.numero_venta


def _clasificar_forma_pago(forma_pago):
    codigo = (getattr(forma_pago, 'codigo', '') or '').upper()
    nombre = (getattr(forma_pago, 'nombre', '') or '').lower()
    if codigo in ('EF', 'EFE', 'EFECTIVO') or 'efectivo' in nombre:
        return 'efectivo'
    if codigo in ('TC', 'TD', 'TAR') or 'tarjeta' in nombre:
        return 'tarjeta'
    if codigo in ('TR', 'TEF', 'TRANSF') or 'transfer' in nombre:
        return 'transferencia'
    return 'otro'


def bodegas_para_rebaja(request, sucursal=None, caja=None, bodega_id=None):
    """Bodega elegida para rebajar stock solo al facturar el documento."""
    sucursal = sucursal or getattr(request, 'sucursal_activa', None)
    qs = Bodega.objects.filter(empresa=request.empresa, activa=True).order_by('nombre')
    if sucursal:
        filtradas = qs.filter(Q(sucursal=sucursal) | Q(sucursal__isnull=True))
        if filtradas.exists():
            qs = filtradas

    candidatas = []
    if bodega_id:
        candidatas.append(bodega_id)
    candidatas.append(request.session.get('dashboard_bodega_id'))
    if getattr(caja, 'bodega_id', None):
        candidatas.append(caja.bodega_id)

    bodega = None
    for raw in candidatas:
        if not raw:
            continue
        bodega = Bodega.objects.filter(pk=raw, empresa=request.empresa, activa=True).first()
        if bodega:
            break
    if not bodega:
        bodega = qs.first()
    return qs, bodega


@login_required
@requiere_empresa
def dashboard_vendedor(request):
    """Puesto de ventas: emitir, consultar y reimprimir documentos del vendedor."""
    import json
    from decimal import Decimal
    from django.db.models import Sum
    from django.db.models.functions import ExtractHour, TruncDate

    hoy = timezone.localdate()
    tz = timezone.get_current_timezone()
    inicio_dia = timezone.make_aware(datetime.combine(hoy, time.min), tz)
    inicio_mes_dt = timezone.make_aware(datetime.combine(hoy.replace(day=1), time.min), tz)

    ventas_usuario = Venta.objects.filter(
        empresa=request.empresa,
        usuario_creacion=request.user,
    ).exclude(estado='anulada').select_related('cliente', 'forma_pago', 'dte')

    ventas_hoy = ventas_usuario.filter(fecha=hoy)
    total_ventas_hoy = ventas_hoy.aggregate(suma=Sum('total'))['suma'] or Decimal('0')
    cantidad_ventas_hoy = ventas_hoy.count()
    ticket_promedio = (total_ventas_hoy / cantidad_ventas_hoy) if cantidad_ventas_hoy else Decimal('0')

    ventas_mes_qs = ventas_usuario.filter(fecha__gte=hoy.replace(day=1))
    total_ventas_mes = ventas_mes_qs.aggregate(suma=Sum('total'))['suma'] or Decimal('0')
    cantidad_ventas_mes = ventas_mes_qs.count()

    cobrado_ayer = ventas_usuario.filter(fecha=hoy - timedelta(days=1)).aggregate(suma=Sum('total'))['suma'] or Decimal('0')
    if cobrado_ayer:
        vs_ayer_pct = int(round(((total_ventas_hoy - cobrado_ayer) / cobrado_ayer) * 100))
    else:
        vs_ayer_pct = 100 if total_ventas_hoy else 0

    tickets_pendientes = ventas_usuario.filter(tipo_documento='ticket', facturado=False)
    tickets_count = tickets_pendientes.count()
    tickets_monto = tickets_pendientes.aggregate(suma=Sum('total'))['suma'] or Decimal('0')

    ver_todas_ventas = request.GET.get('lista') == 'todas'
    fecha_desde, fecha_hasta, inicio_rango, fin_rango = _fecha_rango_caja(request, hoy)
    q_reimp = (request.GET.get('q') or '').strip()
    if ver_todas_ventas:
        documentos_recientes = list(
            ventas_usuario.filter(fecha__gte=fecha_desde, fecha__lte=fecha_hasta).order_by('-fecha_creacion')[:500]
        )
        for venta in documentos_recientes:
            venta.tipo_reimp, venta.folio_caf = _etiqueta_reimpresion_venta(venta)
            venta.tipo_ico, venta.tipo_ico_cls = _icono_tipo_doc(venta.tipo_reimp)
            venta.dte_reimp = _dte_de_venta(venta)
            venta.dte_reimp_id = getattr(venta.dte_reimp, 'id', None)
        if q_reimp:
            needle = q_reimp.casefold()
            documentos_recientes = [
                venta for venta in documentos_recientes
                if needle in f'{venta.tipo_reimp} {venta.folio_caf}'.casefold()
                or needle in (getattr(venta.cliente, 'nombre', None) or '').casefold()
                or needle in (venta.numero_venta or '').casefold()
            ]
        documentos_recientes.sort(
            key=lambda v: (
                (v.tipo_reimp or '').casefold(),
                -(v.fecha_creacion.timestamp() if v.fecha_creacion else 0),
            )
        )
        docs_rango_count = len(documentos_recientes)
        total_rango = sum((v.total or Decimal('0')) for v in documentos_recientes)
    else:
        documentos_recientes = list(ventas_usuario.order_by('-fecha_creacion')[:9])
        for venta in documentos_recientes:
            venta.tipo_reimp, venta.folio_caf = _etiqueta_reimpresion_venta(venta)
            venta.tipo_ico, venta.tipo_ico_cls = _icono_tipo_doc(venta.tipo_reimp)
            venta.dte_reimp = _dte_de_venta(venta)
            venta.dte_reimp_id = getattr(venta.dte_reimp, 'id', None)
        docs_rango_count = len(documentos_recientes)
        total_rango = None

    por_hora = {
        int(r['hora'] or 0): float(r['total'] or 0)
        for r in ventas_usuario.filter(fecha_creacion__gte=inicio_dia).annotate(
            hora=ExtractHour('fecha_creacion')
        ).values('hora').annotate(total=Sum('total'))
    }
    horas_labels = [f'{h:02d}' for h in range(8, 23)]
    horas_values = [int(por_hora.get(h, 0)) for h in range(8, 23)]

    por_dia = {}
    for fila in (
        ventas_usuario.filter(fecha_creacion__gte=inicio_mes_dt)
        .annotate(dia=TruncDate('fecha_creacion'))
        .values('dia')
        .annotate(total=Sum('total'))
    ):
        dia = fila['dia']
        if dia:
            por_dia[dia.day] = float(fila['total'] or 0)
    dias_labels = [f'{d:02d}' for d in range(1, hoy.day + 1)]
    dias_values = [int(por_dia.get(d, 0)) for d in range(1, hoy.day + 1)]
    _meses_es = (
        '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
    )
    mes_activo_label = f'{_meses_es[hoy.month]} {hoy.year}'

    tipos_dte_grafico = {
        '33': 'Facturas', '34': 'Facturas',
        '39': 'Boletas', '41': 'Boletas',
        '52': 'Guías', '56': 'Notas de débito', '61': 'Notas de crédito',
    }
    tipos_venta_grafico = {
        'boleta': 'Boletas', 'boleta_electronica': 'Boletas',
        'factura': 'Facturas', 'factura_electronica': 'Facturas',
        'vale': 'Vales', 'guia': 'Guías', 'cotizacion': 'Cotizaciones',
    }
    tipos_hoy = {}
    for venta in ventas_hoy:
        dte = _dte_de_venta(venta)
        etiqueta = tipos_dte_grafico.get(str(dte.tipo_dte)) if dte else None
        if not etiqueta:
            codigo = (venta.tipo_documento or '')
            if codigo == 'ticket':
                codigo = venta.tipo_documento_planeado or 'boleta'
            etiqueta = tipos_venta_grafico.get(codigo, 'Boletas')
        acc = tipos_hoy.setdefault(etiqueta, {'n': 0, 'total': Decimal('0')})
        acc['n'] += 1
        acc['total'] += venta.total or Decimal('0')
    tipos_labels = list(tipos_hoy.keys()) or ['Sin datos']
    tipos_values = [int(tipos_hoy[k]['total']) for k in tipos_hoy] or [0]

    efectivo = tarjeta = transferencia = Decimal('0')
    for venta in ventas_hoy:
        grupo = _clasificar_forma_pago(venta.forma_pago)
        monto = venta.total or Decimal('0')
        if grupo == 'efectivo':
            efectivo += monto
        elif grupo == 'tarjeta':
            tarjeta += monto
        elif grupo == 'transferencia':
            transferencia += monto

    ahora = timezone.localtime()
    if ahora.hour < 12:
        saludo = 'Buenos días'
    elif ahora.hour < 20:
        saludo = 'Buenas tardes'
    else:
        saludo = 'Buenas noches'

    nombre = ''
    try:
        nombre = (request.user.perfil.nombre_completo or '').strip()
    except Exception:
        nombre = ''
    nombre = nombre or (request.user.first_name or '').strip() or request.user.username
    bodegas_dashboard, bodega_seleccionada = bodegas_para_rebaja(
        request, sucursal=getattr(request, 'sucursal_activa', None)
    )

    context = {
        'saludo': saludo,
        'nombre_vendedor': nombre,
        'bodegas_dashboard': bodegas_dashboard,
        'bodega_seleccionada': bodega_seleccionada,
        'total_ventas_hoy': total_ventas_hoy,
        'cantidad_ventas_hoy': cantidad_ventas_hoy,
        'total_ventas_mes': total_ventas_mes,
        'cantidad_ventas_mes': cantidad_ventas_mes,
        'ticket_promedio': ticket_promedio,
        'cobrado_ayer': cobrado_ayer,
        'vs_ayer_pct': vs_ayer_pct,
        'tickets_count': tickets_count,
        'tickets_monto': tickets_monto,
        'documentos_recientes': documentos_recientes,
        'ver_todas_ventas': ver_todas_ventas,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'docs_rango_count': docs_rango_count,
        'total_rango': total_rango,
        'rango_varios_dias': fecha_desde != fecha_hasta,
        'q_reimp': q_reimp,
        'horas_labels_json': json.dumps(horas_labels),
        'horas_values_json': json.dumps(horas_values),
        'tipos_labels_json': json.dumps(tipos_labels),
        'tipos_values_json': json.dumps(tipos_values),
        'mix_json': json.dumps([int(efectivo), int(tarjeta), int(transferencia)]),
        'dias_labels_json': json.dumps(dias_labels),
        'dias_values_json': json.dumps(dias_values),
        'mes_activo_label': mes_activo_label,
    }
    return render(request, 'dashboard_vendedor.html', context)


_TIPO_DTE_CORTO = {
    '33': 'Factura',
    '34': 'Factura Exenta',
    '39': 'Boleta',
    '41': 'Boleta Exenta',
    '52': 'Guía',
    '56': 'Nota de Débito',
    '61': 'Nota de Crédito',
}

_TIPO_VENTA_CORTO = {
    'factura': 'Factura',
    'factura_electronica': 'Factura',
    'boleta': 'Boleta',
    'boleta_electronica': 'Boleta',
    'guia': 'Guía',
    'vale': 'Vale',
    'cotizacion': 'Cotización',
    'ticket': 'Ticket',
}


def _fecha_rango_caja(request, hoy):
    """Rango Desde/Hasta; por defecto el día de hoy."""
    def _parse(raw):
        try:
            return datetime.strptime((raw or '').strip(), '%Y-%m-%d').date()
        except ValueError:
            return None

    desde = _parse(request.GET.get('desde')) or hoy
    hasta = _parse(request.GET.get('hasta')) or hoy
    if hasta < desde:
        desde, hasta = hasta, desde
    tz = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(desde, time.min), tz)
    fin = timezone.make_aware(datetime.combine(hasta, time.max), tz)
    return desde, hasta, inicio, fin


def _etiqueta_reimpresion(doc):
    """Tipo de documento fiscal y folio CAF (o número interno si no hay DTE)."""
    venta = doc.venta_final
    dte = getattr(doc, 'dte_generado', None)
    if not dte:
        try:
            dte = venta.dte
        except Exception:
            dte = None
    if dte and dte.folio:
        tipo = _TIPO_DTE_CORTO.get(str(dte.tipo_dte), dte.get_tipo_dte_display())
        return tipo, dte.folio
    codigo = (getattr(venta, 'tipo_documento', None) or '')
    if codigo == 'ticket':
        codigo = getattr(venta, 'tipo_documento_planeado', None) or 'boleta'
    tipo = _TIPO_VENTA_CORTO.get(codigo) or 'Boleta'
    return tipo, venta.numero_venta


def _icono_tipo_doc(tipo):
    t = (tipo or '').casefold()
    if 'factura' in t:
        return 'fa-file-invoice', 'tipo-ico-factura'
    if 'boleta' in t:
        return 'fa-receipt', 'tipo-ico-boleta'
    if 'gu' in t:
        return 'fa-truck', 'tipo-ico-guia'
    if 'vale' in t:
        return 'fa-ticket-alt', 'tipo-ico-vale'
    if 'cr' in t:
        return 'fa-file-export', 'tipo-ico-vale'
    if 'd' in t and 'bito' in t:
        return 'fa-file-import', 'tipo-ico-factura'
    return 'fa-receipt', 'tipo-ico-boleta'


@login_required
@requiere_empresa
def dashboard_cajero(request):
    """Puesto de caja: cobrar e imprimir documentos (sin POS ni apertura de turno)."""
    import json
    from decimal import Decimal
    from django.db.models import Sum, Count
    from django.db.models.functions import ExtractHour, TruncDate

    from caja.impresion_utils import agente_impresion_en_linea
    from caja.models import ColaImpresion, VentaProcesada
    from caja.views import _apertura_activa_empresa, _filtrar_tickets_por_caja
    from empresas.middleware import resolver_sucursal_operativa

    sucursal = resolver_sucursal_operativa(request)
    apertura_activa = _apertura_activa_empresa(request, sucursal)

    tickets_qs = Venta.objects.filter(
        empresa=request.empresa,
        tipo_documento='ticket',
        facturado=False,
        venta_preventa__isnull=True,
    ).exclude(
        Q(tipo_documento_planeado='ticket')
        | Q(tipo_documento_planeado__isnull=True)
        | Q(tipo_documento_planeado='')
    )
    tickets_qs = _filtrar_tickets_por_caja(tickets_qs, getattr(apertura_activa, 'caja', None))
    if not apertura_activa and sucursal:
        tickets_qs = tickets_qs.filter(Q(sucursal=sucursal) | Q(sucursal__isnull=True))

    tickets_count = tickets_qs.count()
    tickets_monto = tickets_qs.aggregate(total=Sum('total'))['total'] or Decimal('0')

    inicio_dia = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    docs_qs = VentaProcesada.objects.filter(
        apertura_caja__caja__empresa=request.empresa,
    ).select_related(
        'venta_final', 'venta_preventa', 'venta_final__cliente',
        'dte_generado', 'venta_final__dte',
    )
    if sucursal:
        docs_qs = docs_qs.filter(
            Q(apertura_caja__caja__sucursal=sucursal) | Q(venta_final__sucursal=sucursal)
        )
    documentos_hoy = docs_qs.filter(fecha_proceso__gte=inicio_dia)
    hoy = timezone.localdate()
    ver_todas_ventas = request.GET.get('lista') == 'todas'
    fecha_desde, fecha_hasta, inicio_rango, fin_rango = _fecha_rango_caja(request, hoy)
    q_reimp = (request.GET.get('q') or '').strip()
    if ver_todas_ventas:
        docs_rango_qs = docs_qs.filter(
            fecha_proceso__gte=inicio_rango,
            fecha_proceso__lte=fin_rango,
        )
        documentos_recientes = list(docs_rango_qs.order_by('-fecha_proceso')[:500])
        for doc in documentos_recientes:
            doc.tipo_reimp, doc.folio_caf = _etiqueta_reimpresion(doc)
            doc.tipo_ico, doc.tipo_ico_cls = _icono_tipo_doc(doc.tipo_reimp)
        if q_reimp:
            needle = q_reimp.casefold()
            documentos_recientes = [
                doc for doc in documentos_recientes
                if needle in f'{doc.tipo_reimp} {doc.folio_caf}'.casefold()
                or needle in (getattr(getattr(doc.venta_final, 'cliente', None), 'nombre', None) or '').casefold()
                or needle in (getattr(doc.venta_final, 'numero_venta', None) or '').casefold()
            ]
        documentos_recientes.sort(
            key=lambda d: (
                (d.tipo_reimp or '').casefold(),
                -(d.fecha_proceso.timestamp() if d.fecha_proceso else 0),
            )
        )
        docs_rango_count = len(documentos_recientes)
        total_rango = sum((d.venta_final.total or Decimal('0')) for d in documentos_recientes)
    else:
        documentos_recientes = list(docs_qs.order_by('-fecha_proceso')[:9])
        for doc in documentos_recientes:
            doc.tipo_reimp, doc.folio_caf = _etiqueta_reimpresion(doc)
            doc.tipo_ico, doc.tipo_ico_cls = _icono_tipo_doc(doc.tipo_reimp)
        docs_rango_count = len(documentos_recientes)
        total_rango = None
    cobrado_hoy = documentos_hoy.aggregate(total=Sum('venta_final__total'))['total'] or Decimal('0')
    docs_hoy_count = documentos_hoy.count()
    ticket_promedio = (cobrado_hoy / docs_hoy_count) if docs_hoy_count else Decimal('0')

    inicio_ayer = inicio_dia - timedelta(days=1)
    cobrado_ayer = docs_qs.filter(
        fecha_proceso__gte=inicio_ayer, fecha_proceso__lt=inicio_dia
    ).aggregate(total=Sum('venta_final__total'))['total'] or Decimal('0')
    if cobrado_ayer:
        vs_ayer_pct = int(round(((cobrado_hoy - cobrado_ayer) / cobrado_ayer) * 100))
    else:
        vs_ayer_pct = 100 if cobrado_hoy else 0

    por_hora = {
        int(r['hora'] or 0): float(r['total'] or 0)
        for r in documentos_hoy.annotate(hora=ExtractHour('fecha_proceso'))
        .values('hora')
        .annotate(total=Sum('venta_final__total'))
    }
    horas_labels = [f'{h:02d}' for h in range(8, 23)]
    horas_values = [int(por_hora.get(h, 0)) for h in range(8, 23)]

    tz = timezone.get_current_timezone()
    inicio_mes = timezone.make_aware(datetime.combine(hoy.replace(day=1), time.min), tz)
    por_dia = {}
    for fila in (
        docs_qs.filter(fecha_proceso__gte=inicio_mes)
        .annotate(dia=TruncDate('fecha_proceso'))
        .values('dia')
        .annotate(total=Sum('venta_final__total'))
    ):
        dia = fila['dia']
        if dia:
            por_dia[dia.day] = float(fila['total'] or 0)
    dias_labels = [f'{d:02d}' for d in range(1, hoy.day + 1)]
    dias_values = [int(por_dia.get(d, 0)) for d in range(1, hoy.day + 1)]
    _meses_es = (
        '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
    )
    mes_activo_label = f'{_meses_es[hoy.month]} {hoy.year}'

    tipos_dte_grafico = {
        '33': 'Facturas', '34': 'Facturas',
        '39': 'Boletas', '41': 'Boletas',
        '52': 'Guías', '56': 'Notas de débito', '61': 'Notas de crédito',
    }
    tipos_venta_grafico = {
        'boleta': 'Boletas', 'boleta_electronica': 'Boletas',
        'factura': 'Facturas', 'factura_electronica': 'Facturas',
        'vale': 'Vales', 'guia': 'Guías', 'cotizacion': 'Cotizaciones',
    }
    tipos_hoy = {}
    for doc in documentos_hoy.select_related('venta_final', 'dte_generado'):
        dte = doc.dte_generado
        if dte:
            etiqueta = tipos_dte_grafico.get(str(dte.tipo_dte))
        else:
            etiqueta = None
        if not etiqueta:
            venta = doc.venta_final
            codigo = (getattr(venta, 'tipo_documento', None) or '')
            if codigo == 'ticket':
                codigo = getattr(venta, 'tipo_documento_planeado', None) or 'boleta'
            etiqueta = tipos_venta_grafico.get(codigo, 'Boletas')
        acc = tipos_hoy.setdefault(etiqueta, {'n': 0, 'total': Decimal('0')})
        acc['n'] += 1
        acc['total'] += getattr(doc.venta_final, 'total', None) or Decimal('0')
    tipos_labels = list(tipos_hoy.keys()) or ['Sin datos']
    tipos_values = [int(tipos_hoy[k]['total']) for k in tipos_hoy] or [0]

    cola_qs = ColaImpresion.objects.filter(
        empresa=request.empresa,
        estado__in=['pendiente', 'imprimiendo', 'error'],
    )
    if sucursal:
        cola_qs = cola_qs.filter(caja__sucursal=sucursal)

    total_recaudado = Decimal('0.00')
    efectivo = tarjeta = transferencia = Decimal('0.00')
    turno_duracion = ''
    if apertura_activa:
        apertura_activa.calcular_totales()
        efectivo = apertura_activa.total_ventas_efectivo or Decimal('0.00')
        tarjeta = apertura_activa.total_ventas_tarjeta or Decimal('0.00')
        transferencia = apertura_activa.total_ventas_transferencia or Decimal('0.00')
        total_recaudado = (
            efectivo + tarjeta + transferencia
            + (apertura_activa.total_ventas_cheque or Decimal('0.00'))
        )
        segundos = max(0, int((timezone.now() - apertura_activa.fecha_apertura).total_seconds()))
        horas, resto = divmod(segundos, 3600)
        minutos = resto // 60
        turno_duracion = f'{horas} h {minutos:02d} min' if horas else f'{minutos} min'

    mix_total = efectivo + tarjeta + transferencia
    def _pct(parte):
        if not mix_total:
            return 0
        return int(round((parte / mix_total) * 100))

    ahora = timezone.localtime()
    hora = ahora.hour
    if hora < 12:
        saludo = 'Buenos días'
    elif hora < 20:
        saludo = 'Buenas tardes'
    else:
        saludo = 'Buenas noches'

    nombre = (request.user.first_name or '').strip() or request.user.username
    bodegas_rebaja, bodega_rebaja = bodegas_para_rebaja(
        request, sucursal=sucursal, caja=getattr(apertura_activa, 'caja', None)
    )

    context = {
        'apertura_activa': apertura_activa,
        'sucursal_caja': sucursal,
        'total_recaudado': total_recaudado,
        'efectivo_turno': efectivo,
        'tarjeta_turno': tarjeta,
        'transferencia_turno': transferencia,
        'pct_efectivo': _pct(efectivo),
        'pct_tarjeta': _pct(tarjeta),
        'pct_transferencia': _pct(transferencia),
        'turno_duracion': turno_duracion,
        'saludo': saludo,
        'nombre_cajero': nombre,
        'tickets_count': tickets_count,
        'tickets_monto': tickets_monto,
        'documentos_recientes': documentos_recientes,
        'ver_todas_ventas': ver_todas_ventas,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'docs_rango_count': docs_rango_count,
        'total_rango': total_rango,
        'rango_varios_dias': fecha_desde != fecha_hasta,
        'q_reimp': q_reimp,
        'docs_hoy_count': docs_hoy_count,
        'cobrado_hoy': cobrado_hoy,
        'ticket_promedio': ticket_promedio,
        'cobrado_ayer': cobrado_ayer,
        'vs_ayer_pct': vs_ayer_pct,
        'horas_labels_json': json.dumps(horas_labels),
        'horas_values_json': json.dumps(horas_values),
        'tipos_labels_json': json.dumps(tipos_labels),
        'tipos_values_json': json.dumps(tipos_values),
        'mix_json': json.dumps([int(efectivo), int(tarjeta), int(transferencia)]),
        'dias_labels_json': json.dumps(dias_labels),
        'dias_values_json': json.dumps(dias_values),
        'mes_activo_label': mes_activo_label,
        'impresora_ok': agente_impresion_en_linea(request.empresa, sucursal),
        'cola_impresion_count': cola_qs.count(),
        'bodegas_dashboard': bodegas_rebaja,
        'bodega_seleccionada': bodega_rebaja,
    }
    return render(request, 'dashboard_cajero.html', context)
