"""Asistente de la empresa: responde con datos reales, sin IA externa."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone


def _pesos(valor):
    try:
        n = int(round(float(valor or 0)))
    except (TypeError, ValueError):
        n = 0
    return f"${n:,}".replace(",", ".")


def _hoy():
    return timezone.localdate()


def snapshot_empresa(empresa, sucursal=None):
    """Números del dueño para el resumen y el asistente."""
    from caja.impresion_utils import agente_impresion_en_linea
    from caja.models import AperturaCaja
    from facturacion_electronica.models import DocumentoTributarioElectronico
    from inventario.models import Stock
    from tesoreria.models import DocumentoCliente
    from ventas.models import Venta

    hoy = _hoy()
    ayer = hoy - timedelta(days=1)
    inicio_mes = hoy.replace(day=1)

    ventas = Venta.objects.filter(empresa=empresa, estado="confirmada")
    if sucursal is not None:
        ventas = ventas.filter(sucursal=sucursal)

    def _total(qs):
        return qs.aggregate(t=Sum("total"))["t"] or Decimal("0")

    def _cant(qs):
        return qs.count()

    ventas_hoy_qs = ventas.filter(fecha=hoy)
    ventas_ayer_qs = ventas.filter(fecha=ayer)
    ventas_mes_qs = ventas.filter(fecha__gte=inicio_mes)

    cobrar = DocumentoCliente.objects.filter(
        empresa=empresa,
        estado_pago__in=["pendiente", "parcial", "vencido"],
    )
    vencidos = cobrar.filter(estado_pago="vencido")
    from ventas.telefono_app import normalizar_telefono_cl
    from urllib.parse import quote

    deudores = []
    for d in (
        cobrar.values("cliente_id", "cliente__nombre", "cliente__telefono")
        .annotate(saldo=Sum("saldo_pendiente"))
        .filter(saldo__gt=0)
        .order_by("-saldo")[:5]
    ):
        tel = normalizar_telefono_cl(d.get("cliente__telefono"))
        nombre = d.get("cliente__nombre") or "Cliente"
        msg = quote(f"Hola {nombre}, le recordamos su saldo pendiente con {empresa.nombre}.")
        d["wa"] = f"https://wa.me/{tel}?text={msg}" if tel else ""
        deudores.append(d)

    from django.db.models import F

    stock_bajos = []
    try:
        qs_stock = Stock.objects.filter(
            empresa=empresa, articulo__activo=True, articulo__control_stock=True, stock_minimo__gt=0
        ).select_related("articulo").filter(cantidad__lte=F("stock_minimo"))
        if sucursal is not None:
            qs_stock = qs_stock.filter(bodega__sucursal=sucursal)
        for fila in qs_stock[:8]:
            stock_bajos.append({
                "nombre": fila.articulo.nombre,
                "cantidad": fila.cantidad,
                "minimo": fila.stock_minimo,
            })
    except Exception:
        stock_bajos = []

    dtes = DocumentoTributarioElectronico.objects.filter(empresa=empresa)
    dte_rechazados = dtes.filter(estado_sii__in=["rechazado", "error_envio", "error"]).count()
    dte_pendientes = dtes.filter(estado_sii__in=["pendiente", "enviado", ""]).count()

    caja_abierta = (
        AperturaCaja.objects.filter(caja__empresa=empresa, estado="abierta")
        .select_related("caja")
        .order_by("-fecha_apertura")
        .first()
    )
    impresora_ok = agente_impresion_en_linea(empresa, sucursal)

    return {
        "hoy": hoy,
        "ventas_hoy": _total(ventas_hoy_qs),
        "cant_hoy": _cant(ventas_hoy_qs),
        "ventas_ayer": _total(ventas_ayer_qs),
        "cant_ayer": _cant(ventas_ayer_qs),
        "ventas_mes": _total(ventas_mes_qs),
        "cant_mes": _cant(ventas_mes_qs),
        "por_cobrar": cobrar.aggregate(t=Sum("saldo_pendiente"))["t"] or Decimal("0"),
        "docs_vencidos": vencidos.count(),
        "deudores": deudores,
        "stock_bajos": stock_bajos,
        "dte_rechazados": dte_rechazados,
        "dte_pendientes": dte_pendientes,
        "caja_abierta": caja_abierta.caja.nombre if caja_abierta else "",
        "impresora_ok": impresora_ok,
        "empresa": empresa.nombre,
    }


def responder(pregunta, empresa, sucursal=None):
    texto = (pregunta or "").strip()
    if not texto:
        return {
            "respuesta": "Pregunte por ventas, deudas, stock o el SII. Ejemplo: ¿cuánto vendí hoy?",
            "sugerencias": ["¿cuánto vendí hoy?", "¿quién me debe?", "¿qué stock está bajo?", "¿hay DTE rechazados?"],
        }

    snap = snapshot_empresa(empresa, sucursal)
    q = texto.lower()

    if any(p in q for p in ("vendí", "vendi", "venta", "vendimos", "caja del día", "caja del dia")):
        if "ayer" in q:
            return {
                "respuesta": (
                    f"Ayer {snap['empresa']} vendió {_pesos(snap['ventas_ayer'])} "
                    f"en {snap['cant_ayer']} documentos."
                ),
                "sugerencias": ["¿cuánto vendí hoy?", "¿cuánto voy este mes?"],
            }
        if "mes" in q:
            return {
                "respuesta": (
                    f"Este mes lleva {_pesos(snap['ventas_mes'])} "
                    f"en {snap['cant_mes']} documentos."
                ),
                "sugerencias": ["¿cuánto vendí hoy?", "¿quién me debe?"],
            }
        return {
            "respuesta": (
                f"Hoy {snap['empresa']} lleva {_pesos(snap['ventas_hoy'])} "
                f"en {snap['cant_hoy']} documentos. Ayer fueron {_pesos(snap['ventas_ayer'])}."
            ),
            "sugerencias": ["¿cuánto voy este mes?", "¿quién me debe?"],
        }

    if any(p in q for p in ("debe", "deuda", "cobrar", "vencid", "cuenta corriente")):
        lineas = [
            f"Hay {_pesos(snap['por_cobrar'])} por cobrar"
            + (f" y {snap['docs_vencidos']} documentos vencidos." if snap["docs_vencidos"] else ".")
        ]
        if snap["deudores"]:
            lineas.append("Los que más deben:")
            for d in snap["deudores"]:
                lineas.append(f"· {d['cliente__nombre']}: {_pesos(d['saldo'])}")
        else:
            lineas.append("Nadie tiene saldo pendiente.")
        return {"respuesta": "\n".join(lineas), "sugerencias": ["¿cuánto vendí hoy?", "¿qué stock está bajo?"]}

    if any(p in q for p in ("stock", "inventario", "falt", "mínimo", "minimo", "acab")):
        if not snap["stock_bajos"]:
            return {
                "respuesta": "No hay artículos bajo el mínimo (o no tienen mínimo cargado).",
                "sugerencias": ["¿cuánto vendí hoy?", "¿quién me debe?"],
            }
        lineas = ["Estos van justos o bajo el mínimo:"]
        for s in snap["stock_bajos"]:
            lineas.append(f"· {s['nombre']}: {s['cantidad']} (mínimo {s['minimo']})")
        return {"respuesta": "\n".join(lineas), "sugerencias": ["¿quién me debe?", "¿hay DTE rechazados?"]}

    if any(p in q for p in ("sii", "dte", "rechaz", "boleta", "factura")):
        return {
            "respuesta": (
                f"DTE con problema: {snap['dte_rechazados']}. "
                f"Pendientes o en envío: {snap['dte_pendientes']}. "
                "Si hay rechazo, ábralo en Facturación y lea el detalle del SII."
            ),
            "sugerencias": ["¿cuánto vendí hoy?", "¿la impresora está en línea?"],
        }

    if any(p in q for p in ("impresora", "imprime", "agente")):
        if snap["impresora_ok"]:
            return {
                "respuesta": "La impresora está en línea. No hay que configurar de nuevo.",
                "sugerencias": ["¿cuánto vendí hoy?"],
            }
        return {
            "respuesta": "La impresora no está en línea. Abra Impresora GestionCloud en el computador. No configure de nuevo.",
            "sugerencias": ["¿está la caja abierta?"],
        }

    if any(p in q for p in ("caja abierta", "apertura", "turno")):
        if snap["caja_abierta"]:
            return {
                "respuesta": f"Hay caja abierta: {snap['caja_abierta']}.",
                "sugerencias": ["¿cuánto vendí hoy?", "¿la impresora está en línea?"],
            }
        return {
            "respuesta": "No hay caja abierta en este momento.",
            "sugerencias": ["¿cuánto vendí hoy?"],
        }

    if any(p in q for p in ("ayuda", "qué puedo", "que puedo", "hola", "buenas")):
        return {
            "respuesta": (
                f"Soy el asistente de {snap['empresa']}. Pregunte en castellano, por ejemplo:\n"
                "· ¿cuánto vendí hoy / ayer / este mes?\n"
                "· ¿quién me debe?\n"
                "· ¿qué stock está bajo?\n"
                "· ¿hay DTE rechazados?\n"
                "· ¿la impresora está en línea?"
            ),
            "sugerencias": ["¿cuánto vendí hoy?", "¿quién me debe?", "¿qué stock está bajo?"],
        }

    return {
        "respuesta": (
            f"Hoy lleva {_pesos(snap['ventas_hoy'])}. "
            f"Por cobrar: {_pesos(snap['por_cobrar'])}. "
            "Puede preguntar por ventas, deudas, stock, SII o la impresora."
        ),
        "sugerencias": ["¿cuánto vendí hoy?", "¿quién me debe?", "¿qué stock está bajo?", "¿hay DTE rechazados?"],
    }
