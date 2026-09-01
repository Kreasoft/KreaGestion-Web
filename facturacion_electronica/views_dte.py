"""
Vistas para generación y gestión de DTE
"""
import logging
import os
import re
import traceback
from io import BytesIO
from urllib.parse import urlencode, unquote, urlparse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import datetime
from core.decorators import requiere_empresa
from .models import DocumentoTributarioElectronico
from .dte_service import DTEService, normalizar_error_envio_sii
from .lineas_dte import obtener_lineas_dte
from ventas.models import Venta, NotaCredito
from clientes.models import Cliente

logger = logging.getLogger(__name__)

# Importar OrdenDespacho si existe (puede no estar disponible en todos los proyectos)
try:
    from pedidos.models import OrdenDespacho
except ImportError:
    OrdenDespacho = None


def redirect_to_dte_list(request, anchor=None, dte=None):
    """
    Redirige a la lista de DTEs, manteniendo los filtros de búsqueda si existen
    """
    from django.urls import reverse
    
    url = request.POST.get('return_url') or request.GET.get('return_url')
    
    if not url:
        # Intentar obtener del referer si no hay return_url
        referer = request.META.get('HTTP_REFERER')
        if referer:
            # Evitar bucles si el referer es la misma página de acción o el detalle del documento
            excluded_patterns = [
                '/enviar/', '/enviar-email/', '/consultar-estado/', '/consultar-estados/',
                '/sincronizar-pendientes/', '/descargar-pdf/',
                '/descargar-xml/', '/regenerar-xml/', '/ver-factura/',
                '/ver-notacredito/', '/ver-notadebito/', '/dte/'
            ]
            if not any(x in referer for x in excluded_patterns):
                url = referer

    if not url:
        # Fallback inteligente según el tipo de DTE
        if dte and dte.tipo_dte == '52':
            url = reverse('ventas:libro_guias')
        elif dte and str(dte.tipo_dte) in {'33', '34', '39', '41', '56', '61'}:
            url = reverse('ventas:libro_ventas')
        else:
            url = reverse('facturacion_electronica:dte_list')
            
        # Limpiar query_string de return_url para no ensuciar la URL final
        params = request.GET.copy()
        if 'return_url' in params:
            del params['return_url']
        query_string = params.urlencode()
        if query_string:
            if '?' in url:
                url += '&' + query_string
            else:
                url += '?' + query_string
    
    if anchor:
        if '#' in url:
            url = url.split('#')[0]
        url += f'#{anchor}'
        
    return redirect(url)


def _attr_texto(obj, name):
    if obj is None:
        return ''
    val = getattr(obj, name, None)
    if val is None:
        return ''
    return str(val).strip()


def _build_receptor_display(dte=None, fallback_cliente=None):
    """Unifica los datos del receptor usando cliente y DTE como respaldo."""
    class ReceptorDisplay:
        def __init__(self, dte, fallback_cliente=None):
            self.nombre = (
                _attr_texto(fallback_cliente, 'nombre')
                or _attr_texto(dte, 'razon_social_receptor')
                or 'Cliente General'
            )
            self.rut = _attr_texto(fallback_cliente, 'rut') or _attr_texto(dte, 'rut_receptor')
            self.giro = _attr_texto(fallback_cliente, 'giro') or _attr_texto(dte, 'giro_receptor')
            self.direccion = _attr_texto(fallback_cliente, 'direccion') or _attr_texto(dte, 'direccion_receptor')
            self.comuna = _attr_texto(fallback_cliente, 'comuna') or _attr_texto(dte, 'comuna_receptor')
            self.ciudad = _attr_texto(fallback_cliente, 'ciudad') or _attr_texto(dte, 'ciudad_receptor')
            self.telefono = _attr_texto(fallback_cliente, 'telefono')
            self.email = _attr_texto(fallback_cliente, 'email')

    return ReceptorDisplay(dte, fallback_cliente=fallback_cliente)


def _format_bodega_display(bodega):
    if not bodega:
        return ''
    nombre = _attr_texto(bodega, 'nombre') or str(bodega)
    codigo = _attr_texto(bodega, 'codigo')
    if codigo and nombre:
        return f'{nombre} ({codigo})'
    return nombre or codigo


def resolver_bodega_documento(venta=None, dte=None):
    """Resuelve la bodega de origen para imprimirla en guía/factura térmica."""
    bodega = getattr(venta, 'bodega', None)
    if bodega:
        return _format_bodega_display(bodega)

    try:
        from caja.models import VentaProcesada
        qs = VentaProcesada.objects.select_related('apertura_caja__caja__bodega')
        vp = None
        venta_id = getattr(venta, 'pk', None) or getattr(venta, 'id', None)
        if venta_id:
            vp = qs.filter(venta_final_id=venta_id).first()
        if not vp and dte is not None:
            vp = qs.filter(dte_generado=dte).first()
            venta_dte_id = getattr(dte, 'venta_id', None)
            if not vp and venta_dte_id:
                vp = qs.filter(venta_final_id=venta_dte_id).first()
        caja = getattr(getattr(vp, 'apertura_caja', None), 'caja', None) if vp else None
        if caja and getattr(caja, 'bodega', None):
            return _format_bodega_display(caja.bodega)
    except Exception:
        pass

    try:
        orden_pedido = getattr(venta, 'orden_pedido', None)
        if orden_pedido and getattr(orden_pedido, 'bodega', None):
            return _format_bodega_display(orden_pedido.bodega)
        if dte is not None and hasattr(dte, 'orden_despacho'):
            od = dte.orden_despacho.select_related('orden_pedido__bodega').first()
            if od and getattr(od, 'orden_pedido', None) and od.orden_pedido.bodega:
                return _format_bodega_display(od.orden_pedido.bodega)
    except Exception:
        pass

    try:
        if dte is not None and hasattr(dte, 'transferencias'):
            transf = dte.transferencias.select_related('bodega_origen').first()
            if transf and getattr(transf, 'bodega_origen', None):
                return _format_bodega_display(transf.bodega_origen)
    except Exception:
        pass

    try:
        from caja.models import Caja
        from bodegas.models import Bodega

        empresa = getattr(venta, 'empresa', None) or getattr(dte, 'empresa', None)
        estacion = getattr(venta, 'estacion_trabajo', None)
        sucursal = getattr(venta, 'sucursal', None) or getattr(estacion, 'sucursal', None)
        if empresa and estacion:
            caja = Caja.objects.filter(
                empresa=empresa, estacion_trabajo=estacion, activo=True
            ).select_related('bodega').first()
            if caja and caja.bodega:
                return _format_bodega_display(caja.bodega)
        if empresa and sucursal:
            caja = Caja.objects.filter(
                empresa=empresa, sucursal=sucursal, estacion_trabajo__isnull=True, activo=True
            ).select_related('bodega').first()
            if caja and caja.bodega:
                return _format_bodega_display(caja.bodega)
        if empresa:
            qs = Bodega.objects.filter(empresa=empresa, activa=True)
            if sucursal:
                suc_qs = qs.filter(Q(sucursal=sucursal) | Q(sucursal__isnull=True))
                if suc_qs.exists():
                    qs = suc_qs
            bodega = qs.order_by('nombre').first()
            if bodega:
                return _format_bodega_display(bodega)
    except Exception:
        pass

    return ''


@login_required
@requiere_empresa
def generar_dte_venta(request, venta_id):
    """
    Genera un DTE a partir de una venta
    """
    venta = get_object_or_404(Venta, pk=venta_id, empresa=request.empresa)
    
    # Verificar que la venta no tenga ya un DTE
    if hasattr(venta, 'dte'):
        messages.warning(request, 'Esta venta ya tiene un DTE generado.')
        return redirect('ventas:detalle_venta', pk=venta_id)
    
    # Verificar que la empresa tenga FE activada
    if not request.empresa.facturacion_electronica:
        messages.error(request, 'La facturación electrónica no está activada para esta empresa.')
        return redirect('ventas:detalle_venta', pk=venta_id)
    
    if request.method == 'POST':
        tipo_dte = request.POST.get('tipo_dte', '39')  # Por defecto Boleta
        
        # Capturar datos de transporte para Guías de Despacho
        transport_data = {}
        if tipo_dte == '52':
            transport_data = {
                'patente_transporte': request.POST.get('patente_transporte'),
                'rut_transportista': request.POST.get('rut_transportista'),
                'nombre_chofer': request.POST.get('nombre_chofer'),
            }
        
        try:
            # Inicializar servicio de DTE
            dte_service = DTEService(request.empresa)
            
            # Generar el DTE
            dte = dte_service.generar_dte_desde_venta(venta, tipo_dte, **transport_data)
            
            messages.success(
                request,
                f'DTE generado exitosamente: {dte.get_tipo_dte_display()} N° {dte.folio}'
            )
            
            # Preguntar si desea enviar al SII
            if request.POST.get('enviar_sii') == 'true':
                return redirect('facturacion_electronica:enviar_dte', dte_id=dte.id)
            else:
                return redirect('facturacion_electronica:dte_detail', pk=dte.id)
            
        except ValueError as e:
            messages.error(request, f'Error al generar DTE: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error al generar DTE: {normalizar_error_envio_sii(e)}')
            import traceback
            traceback.print_exc()
    
    # Mostrar formulario para seleccionar tipo de DTE
    context = {
        'venta': venta,
        'tipos_dte': [
            ('33', 'Factura Electrónica'),
            ('39', 'Boleta Electrónica'),
            ('52', 'Guía de Despacho Electrónica'),
        ]
    }
    
    return render(request, 'facturacion_electronica/generar_dte_form.html', context)


@login_required
@requiere_empresa
def enviar_dte_sii(request, dte_id):
    """
    Encola el DTE para envío al SII en segundo plano (no bloquea la página).
    """
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=dte_id, empresa=request.empresa)

    if dte.tiene_track_sii and not dte.permite_reenvio_xml_corregido:
        messages.warning(
            request,
            f'El folio {dte.folio} ya tiene Track {dte.track_id_efectivo()}. '
            'Use Consultar SII. Reenviar el mismo archivo es riesgoso.'
        )
        return redirect_to_dte_list(request, anchor=f'row-{dte.id}', dte=dte)

    if dte.en_espera_reintento_sii() and not dte.permite_reenvio_xml_corregido:
        messages.warning(request, dte.get_mensaje_espera_reintento())
        return redirect_to_dte_list(request, anchor=f'row-{dte.id}', dte=dte)

    if not dte.puede_enviarse_al_sii and not dte.permite_reenvio_xml_corregido:
        if dte.estado_sii in ['enviado', 'enviando'] and str(dte.track_id or '').strip():
            messages.warning(request, 'Este DTE ya fue enviado al SII y está pendiente de respuesta.')
        else:
            messages.warning(request, 'Este DTE no está disponible para reenvío al SII.')
        return redirect_to_dte_list(request, anchor=f'row-{dte.id}', dte=dte)

    if dte.permite_reenvio_xml_corregido:
        servicio = DTEService(request.empresa)
        try:
            servicio.procesar_dte_existente(dte)
            dte.refresh_from_db()
            envio = servicio.enviar_dte_al_sii(dte)
        except Exception as exc:
            messages.error(request, f'No se pudo subir el XML del folio {dte.folio}: {exc}')
            return redirect_to_dte_list(request, anchor=f'row-{dte.id}', dte=dte)
        if envio.get('success'):
            track = envio.get('track_id') or dte.track_id_efectivo()
            messages.success(
                request,
                f'Folio {dte.folio} subido de nuevo (mismo folio). Track {track or "-"}. Pulse Consultar SII.'
            )
        else:
            messages.error(
                request,
                f'El SII no aceptó el XML del folio {dte.folio}: {envio.get("message") or "sin detalle"}.'
            )
        return redirect_to_dte_list(request, anchor=f'row-{dte.id}', dte=dte)

    servicio = DTEService(request.empresa)
    try:
        envio = servicio.enviar_dte_al_sii(dte)
    except Exception as exc:
        messages.error(request, f'El SII no recibió el folio {dte.folio}: {exc}')
        return redirect_to_dte_list(request, anchor=f'row-{dte.id}', dte=dte)
    dte.refresh_from_db()
    track = envio.get('track_id') or dte.track_id_efectivo()
    if envio.get('success') or track:
        messages.success(
            request,
            f'Folio {dte.folio} enviado al SII. Track {track or "-"}.'
        )
    else:
        messages.error(
            request,
            f'El SII no confirmó el folio {dte.folio}: {envio.get("message") or envio.get("error") or "sin detalle"}.'
        )
    return redirect_to_dte_list(request, anchor=f'row-{dte.id}', dte=dte)




@login_required
@requiere_empresa
def consultar_estado_dte(request, dte_id):
    """
    Consulta el estado de un DTE en el SII
    """
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=dte_id, empresa=request.empresa)
    
    if not dte.tiene_track_sii:
        messages.error(request, 'Este DTE no tiene Track ID. Debe ser enviado al SII primero.')
        return redirect('facturacion_electronica:dte_detail', pk=dte_id)
    if not str(dte.track_id or '').strip():
        dte.track_id = dte.track_id_efectivo()
        dte.save(update_fields=['track_id'])
    
    try:
        # Inicializar servicio
        dte_service = DTEService(request.empresa)
        
        estado = dte_service.consultar_estado_dte(dte)
        dte.refresh_from_db()
        estado_real = dte.get_estado_sii_real()
        etiqueta = dte.get_estado_sii_real_display()
        glosa = (estado.get('glosa') or dte.glosa_sii or '').strip()
        detalle = str(estado.get('detalle_estado') or '').strip().upper()
        recibido_sin_resolucion = estado_real == 'enviado' and (
            detalle == 'DOK' or 'DTE RECIBIDO' in glosa.upper()
        )
        if recibido_sin_resolucion:
            messages.info(
                request,
                'El SII recibió el documento (DOK). Aún no informa si fue aceptado o rechazado.'
            )
        elif estado_real == 'rechazado':
            messages.error(request, f'{etiqueta}: {glosa}' if glosa else etiqueta)
        elif estado_real == 'aceptado_reparos':
            messages.warning(request, f'{etiqueta}: {glosa}' if glosa else etiqueta)
        elif glosa:
            messages.success(request, f'{etiqueta}: {glosa}')
        else:
            messages.success(
                request,
                f'Estado SII: {etiqueta} ({estado.get("estado") or "-"})'
            )
        
    except Exception as e:
        messages.error(request, f'Error al consultar estado: {str(e)}')
        import traceback
        traceback.print_exc()
    
    return redirect_to_dte_list(request, anchor=f'row-{dte.id}', dte=dte)


def _safe_internal_url(url, fallback):
    """Acepta solo rutas internas relativas para volver al listado."""
    if not url:
        return fallback
    raw = str(url).strip()
    if raw.startswith('/') and not raw.startswith('//'):
        return raw
    return fallback


def _email_receptor_dte(dte):
    """Correo del receptor: venta, nota o pedido de despacho."""
    venta = getattr(dte, 'venta', None)
    cliente = getattr(venta, 'cliente', None) if venta else None
    email = _attr_texto(cliente, 'email')
    if email:
        return email
    for related in ('notas_credito', 'notas_debito'):
        try:
            nota = getattr(dte, related).select_related('cliente').first()
        except Exception:
            nota = None
        email = _attr_texto(getattr(nota, 'cliente', None), 'email')
        if email:
            return email
    for related in ('detalles_despacho_guia', 'detalles_despacho_factura'):
        try:
            detalle = getattr(dte, related).select_related(
                'orden_despacho__orden_pedido__cliente'
            ).first()
        except Exception:
            detalle = None
        pedido = getattr(getattr(detalle, 'orden_despacho', None), 'orden_pedido', None)
        email = _attr_texto(getattr(pedido, 'cliente', None), 'email')
        if email:
            return email
    return ''


def _xml_dte_bytes(dte):
    """XML firmado (o sin firmar) listo para adjuntar al correo."""
    xml = (dte.xml_firmado or dte.xml_dte or '').strip()
    if not xml:
        return None
    if isinstance(xml, bytes):
        return xml
    encoding = 'utf-8'
    decl = re.search(r'encoding=["\']([^"\']+)["\']', xml[:220], re.IGNORECASE)
    if decl:
        encoding = decl.group(1).strip() or encoding
    try:
        return xml.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return xml.encode('utf-8', errors='replace')


def url_copia_impresa(dte):
    """URL del visor imprimible según el tipo de DTE."""
    try:
        if dte.tipo_dte == '52':
            transferencia = dte.transferencias.first()
            if transferencia:
                return reverse('inventario:transferencia_imprimir_guia', args=[transferencia.pk])
        if dte.tipo_dte == '61':
            nota = dte.notas_credito.first()
            if nota:
                return reverse('facturacion_electronica:ver_notacredito_electronica', args=[nota.pk])
        if dte.tipo_dte == '56':
            nota = dte.notas_debito.first()
            if nota:
                return reverse('facturacion_electronica:ver_notadebito_electronica', args=[nota.pk])
    except Exception:
        logger.exception('url_copia_impresa DTE %s', getattr(dte, 'pk', None))
    return reverse('facturacion_electronica:ver_factura_electronica', args=[dte.pk])


def _tipo_impresora_dte(empresa, dte):
    tipo = str(getattr(dte, 'tipo_dte', '') or '')
    if tipo in {'33', '34'}:
        return getattr(empresa, 'impresora_factura', 'laser') or 'laser'
    if tipo in {'39', '41'}:
        return getattr(empresa, 'impresora_boleta', 'laser') or 'laser'
    if tipo == '52':
        return getattr(empresa, 'impresora_guia', 'laser') or 'laser'
    if tipo == '61':
        return getattr(empresa, 'impresora_nota_credito', 'laser') or 'laser'
    if tipo == '56':
        return getattr(empresa, 'impresora_nota_debito', 'laser') or 'laser'
    return 'laser'


def n_copias_impresion(empresa, dte=None, estacion=None, tipo_slug=None, request=None):
    """Estación (POS) si existe; si no, copias de la empresa. PDF fuerza 1."""
    if request is not None and str(request.GET.get('pdf') or '') == '1':
        return 1
    slug = tipo_slug
    if not slug and dte is not None:
        slug = dte.get_tipo_slug()
    slug = str(slug or 'guia').strip().lower()
    if estacion is not None:
        try:
            n = int(estacion.get_copias_por_tipo(slug) or 0)
            if n:
                return max(1, min(10, n))
        except Exception:
            pass
    if empresa is not None and hasattr(empresa, 'get_copias_impresion'):
        return empresa.get_copias_impresion(slug)
    return 1


def _pdf_link_callback(uri, rel):
    """Resuelve /media y /static a rutas de archivo para xhtml2pdf."""
    from django.conf import settings
    from django.contrib.staticfiles import finders

    raw = unquote(str(uri or '').strip())
    if not raw or raw.startswith('data:'):
        return raw
    if os.path.exists(raw):
        return raw

    path = urlparse(raw).path or raw
    media_url = settings.MEDIA_URL or '/media/'
    static_url = settings.STATIC_URL or '/static/'

    if path.startswith(media_url):
        rel_path = path[len(media_url):].lstrip('/').replace('/', os.sep)
        full = os.path.join(settings.MEDIA_ROOT, rel_path)
        return full if os.path.exists(full) else raw

    if path.startswith(static_url):
        rel_path = path[len(static_url):].lstrip('/')
        found = finders.find(rel_path)
        return found or raw

    if path.startswith('/'):
        candidate = os.path.join(settings.MEDIA_ROOT, path.lstrip('/').replace('/', os.sep))
        if os.path.exists(candidate):
            return candidate
    return raw


def _html_tributario_a_pdf(html, tipo_impresora):
    """Convierte la copia oficial (láser/térmica) a PDF."""
    from xhtml2pdf import pisa

    tipo = str(tipo_impresora or 'laser').lower()
    if tipo == 'termica_58':
        pagina = '@page { size: 58mm 260mm; margin: 2mm; }'
    elif tipo in {'termica_80', 'termica'}:
        pagina = '@page { size: 80mm 280mm; margin: 2mm; }'
    else:
        pagina = '@page { size: A4; margin: 10mm; }'

    html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'@page\s*\{[^}]*\}', '', html)
    extra_css = (
        f'<style>{pagina}'
        '.no-print, .no-print * { display: none !important; }'
        '.header, .header *, .document-meta, .company-name, .company-info { border: 0 !important; }'
        'table.sii-id-box, table.sii-id-box td { border-collapse: collapse; }'
        'table.sii-id-box { border: 2px solid #000 !important; }'
        'table.sii-id-box td { border: 0 !important; }'
        '</style>'
    )
    if '</head>' in html.lower():
        html = re.sub(r'</head>', extra_css + '</head>', html, count=1, flags=re.IGNORECASE)
    else:
        html = extra_css + html

    buffer = BytesIO()
    resultado = pisa.CreatePDF(
        src=html,
        dest=buffer,
        encoding='utf-8',
        link_callback=_pdf_link_callback,
    )
    if resultado.err:
        logger.warning('xhtml2pdf reportó %s avisos al generar PDF tributario', resultado.err)
    pdf = buffer.getvalue()
    if not pdf.startswith(b'%PDF'):
        raise ValueError('El PDF generado no es válido')
    return pdf


def _respuesta_copia_oficial(request, dte):
    """Renderiza la misma copia tributaria usada al imprimir."""
    if dte.tipo_dte == '52':
        transferencia = dte.transferencias.first()
        if transferencia:
            from inventario.views_transferencias import transferencia_imprimir_guia
            return transferencia_imprimir_guia(request, transferencia.pk)
    if dte.tipo_dte == '61':
        nota = dte.notas_credito.first()
        if nota:
            return ver_notacredito_electronica(request, nota.pk)
    if dte.tipo_dte == '56':
        nota = dte.notas_debito.first()
        if nota:
            return ver_notadebito_electronica(request, nota.pk)
    return ver_factura_electronica(request, dte.pk)


def _dte_detail_es_partial(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.GET.get('partial') == '1'
    )


def _dte_detail_error_response(request, dte, exc, is_partial):
    """HTML útil con status 200 para que el modal no quede en un error opaco."""
    tb = traceback.format_exc()
    logger.exception('dte_detail fallo DTE %s: %s', getattr(dte, 'pk', None), exc)
    try:
        estado = dte.get_estado_sii_real_display() if dte else '-'
    except Exception:
        estado = getattr(dte, 'estado_sii', None) or '-'
    context = {
        'dte': dte,
        'folio': getattr(dte, 'folio', '-'),
        'tipo': '',
        'track_id': getattr(dte, 'track_id', '') or '',
        'estado': estado,
        'glosa': (getattr(dte, 'glosa_sii', None) or getattr(dte, 'error_envio', None) or '').strip(),
        'mensaje_tecnico': f'{exc.__class__.__name__}: {exc}',
        'traceback_corto': (tb or '')[-1200:],
    }
    try:
        context['tipo'] = dte.get_tipo_dte_display() if dte else ''
    except Exception:
        context['tipo'] = str(getattr(dte, 'tipo_dte', '') or '')
    return render(
        request,
        'facturacion_electronica/_dte_detail_modal_error.html',
        context,
        status=200,
    )


@login_required
@requiere_empresa
def dte_detail(request, pk):
    """
    Detalle de un DTE con tracking SII y motivo de rechazo/reparos.
    El partial del modal nunca responde 500: si falla, entrega HTML de error.
    """
    is_partial = _dte_detail_es_partial(request)
    try:
        dte = get_object_or_404(
            DocumentoTributarioElectronico.objects.select_related(
                'venta', 'venta__cliente', 'empresa'
            ).prefetch_related(
                'notas_credito__items__articulo',
                'notas_debito__items__articulo',
                'transferencias__detalles__articulo',
                'venta__ventadetalle_set__articulo',
                'detalles_despacho_guia__item_pedido__articulo',
                'detalles_despacho_factura__item_pedido__articulo',
            ),
            pk=pk,
            empresa=request.empresa,
        )
    except Http404:
        raise
    except Exception as exc:
        if is_partial:
            logger.exception('dte_detail no pudo cargar DTE %s', pk)
            return _dte_detail_error_response(request, None, exc, True)
        raise

    try:
        dte.corregir_falso_rechazo_espera()
    except Exception:
        logger.exception('corregir_falso_rechazo_espera DTE %s', dte.pk)

    try:
        fallback = reverse('ventas:libro_guias') if dte.tipo_dte == '52' else reverse('facturacion_electronica:dte_list')
        fallback += f'#row-dte-{dte.id}'
        back_url = _safe_internal_url(request.GET.get('return_url'), fallback)

        try:
            estado_real = dte.get_estado_sii_real()
        except Exception:
            estado_real = str(dte.estado_sii or 'enviado')

        if is_partial:
            action_return = back_url
        else:
            action_return = reverse('facturacion_electronica:dte_detail', args=[dte.pk])
            if request.GET.get('return_url'):
                action_return += '?' + urlencode({'return_url': request.GET.get('return_url')})

        try:
            url_copia = url_copia_impresa(dte)
        except Exception:
            logger.exception('url_copia_impresa DTE %s', dte.pk)
            url_copia = reverse('facturacion_electronica:ver_factura_electronica', args=[dte.pk])

        try:
            lineas = obtener_lineas_dte(dte)
        except Exception:
            logger.exception('obtener_lineas_dte DTE %s', dte.pk)
            lineas = []

        try:
            email_receptor = _email_receptor_dte(dte)
        except Exception:
            email_receptor = ''

        try:
            tiene_xml = bool((dte.xml_firmado or dte.xml_dte or '').strip())
        except Exception:
            tiene_xml = False

        context = {
            'dte': dte,
            'back_url': back_url,
            'url_copia': url_copia,
            'estado_real': estado_real,
            'mostrar_motivo': estado_real in ('rechazado', 'aceptado_reparos') or bool((dte.glosa_sii or '').strip()),
            'tiene_xml': tiene_xml,
            'email_receptor': email_receptor,
            'detail_return_q': urlencode({'return_url': action_return}),
            'return_url_q': urlencode({'return_url': action_return}),
            'dte_modal_preload': True,
            'lineas_dte': lineas,
        }
        template = (
            'facturacion_electronica/_dte_detail_modal.html'
            if is_partial
            else 'facturacion_electronica/dte_detail.html'
        )
        return render(request, template, context)
    except Exception as exc:
        return _dte_detail_error_response(request, dte, exc, is_partial)


def _generar_pdf_tributario_bytes(request, dte):
    """Genera el PDF de la copia tributaria. Lanza ValueError si no se puede."""
    if not dte.puede_compartir_pdf_correo_whatsapp:
        raise ValueError(dte.get_mensaje_no_compartible())

    original_get = request.GET
    query = original_get.copy()
    query['pdf'] = '1'
    request.GET = query
    try:
        respuesta = _respuesta_copia_oficial(request, dte)
    finally:
        request.GET = original_get

    if respuesta.status_code >= 300:
        raise ValueError('No se pudo generar la copia tributaria del documento.')

    html = respuesta.content.decode(getattr(respuesta, 'charset', None) or 'utf-8', errors='replace')
    tipo_impresora = _tipo_impresora_dte(getattr(request, 'empresa', None) or dte.empresa, dte)
    return _html_tributario_a_pdf(html, tipo_impresora)


@login_required
@requiere_empresa
def descargar_xml_dte(request, dte_id):
    """Descarga el XML firmado (o el XML del DTE si aún no está firmado)."""
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=dte_id, empresa=request.empresa)
    xml = (dte.xml_firmado or dte.xml_dte or '').strip()
    if not xml:
        messages.error(request, 'Este documento no tiene XML disponible.')
        return redirect('facturacion_electronica:dte_detail', pk=dte.pk)

    xml_bytes = xml.encode('utf-8') if isinstance(xml, str) else xml
    response = HttpResponse(xml_bytes, content_type='application/xml; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="DTE_{dte.tipo_dte}_{dte.folio}.xml"'
    return response


@login_required
@requiere_empresa
def descargar_pdf_dte(request, dte_id):
    """Descarga el PDF de la copia tributaria (láser o térmica según configuración)."""
    dte = get_object_or_404(
        DocumentoTributarioElectronico.objects.select_related(
            'empresa', 'venta', 'caf_utilizado', 'vendedor'
        ).prefetch_related('notas_credito', 'notas_debito', 'transferencias'),
        pk=dte_id,
        empresa=request.empresa,
    )
    if not dte.puede_compartir_pdf_correo_whatsapp:
        messages.error(request, dte.get_mensaje_no_compartible())
        return redirect('facturacion_electronica:dte_detail', pk=dte.pk)

    try:
        pdf_bytes = _generar_pdf_tributario_bytes(request, dte)
    except Exception as exc:
        logger.exception('Error generando PDF tributario del DTE %s: %s', dte.pk, exc)
        messages.error(request, 'No se pudo generar el PDF del documento tributario.')
        return redirect('facturacion_electronica:dte_detail', pk=dte.pk)

    filename = f'DTE_{dte.tipo_dte}_{dte.folio}.pdf'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@requiere_empresa
def enviar_dte_email(request, dte_id):
    """Envía el DTE por correo con PDF tributario y XML adjuntos."""
    from django.core.exceptions import ValidationError
    from django.core.mail import EmailMessage
    from django.core.validators import validate_email

    dte = get_object_or_404(
        DocumentoTributarioElectronico.objects.select_related(
            'empresa', 'venta', 'venta__cliente', 'caf_utilizado', 'vendedor'
        ).prefetch_related('notas_credito', 'notas_debito', 'transferencias'),
        pk=dte_id,
        empresa=request.empresa,
    )
    destino = redirect_to_dte_list(request, anchor=f'row-{dte.id}', dte=dte)

    if request.method != 'POST':
        return destino

    if not dte.puede_compartir_pdf_correo_whatsapp:
        messages.error(request, dte.get_mensaje_no_compartible())
        return destino

    email = (request.POST.get('email') or '').strip() or _email_receptor_dte(dte)
    try:
        validate_email(email)
    except ValidationError:
        messages.error(request, 'Indique un correo válido para enviar el documento.')
        return destino

    from utilidades.utils import aviso_correo_no_entregado, conexion_correo, datos_smtp
    smtp = datos_smtp(dte.empresa)
    if not smtp['listo']:
        messages.error(request, aviso_correo_no_entregado(email))
        return destino

    xml_bytes = _xml_dte_bytes(dte)
    if not xml_bytes:
        messages.error(request, 'Este documento no tiene XML para enviar.')
        return destino

    try:
        pdf_bytes = _generar_pdf_tributario_bytes(request, dte)
    except Exception as exc:
        logger.exception('Error generando PDF para correo del DTE %s: %s', dte.pk, exc)
        messages.error(request, 'No se pudo generar el PDF del documento tributario.')
        return destino

    empresa = dte.empresa
    receptor = (dte.razon_social_receptor or '').strip() or 'Cliente'
    tipo = dte.get_tipo_dte_display()
    total = f"{int(round(float(dte.monto_total or 0))):,}".replace(',', '.')
    extra = (request.POST.get('mensaje') or '').strip()
    extra_txt = f"{extra}\n\n" if extra else ""
    cuerpo = (
        f"Estimado/a {receptor},\n\n"
        f"{extra_txt}"
        f"Adjuntamos {tipo} N° {dte.folio} de {empresa.nombre} (PDF y XML).\n"
        f"Total: ${total}\n\n"
        f"{empresa.nombre}\n"
        f"{empresa.telefono or ''}\n"
        f"{empresa.email or ''}\n"
    )
    copia = (empresa.email or '').strip()
    try:
        mensaje = EmailMessage(
            subject=f"{tipo} N° {dte.folio} — {empresa.nombre}",
            body=cuerpo,
            from_email=smtp['from_email'] or empresa.email,
            to=[email],
            cc=[copia] if copia and copia.lower() != email.lower() else None,
            connection=conexion_correo(empresa),
        )
        mensaje.attach(f'DTE_{dte.tipo_dte}_{dte.folio}.pdf', pdf_bytes, 'application/pdf')
        mensaje.attach(f'DTE_{dte.tipo_dte}_{dte.folio}.xml', xml_bytes, 'application/xml')
        mensaje.send(fail_silently=False)
    except Exception as exc:
        logger.exception('Error enviando correo del DTE %s: %s', dte.pk, exc)
        messages.error(request, f'No se pudo enviar el correo ({exc}).')
        return destino

    messages.success(request, f'{tipo} N° {dte.folio} enviado a {email}.')
    return destino


@login_required
@requiere_empresa
def _pide_copia_a4(request):
    formato = (request.GET.get('formato') or request.GET.get('vista') or '').strip().lower()
    if formato in ('a4', 'carta', 'laser', 'copia'):
        return True
    return_url = (request.GET.get('return_url') or '').lower()
    return 'cuenta-corriente' in return_url


def ver_factura_electronica(request, dte_id, forzar_a4=False):
    """
    Muestra la factura electrónica con el timbre
    """
    forzar_a4 = bool(forzar_a4) or _pide_copia_a4(request)
    # Optimizar el query de DTE con select_related y prefetch_related
    dte = get_object_or_404(
        DocumentoTributarioElectronico.objects.select_related(
            'empresa', 'venta', 'caf_utilizado', 'vendedor'
        ).prefetch_related('orden_despacho'), 
        pk=dte_id, empresa=request.empresa
    )

    if not dte.puede_emitir_documento_tributario:
        messages.error(
            request,
            dte.get_mensaje_no_emitible()
        )
        return redirect('facturacion_electronica:dte_detail', pk=dte_id)
    
    # ASEGURAR TIMBRE PDF417 si falta o es placeholder, pero tenemos el TED
    if dte.timbre_electronico and (not dte.timbre_pdf417 or dte.timbre_pdf417.size < 3000):
        try:
            from .pdf417_generator import PDF417Generator
            # Guardar el timbre (esta funcion llama a dte.timbre_pdf417.save que actualiza la DB)
            if PDF417Generator.guardar_pdf417_en_dte(dte):
                # Recargar el objeto para tener la URL del archivo
                dte.refresh_from_db()
        except Exception as e_timbre:
            logger.error(f"[PREVIEW] Error regenerando timbre: {e_timbre}")

    # Obtener la venta o la orden de despacho asociada con relaciones cargadas
    venta = None
    if dte.venta_id:
        # Cargar venta con todas las relaciones necesarias PREFETCHING referencias
        venta = Venta.objects.select_related(
            'cliente', 'vendedor', 'empresa', 'estacion_trabajo', 'forma_pago'
        ).prefetch_related('referencias').get(pk=dte.venta_id)
    
    # Usar el prefetched orden_despacho histórico (Venta) o, para pedidos,
    # recuperar la OrdenDespacho real desde los detalles vinculados al DTE.
    orden_despacho = dte.orden_despacho.all()[0] if dte.orden_despacho.exists() else None
    if not orden_despacho and OrdenDespacho:
        detalle_despacho = None
        if dte.tipo_dte == '52':
            detalle_despacho = dte.detalles_despacho_guia.select_related(
                'orden_despacho',
                'orden_despacho__orden_pedido',
                'orden_despacho__orden_pedido__cliente',
            ).first()
        elif dte.tipo_dte in ['33', '34']:
            detalle_despacho = dte.detalles_despacho_factura.select_related(
                'orden_despacho',
                'orden_despacho__orden_pedido',
                'orden_despacho__orden_pedido__cliente',
            ).first()
        if detalle_despacho:
            orden_despacho = detalle_despacho.orden_despacho
    
    # Intentar obtener transferencia
    transferencia = dte.transferencias.first()
    
    documento_origen = venta or orden_despacho or transferencia

    if not documento_origen:
        messages.error(request, 'Este DTE no tiene un documento de origen asociado (Venta, Orden de Despacho o Transferencia).')
        return redirect('facturacion_electronica:dte_detail', pk=dte_id)

    # Crear wrapper de cliente desde DTE si no hay cliente o el cliente no tiene datos
    class ClienteWrapper:
        def __init__(self, dte):
            self.nombre = dte.razon_social_receptor or "Cliente General"
            self.rut = dte.rut_receptor or ""
            self.direccion = dte.direccion_receptor or ""
            self.giro = dte.giro_receptor or ""
            self.ciudad = dte.ciudad_receptor or ""
            self.comuna = dte.comuna_receptor or ""
            self.telefono = ""
            self.email = ""
    
    # Si no hay venta pero hay orden de despacho, crear un objeto wrapper para compatibilidad
    if not venta and orden_despacho:
        # Crear un objeto simple que tenga los atributos necesarios para el template
        class VentaWrapper:
            def __init__(self, orden_despacho, dte):
                # Número de venta: usar folio del DTE o número de despacho
                self.numero_venta = dte.folio or getattr(orden_despacho, 'numero_despacho', 'N/A')
                # Empresa
                self.empresa = orden_despacho.empresa if hasattr(orden_despacho, 'empresa') else dte.empresa
                # Cliente desde orden_pedido o DTE como fallback
                cliente_real = orden_despacho.orden_pedido.cliente if hasattr(orden_despacho, 'orden_pedido') and orden_despacho.orden_pedido else None
                self.cliente = cliente_real if cliente_real else ClienteWrapper(dte)
                # Vendedor desde orden_pedido si existe
                self.vendedor = getattr(orden_despacho.orden_pedido, 'vendedor', None) if hasattr(orden_despacho, 'orden_pedido') and orden_despacho.orden_pedido else None
                # Fecha: usar fecha_despacho o fecha_emision del DTE
                self.fecha = orden_despacho.fecha_despacho if hasattr(orden_despacho, 'fecha_despacho') else dte.fecha_emision
                # Totales desde DTE
                self.total = dte.monto_total
                self.subtotal = dte.monto_neto
                self.iva = dte.monto_iva
                self.descuento = 0
                self.neto = dte.monto_neto
                self.impuesto_especifico = 0
                # Forma de pago: None (no aplica para órdenes de despacho)
                self.forma_pago = None
                self.saldo_pendiente = 0
                # Referencias: objeto vacío que retorna False en .exists()
                class ReferenciasWrapper:
                    def exists(self):
                        return False
                    def all(self):
                        return []
                self.referencias = ReferenciasWrapper()
                # Observaciones
                self.observaciones = getattr(orden_despacho, 'observaciones', '')
        
        venta = VentaWrapper(orden_despacho, dte)

    # Determinar el objeto cliente a mostrar en el template (sin tocar el FK real de venta)
    if venta and not isinstance(venta, Venta):
        cliente_display = getattr(venta, 'cliente', None)
    elif venta and isinstance(venta, Venta):
        if venta.cliente and venta.cliente.nombre:
            cliente_display = venta.cliente
        else:
            cliente_display = ClienteWrapper(dte)
    else:
        cliente_display = ClienteWrapper(dte)

    # Obtener detalles del documento
    detalles = []
    
    if isinstance(documento_origen, Venta):
        detalles = list(documento_origen.ventadetalle_set.all().select_related('articulo', 'articulo__unidad_medida'))
    elif OrdenDespacho and isinstance(documento_origen, OrdenDespacho):
        detalles_qs = documento_origen.items.filter(cantidad__gt=0)
        if str(dte.tipo_dte) == '52':
            vinculados = detalles_qs.filter(guia_despacho=dte)
            if vinculados.exists():
                detalles_qs = vinculados
        elif str(dte.tipo_dte) in ['33', '34']:
            vinculados = detalles_qs.filter(factura=dte)
            if vinculados.exists():
                detalles_qs = vinculados
        detalles_despacho = detalles_qs.select_related('item_pedido__articulo', 'item_pedido__articulo__unidad_medida')
        
        class DetalleWrapper:
            def __init__(self, detalle_despacho):
                self.detalle_despacho = detalle_despacho
                class ArticuloWrapper:
                    def __init__(self, articulo):
                        self.codigo = articulo.codigo
                        self.nombre = articulo.nombre
                        self.unidad_medida = articulo.unidad_medida
                
                self.articulo = ArticuloWrapper(detalle_despacho.item_pedido.articulo)
                self.cantidad = detalle_despacho.cantidad
                self.precio_unitario = detalle_despacho.item_pedido.precio_unitario
                subtotal_val = float(detalle_despacho.cantidad) * float(detalle_despacho.item_pedido.precio_unitario)
                descuento_pct = float(detalle_despacho.item_pedido.descuento_porcentaje or 0)
                self.descuento = subtotal_val * (descuento_pct / 100)
                self.precio_total = subtotal_val - self.descuento
        
        detalles = [DetalleWrapper(d) for d in detalles_despacho]
    
    # Caso para Transferencias
    from inventario.models import TransferenciaInventario
    if not detalles and isinstance(documento_origen, TransferenciaInventario):
        detalles_transf = documento_origen.detalles.all().select_related('articulo', 'articulo__unidad_medida')
        
        class DetalleTransfWrapper:
            def __init__(self, item_inv):
                self.articulo = item_inv.articulo
                self.cantidad = item_inv.cantidad
                self.precio_unitario = item_inv.precio_unitario
                self.precio_total = item_inv.total
                self.descuento = 0
                
        detalles = [DetalleTransfWrapper(d) for d in detalles_transf]
    
    # Obtener configuración de impresora
    empresa = request.empresa
    nombre_impresora = None
    
    # Seleccionar template según tipo de DTE
    if dte.tipo_dte in ['33', '34']:  # Facturas
        tipo_impresora = getattr(empresa, 'impresora_factura', 'laser')
        nombre_impresora = getattr(empresa, 'impresora_factura_nombre', None)
        template = 'ventas/factura_electronica_termica.html' if tipo_impresora in ['termica_80', 'termica_58', 'termica'] else 'ventas/factura_electronica_html.html'
    
    elif dte.tipo_dte in ['39', '41']:  # Boletas
        tipo_impresora = getattr(empresa, 'impresora_boleta', 'laser')
        nombre_impresora = getattr(empresa, 'impresora_boleta_nombre', None)
        template = 'ventas/boleta_electronica_termica.html' if tipo_impresora in ['termica_80', 'termica_58', 'termica'] else 'ventas/factura_electronica_html.html'
    
    elif dte.tipo_dte == '52':  # Guía de Despacho
        tipo_impresora = getattr(empresa, 'impresora_guia', 'laser')
        nombre_impresora = getattr(empresa, 'impresora_guia_nombre', None)
        template = 'inventario/guia_despacho_electronica_termica.html' if tipo_impresora in ['termica_80', 'termica_58', 'termica'] else 'inventario/guia_despacho_electronica_html.html'
    
    else:
        template = 'ventas/factura_electronica_html.html'

    if forzar_a4:
        nombre_impresora = None
        if dte.tipo_dte == '52':
            template = 'inventario/guia_despacho_electronica_html.html'
        else:
            template = 'ventas/factura_electronica_html.html'
    
    # Obtener formas de pago múltiples
    formas_pago_list = []
    condicion_pago_display = None
    try:
        from caja.models import VentaProcesada, MovimientoCaja
        
        # MÉTODO 0: Buscar desde DTE directamente
        venta_procesada_dte = VentaProcesada.objects.filter(dte_generado=dte).select_related('venta_final').first()
        if venta_procesada_dte and venta_procesada_dte.venta_final:
            movs = MovimientoCaja.objects.filter(
                venta=venta_procesada_dte.venta_final,
                tipo__in=['venta', 'ingreso']
            ).select_related('forma_pago')
            for mov in movs:
                if mov.forma_pago:
                    formas_pago_list.append({
                        'forma_pago': mov.forma_pago.nombre,
                        'monto': abs(float(mov.monto))
                    })
        
        # Fallback si no hay formas de pago múltiples
        if not formas_pago_list and venta and isinstance(venta, Venta):
            if venta.forma_pago:
                formas_pago_list.append({
                    'forma_pago': venta.forma_pago.nombre,
                    'monto': float(venta.total)
                })
    except Exception as e:
        logger.warning(f"Error al obtener formas de pago: {str(e)}")

    if venta and isinstance(venta, Venta):
        saldo_pendiente = float(getattr(venta, 'saldo_pendiente', 0) or 0)
        forma_pago = getattr(venta, 'forma_pago', None)
        es_credito = bool(getattr(forma_pago, 'es_cuenta_corriente', False)) or saldo_pendiente > 0
        if es_credito:
            condicion_pago_display = {
                'label': 'Credito / Cuenta Corriente',
                'monto': saldo_pendiente if saldo_pendiente > 0 else float(venta.total)
            }
            if not any((fp.get('forma_pago') or '').lower() in ['credito', 'crédito', 'cuenta corriente', 'credito / cuenta corriente'] for fp in formas_pago_list):
                formas_pago_list.append({
                    'forma_pago': condicion_pago_display['label'],
                    'monto': condicion_pago_display['monto']
                })
    
    # Copias: estación POS si hay, si no las de la empresa (Configurar impresoras).
    n_copias = n_copias_impresion(
        empresa,
        dte=dte,
        estacion=getattr(venta, 'estacion_trabajo', None) if venta else None,
        request=request,
    )
    
    receptor_display = _build_receptor_display(dte, fallback_cliente=cliente_display)
    bodega_display = resolver_bodega_documento(venta=venta, dte=dte)

    context = {
        'dte': dte,
        'venta': venta,
        'cliente_display': cliente_display,
        'receptor_display': receptor_display,
        'bodega_display': bodega_display,
        'detalles': detalles,
        'empresa': empresa,
        'nombre_impresora': nombre_impresora,
        'formas_pago_list': formas_pago_list,
        'condicion_pago_display': condicion_pago_display,
        'n_copias': n_copias,
        'copias_range': range(n_copias),
    }
    
    return render(request, template, context)


@login_required
@requiere_empresa
def ver_notacredito_electronica(request, notacredito_id):
    """
    Muestra la Nota de Crédito electrónica con el timbre
    """
    nota = get_object_or_404(NotaCredito, pk=notacredito_id, empresa=request.empresa)
    
    # Obtener el DTE asociado directamente desde la nota de crédito
    dte = nota.dte

    if not dte.puede_emitir_documento_tributario:
        messages.error(
            request,
            dte.get_mensaje_no_emitible()
        )
        return redirect('facturacion_electronica:dte_detail', pk=dte.pk)

    # Obtener detalles de la nota de crédito
    detalles = nota.items.all()
    
    # Obtener configuración de impresora
    empresa = request.empresa
    tipo_impresora = getattr(empresa, 'impresora_nota_credito', 'laser')
    nombre_impresora = getattr(empresa, 'impresora_nota_credito_nombre', None)
    
    # Seleccionar template según configuración
    if tipo_impresora in ['termica_80', 'termica_58', 'termica']:
        template = 'ventas/notacredito_electronica_termica.html'
        print(f"[PRINT] Nota Credito -> Formato TERMICO 80mm")
    else:
        template = 'ventas/notacredito_electronica_html.html'
        print(f"[PRINT] Nota Credito -> Formato LASER A4")
    
    # Obtener configuración de copias de la estación (prioritario)
    n_copias = 1
    venta = getattr(nota, 'venta', None)
    estacion = getattr(venta, 'estacion_trabajo', None) if venta else None
    if estacion:
        n_copias = estacion.get_copias_por_tipo('notacredito')
    if request.GET.get('pdf') == '1':
        n_copias = 1

    receptor_display = _build_receptor_display(dte, fallback_cliente=getattr(nota, 'cliente', None))

    context = {
        'nota': nota,
        'dte': dte,
        'receptor_display': receptor_display,
        'detalles': detalles,
        'empresa': empresa,
        'n_copias': n_copias,
        'copias_range': range(n_copias),
    }
    
    return render(request, template, context)


@login_required
@requiere_empresa
def ver_notadebito_electronica(request, notadebito_id):
    """
    Muestra la Nota de Débito electrónica con el timbre
    """
    from ventas.models import NotaDebito
    nota = get_object_or_404(NotaDebito, pk=notadebito_id, empresa=request.empresa)
    
    # Obtener el DTE asociado
    dte = nota.dte

    # Obtener detalles
    detalles = nota.items.all()
    
    # Obtener configuración de impresora
    empresa = request.empresa
    tipo_impresora = getattr(empresa, 'impresora_nota_debito', 'laser')
    
    # Seleccionar template según configuración
    if tipo_impresora in ['termica_80', 'termica_58', 'termica']:
        template = 'ventas/notadebito_electronica_termica.html'
        print(f"[PRINT] Nota Debito -> Formato TERMICO 80mm")
    else:
        # Por ahora usamos el listado si no hay template laser específico o reusamos lógica
        template = 'ventas/notadebito_electronica_termica.html' # Ajustar si existe html
        print(f"[PRINT] Nota Debito -> Formato TERMICO (fallback)")

    n_copias = 1
    if request.GET.get('pdf') == '1':
        n_copias = 1
    receptor_display = _build_receptor_display(dte, fallback_cliente=getattr(nota, 'cliente', None))

    context = {
        'nota': nota,
        'dte': dte,
        'receptor_display': receptor_display,
        'detalles': detalles,
        'empresa': empresa,
        'copias_range': range(n_copias),
    }
    
    return render(request, template, context)


@login_required
@requiere_empresa
def dte_list(request):
    """
    Lista de DTEs de la empresa (REDIRIGIDO AL LIBRO DE VENTAS OFICIAL EN VENTAS)
    """
    from django.shortcuts import redirect
    from django.urls import reverse
    
    url = reverse('ventas:libro_ventas')
    query_string = request.GET.urlencode()
    if query_string:
        url += '?' + query_string
        
    return redirect(url)



@login_required
@requiere_empresa
def regenerar_xml_dte(request, dte_id):
    """
    Regenera el XML de un DTE existente. Soporta Boletas (39) y Guías de Despacho (52) asociadas a transferencia.
    """
    from decimal import Decimal
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=dte_id, empresa=request.empresa)

    if dte.tipo_dte == '39':
        try:
            dte.estado_sii = 'generado'
            dte.error_envio = ''
            dte.track_id = ''
            dte.save()
            dte_service = DTEService(request.empresa)
            dte_service.procesar_dte_existente(dte)
            messages.success(request, f'XML de la Boleta folio {dte.folio} regenerado correctamente.')
        except Exception as e:
            messages.error(request, f'Error al regenerar XML: {str(e)}')
            import traceback
            return redirect_to_dte_list(request, anchor=f'row-{dte.id}', dte=dte)

    if dte.tipo_dte == '52':
        transferencia = getattr(dte, 'transferencias', None)
        if transferencia:
            transferencia = transferencia.first()
        if not transferencia:
            messages.error(request, 'Esta guía no está asociada a una transferencia. No se puede regenerar el XML.')
            return redirect_to_dte_list(request)
        try:
            from facturacion_electronica.dte_generator import DTEXMLGenerator
            from facturacion_electronica.firma_electronica import FirmadorDTE
            from facturacion_electronica.pdf417_generator import PDF417Generator

            detalles = transferencia.detalles.all()
            subtotal = sum(detalle.total for detalle in detalles)
            iva = subtotal * Decimal('0.19')
            total = subtotal + iva

            class TransferenciaWrapper:
                def __init__(self, transferencia, subtotal, iva, total, tipo_traslado='5'):
                    self.empresa = transferencia.empresa
                    self.cliente = None
                    self.tipo_documento = '52'
                    self.fecha_emision = timezone.now().date()
                    self.tipo_traslado = tipo_traslado
                    self.tipo_despacho = tipo_traslado
                    self.rut_receptor = transferencia.empresa.rut
                    self.razon_social_receptor = transferencia.empresa.nombre
                    self.giro_receptor = transferencia.empresa.giro
                    self.direccion_receptor = transferencia.empresa.direccion
                    self.comuna_receptor = transferencia.empresa.comuna
                    self.ciudad_receptor = transferencia.empresa.ciudad
                    self.monto_neto = subtotal
                    self.monto_exento = Decimal('0')
                    self.monto_iva = iva
                    self.monto_total = total
                    self.descuento = Decimal('0')
                    self.items = transferencia.detalles

            tipo_traslado = (dte.tipo_traslado or '5').strip() or '5'
            venta_wrapper = TransferenciaWrapper(transferencia, subtotal, iva, total, tipo_traslado=tipo_traslado)
            generator = DTEXMLGenerator(request.empresa, venta_wrapper, '52', dte.folio, dte.caf_utilizado)
            xml_sin_firmar = generator.generar_xml()

            firmador = FirmadorDTE(
                request.empresa.certificado_digital.path,
                request.empresa.password_certificado
            )
            xml_firmado = firmador.firmar_xml(xml_sin_firmar)

            dte_service = DTEService(request.empresa)
            try:
                datos_parsed = dte_service._parsear_datos_caf(dte.caf_utilizado)
                datos_caf = {'modulo': datos_parsed.get('M', ''), 'exponente': datos_parsed.get('E', '')}
            except Exception:
                datos_caf = {'modulo': 'ERROR', 'exponente': 'ERROR'}

            caf = dte.caf_utilizado
            dte_data = {
                'rut_emisor': request.empresa.rut,
                'tipo_dte': '52',
                'folio': dte.folio,
                'fecha_emision': (dte.fecha_emision or timezone.now().date()).strftime('%Y-%m-%d'),
                'rut_receptor': request.empresa.rut,
                'razon_social_receptor': request.empresa.nombre,
                'monto_total': int(total),
                'item_1': 'Guía de Despacho Electrónica',
            }
            caf_data = {
                'rut_emisor': request.empresa.rut,
                'razon_social': request.empresa.razon_social_sii or request.empresa.razon_social,
                'tipo_documento': '52',
                'folio_desde': caf.folio_desde,
                'folio_hasta': caf.folio_hasta,
                'fecha_autorizacion': caf.fecha_autorizacion.strftime('%Y-%m-%d'),
                'modulo': datos_caf.get('modulo', ''),
                'exponente': datos_caf.get('exponente', ''),
                'firma': caf.firma_electronica,
            }
            ted_xml = firmador.generar_ted(dte_data, caf_data)

            pdf417_data = firmador.generar_datos_pdf417(ted_xml)
            dte.xml_dte = xml_sin_firmar
            dte.xml_firmado = xml_firmado
            dte.timbre_electronico = ted_xml
            dte.datos_pdf417 = pdf417_data
            dte.estado_sii = 'generado'
            dte.error_envio = ''
            dte.track_id = ''
            dte.save()
            PDF417Generator.guardar_pdf417_en_dte(dte)
            messages.success(request, f'XML de la Guía folio {dte.folio} regenerado correctamente. Ya puede enviarla al SII.')
        except Exception as e:
            messages.error(request, f'Error al regenerar XML de la guía: {str(e)}')
        return redirect_to_dte_list(request, anchor=f'row-{dte.id}', dte=dte)

    messages.error(request, 'Solo se puede regenerar XML de Boletas (39) o Guías de Despacho (52) asociadas a una transferencia.')
    return redirect_to_dte_list(request, anchor=f'row-{dte.id}', dte=dte)



@login_required
@requiere_empresa
def sincronizar_pendientes_sii(request):
    """
    Encola DTEs pendientes al SII en segundo plano (BackgroundDTESender).
    GET o POST; AJAX responde JSON.
    """
    from .background_sender import get_background_sender
    from .validacion_envio import obtener_dtes_pendientes_envio

    sender = get_background_sender()
    dtes_pendientes = obtener_dtes_pendientes_envio(request.empresa)
    tipo_dte = (request.GET.get('tipo_dte') or request.POST.get('tipo_dte') or '').strip()
    if tipo_dte:
        dtes_pendientes = dtes_pendientes.filter(tipo_dte=tipo_dte)
    dtes_ids = list(dtes_pendientes.values_list('id', flat=True))
    count = sender.enviar_multiples(dtes_ids, request.empresa.id) if dtes_ids else 0

    if count > 0:
        msg = f'Se han encolado {count} documentos para envío al SII en segundo plano.'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': msg, 'count': count})
        messages.success(request, msg)
    else:
        msg = 'No hay documentos pendientes para enviar.'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': msg, 'count': 0})
        messages.info(request, msg)

    return redirect_to_dte_list(request)


@login_required
@requiere_empresa
def consultar_estados_pendientes_sii(request):
    """Consulta en el SII el estado de DTEs ya enviados (con Track) que aún no son finales."""
    tipo_dte = (request.GET.get('tipo_dte') or request.POST.get('tipo_dte') or '').strip()
    qs = DocumentoTributarioElectronico.objects.filter(
        empresa=request.empresa,
    ).exclude(
        Q(track_id__isnull=True) | Q(track_id='')
    ).exclude(
        estado_sii__in=['aceptado', 'aceptado_reparos', 'anulado']
    )
    if tipo_dte:
        qs = qs.filter(tipo_dte=tipo_dte)
    qs = qs.select_related('empresa').order_by('-fecha_emision', '-folio')[:80]

    pendientes = []
    for documento in qs:
        if documento.requiere_consulta_estado_sii():
            pendientes.append(documento)
        if len(pendientes) >= 20:
            break

    consultados = 0
    errores = 0
    if pendientes:
        servicio = DTEService(request.empresa)
        for documento in pendientes:
            try:
                servicio.consultar_estado_dte(documento)
                consultados += 1
            except Exception:
                errores += 1

    etiqueta = 'guías' if tipo_dte == '52' else 'documentos'
    if consultados:
        msg = f'Se consultó el estado de {consultados} {etiqueta} en el SII.'
        if errores:
            msg += f' {errores} no se pudieron consultar.'
        messages.success(request, msg)
    elif errores:
        messages.error(request, f'No se pudo consultar el estado de {errores} {etiqueta}.')
    else:
        messages.info(request, f'No hay {etiqueta} pendientes de consulta SII.')

    return redirect_to_dte_list(request)
