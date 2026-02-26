"""
Vistas para generación y gestión de DTE
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import datetime
from core.decorators import requiere_empresa
from .models import DocumentoTributarioElectronico
from .dte_service import DTEService
from ventas.models import Venta, NotaCredito
from clientes.models import Cliente

# Importar OrdenDespacho si existe (puede no estar disponible en todos los proyectos)
try:
    from pedidos.models import OrdenDespacho
except ImportError:
    OrdenDespacho = None


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
            messages.error(request, f'Error inesperado: {str(e)}')
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
    Envía un DTE al SII
    """
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=dte_id, empresa=request.empresa)
    
    # Verificar que no haya sido enviado ya
    if dte.estado_sii in ['enviado', 'aceptado']:
        messages.warning(request, 'Este DTE ya fue enviado al SII.')
        return redirect('facturacion_electronica:dte_list')

    # Acción directa: cualquier request que llegue aquí intenta enviar el DTE
    try:
        # Inicializar servicio
        dte_service = DTEService(request.empresa)

        # Enviar al SII (vía DTEBox)
        respuesta = dte_service.enviar_dte_al_sii(dte)

        if respuesta.get('track_id'):
            messages.success(
                request,
                f'DTE enviado exitosamente al SII. Track ID: {respuesta["track_id"]}'
            )
        else:
            messages.warning(
                request,
                'DTE enviado pero no se recibió Track ID. Revise la respuesta del SII.'
            )

    except Exception as e:
        messages.error(request, f'Error al enviar DTE: {str(e)}')
        import traceback
        traceback.print_exc()

    # Siempre volver al listado de DTE después del intento de envío
    return redirect('facturacion_electronica:dte_list')




@login_required
@requiere_empresa
def consultar_estado_dte(request, dte_id):
    """
    Consulta el estado de un DTE en el SII
    """
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=dte_id, empresa=request.empresa)
    
    if not dte.track_id:
        messages.error(request, 'Este DTE no tiene Track ID. Debe ser enviado al SII primero.')
        return redirect('facturacion_electronica:dte_detail', pk=dte_id)
    
    try:
        # Inicializar servicio
        dte_service = DTEService(request.empresa)
        
        # Consultar estado
        estado = dte_service.consultar_estado_dte(dte)
        
        messages.success(
            request,
            f'Estado consultado: {estado.get("estado")} - {estado.get("glosa", "")}'
        )
        
    except Exception as e:
        messages.error(request, f'Error al consultar estado: {str(e)}')
        import traceback
        traceback.print_exc()
    
    return redirect('facturacion_electronica:dte_detail', pk=dte_id)


@login_required
@requiere_empresa
def dte_detail(request, pk):
    """
    Detalle de un DTE
    """
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=pk, empresa=request.empresa)
    
    context = {
        'dte': dte,
    }
    
    return render(request, 'facturacion_electronica/dte_detail.html', context)


@login_required
@requiere_empresa
def ver_factura_electronica(request, dte_id):
    """
    Muestra la factura electrónica con el timbre
    """
    # Optimizar el query de DTE con select_related y prefetch_related
    dte = get_object_or_404(
        DocumentoTributarioElectronico.objects.select_related(
            'empresa', 'venta', 'caf_utilizado', 'vendedor'
        ).prefetch_related('orden_despacho'), 
        pk=dte_id, empresa=request.empresa
    )
    
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
    
    # Usar el prefetched orden_despacho
    orden_despacho = dte.orden_despacho.all()[0] if dte.orden_despacho.exists() else None
    documento_origen = venta or orden_despacho

    if not documento_origen:
        messages.error(request, 'Este DTE no tiene un documento de origen asociado (Venta u Orden de Despacho).')
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
        detalles_despacho = documento_origen.items.all().select_related('item_pedido__articulo', 'item_pedido__articulo__unidad_medida')
        
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
                subtotal = float(detalle_despacho.cantidad) * float(detalle_despacho.item_pedido.precio_unitario)
                descuento_pct = float(detalle_despacho.item_pedido.descuento_porcentaje or 0)
                self.descuento = subtotal * (descuento_pct / 100)
                self.precio_total = subtotal - self.descuento
        
        detalles = [DetalleWrapper(d) for d in detalles_despacho]
    
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
    
    # Obtener formas de pago múltiples
    formas_pago_list = []
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
    
    context = {
        'dte': dte,
        'venta': venta,
        'cliente_display': cliente_display,
        'detalles': detalles,
        'empresa': empresa,
        'nombre_impresora': nombre_impresora,
        'formas_pago_list': formas_pago_list,
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
    
    context = {
        'nota': nota,
        'dte': dte,
        'detalles': detalles,
        'empresa': empresa,
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
    
    context = {
        'nota': nota,
        'dte': dte,
        'detalles': detalles,
        'empresa': empresa,
    }
    
    return render(request, template, context)


@login_required
@requiere_empresa
def dte_list(request):
    """
    Lista de DTEs de la empresa (REDIRIGIDO AL LIBRO DE VENTAS OFICIAL EN VENTAS)
    """
    from django.shortcuts import redirect
    return redirect('ventas:libro_ventas')


@login_required
@requiere_empresa
def probar_dtebox(request, dte_id):
    """
    Vista de prueba para probar DTEBox con un DTE existente
    """
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=dte_id, empresa=request.empresa)
    
    if not request.empresa.dtebox_habilitado:
        messages.error(request, 'DTEBox no está habilitado para esta empresa.')
        return redirect('facturacion_electronica:dte_detail', pk=dte_id)
    
    if not dte.xml_firmado:
        messages.error(request, 'Este DTE no tiene XML firmado. Debe generar el DTE primero.')
        return redirect('facturacion_electronica:dte_detail', pk=dte_id)
    
    resultado = None
    error = None
    
    if request.method == 'POST':
        try:
            from facturacion_electronica.dtebox_service import DTEBoxService
            
            dtebox = DTEBoxService(request.empresa)
            resultado = dtebox.timbrar_dte(dte.xml_firmado)
            
            if resultado['success']:
                # Actualizar el TED en el DTE
                dte.timbre_electronico = resultado['ted']
                
                # Regenerar PDF417 con el nuevo TED
                from facturacion_electronica.firma_electronica import FirmadorDTE
                firmador = FirmadorDTE(
                    request.empresa.certificado_digital.path,
                    request.empresa.password_certificado
                )
                pdf417_data = firmador.generar_datos_pdf417(resultado['ted'])
                dte.datos_pdf417 = pdf417_data
                
                # Regenerar imagen PDF417
                from facturacion_electronica.pdf417_generator import PDF417Generator
                PDF417Generator.guardar_pdf417_en_dte(dte)
                
                dte.save()
                
                messages.success(request, '✅ TED obtenido exitosamente desde DTEBox y actualizado en el DTE.')
            else:
                error = resultado['error']
                messages.error(request, f'❌ Error al obtener TED desde DTEBox: {error}')
                
        except Exception as e:
            error = str(e)
            messages.error(request, f'❌ Error inesperado: {error}')
            import traceback
            traceback.print_exc()
    
    context = {
        'dte': dte,
        'resultado': resultado,
        'error': error,
        'empresa': request.empresa,
    }
    
    return render(request, 'facturacion_electronica/probar_dtebox.html', context)


@login_required
@requiere_empresa
def probar_dtebox_xml_ejemplo(request):
    """
    Vista para probar DTEBox con el XML de ejemplo exacto que el usuario compartió
    """
    if not request.empresa.dtebox_habilitado:
        messages.error(request, 'DTEBox no está habilitado para esta empresa.')
        return redirect('facturacion_electronica:dte_list')
    
    resultado = None
    error = None
    
    # XML de ejemplo válido y timbrado que el usuario compartió
    xml_ejemplo = '''<EnvioDTE xmlns="http://www.sii.cl/SiiDte" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.0" xsi:schemaLocation="http://www.sii.cl/SiiDte EnvioDTE_v10.xsd">
<SetDTE ID="ID74b2e30033e64606b9a1d4d54bd6b05f">
<Caratula version="1.0">
<RutEmisor>77117239-3</RutEmisor>
<RutEnvia>10974377-1</RutEnvia>
<RutReceptor>78421900-3</RutReceptor>
<FchResol>2014-08-22</FchResol>
<NroResol>80</NroResol>
<TmstFirmaEnv>2025-11-03T12:26:50</TmstFirmaEnv>
<SubTotDTE>
<TpoDTE>33</TpoDTE>
<NroDTE>1</NroDTE>
</SubTotDTE>
</Caratula>
<DTE xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns="http://www.sii.cl/SiiDte" version="1.0">
<Documento ID="F3220T33">
<Encabezado>
<IdDoc>
<TipoDTE>33</TipoDTE>
<Folio>3220</Folio>
<FchEmis>2025-11-03</FchEmis>
<FmaPago>1</FmaPago>
</IdDoc>
<Emisor>
<RUTEmisor>77117239-3</RUTEmisor>
<RznSoc>SOCIEDAD INFORMATICA KREASOFT SPA</RznSoc>
<GiroEmis>.COMPUTACION</GiroEmis>
<Telefono>963697225</Telefono>
<Acteco>523930</Acteco>
<DirOrigen>VICTOR PLAZA MAYORGA 887</DirOrigen>
<CmnaOrigen>EL BOSQUE</CmnaOrigen>
<CiudadOrigen>SANTIAGO</CiudadOrigen>
<CdgVendedor>OFICINA</CdgVendedor>
</Emisor>
<Receptor>
<RUTRecep>78421900-3</RUTRecep>
<RznSocRecep>JPF CINE S.A.</RznSocRecep>
<GiroRecep>PRODUCCIONES AUDIOVISUALES.</GiroRecep>
<Contacto>.</Contacto>
<DirRecep>CALLE NUEVA 1757.</DirRecep>
<CmnaRecep>HUECHURABA.</CmnaRecep>
<CiudadRecep>SANTIAGO.</CiudadRecep>
</Receptor>
<Totales>
<MntNeto>186181</MntNeto>
<MntExe>0</MntExe>
<TasaIVA>19</TasaIVA>
<IVA>35374</IVA>
<MntTotal>221555</MntTotal>
</Totales>
</Encabezado>
<Detalle>
<NroLinDet>1</NroLinDet>
<CdgItem>
<TpoCodigo>INT</TpoCodigo>
<VlrCodigo>SER001</VlrCodigo>
</CdgItem>
<NmbItem>SERVICIO MENSUAL</NmbItem>
<DscItem>SERVICIO DE MANTENCION SISTEMAS N O V I E M B R E - 2025 </DscItem>
<QtyItem>1</QtyItem>
<PrcItem>186181</PrcItem>
<MontoItem>186181</MontoItem>
</Detalle>
<TED version="1.0">
<DD>
<RE>77117239-3</RE>
<TD>33</TD>
<F>3220</F>
<FE>2025-11-03</FE>
<RR>78421900-3</RR>
<RSR>JPF CINE S.A.</RSR>
<MNT>221555</MNT>
<IT1>SERVICIO MENSUAL</IT1>
<CAF version="1.0">
<DA>
<RE>77117239-3</RE>
<RS>SOCIEDAD INFORMÁTICA KREASOFT SPA</RS>
<TD>33</TD>
<RNG>
<D>3150</D>
<H>3227</H>
</RNG>
<FA>2025-05-05</FA>
<RSAPK>
<M>uYWbTHGa7MxLNibxh9WcGUObQQ+R+Jftd5Oxt4XKOl2Br/Dvo3MRSqUWatRH0x7CF7H2hCZbifaj+FGLJnuP9Q==</M>
<E>Aw==</E>
</RSAPK>
<IDK>300</IDK>
</DA>
<FRMA algoritmo="SHA1withRSA">lmeB07XNTlAH7022i7xjKGPRaTrjRbJQuKH2qp7PwaWdUq5m7At5d0P9c7dXrDjF7gAresSLoeExxg0wtUeBiQ==</FRMA>
</CAF>
<TSTED>2025-11-03T12:26:45</TSTED>
</DD>
<FRMT algoritmo="SHA1withRSA">KHvM01ziigCDTlSeNcnyWHjRbMVuWHQ1va+Y7tc5TV7QC9uM3fu4y2gjvEzhJpBAwhRio0kvgMIpWIZb/L5AKw==</FRMT>
</TED>
<TmstFirma>2025-11-03T12:26:45</TmstFirma>
</Documento>
<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
<SignedInfo>
<CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
<SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>
<Reference URI="#F3220T33">
<Transforms>
<Transform Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
</Transforms>
<DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
<DigestValue>jjWEeksyW8B3whSe2dXZTWqYfRI=</DigestValue>
</Reference>
</SignedInfo>
<SignatureValue> cs7egu7YkL5hoD1rtIECgAE2SVuiheFdpPgh+CsJFTF9HMHSb4kMiEh4r5f4XFsA 9QoV3yJB/AnGrTIKXKtL0sjj38XzxiPxo6po4Wr0L4xM5EP+JyR7nFHYt7i19U7k QKVoO8A8xgfS0BPhRh4Ah8tn2iRzWakZTISPB6tzT3jPwmmvWjM8tY9PD4IK4nIG WD9LVhJnBkhXjfYkkMGHRMnQdYagklATbBQEDv36w0Syw9eu/ddlUoNMM6n0tCSE 46N8C3Syu3kDf+VxX2OGyV4HDDrxKIrxkYkzpuutkzXO9dLvlbSPfMYvrwNspcsz J9ZUb35sTj7wf8tnFAZgFA== </SignatureValue>
<KeyInfo>
<KeyValue>
<RSAKeyValue>
<Modulus> nMxFllg/ae7Awo2T+2/6mMFfebVoTC4vBfqV5feMkAQ4YevKqh2nhBtjB4HKhMd4 GEVn3O57BTRkjEdQIGy/lVQBgBdZzaTW8e0YDqIXZQSh9qKRQqL9tQ7nhNl8Cq1e BMJqLInQVvlC0UYmvUEFe3t6/ws4QwdhRMK5WxNpb/r2WAeymQD0k9+jKnRda6zh gwyCMNrOifWAwG6vMNGwr+NZA2FHV9/6ecs6jfmKaVfDALjG4u9PW4ZH+GDrEWB8 fwWsWj6e4umicxnbLIqWWwUxxM5PacSSahvpdk22oDjJWK1xuAFZkO/2mhKlnRaS hh27GZgMRd9TxigV4QI/3Q== </Modulus>
<Exponent>AQAB</Exponent>
</RSAKeyValue>
</KeyValue>
<X509Data>
<X509Certificate> MIIGEDCCBPigAwIBAgIIS9+A8qleqEEwDQYJKoZIhvcNAQELBQAwgboxHjAcBgkq hkiG9w0BCQEWD3NvcG9ydGVAaWRvay5jbDEiMCAGA1UEAwwZSURPSyBGSVJNQSBF TEVDVFJPTklDQSBWNDEXMBUGA1UECwwOUlVULTc2NjEwNzE4LTQxIDAeBgNVBAsM F0F1dG9yaWRhZCBDZXJ0aWZpY2Fkb3JhMRkwFwYDVQQKDBBCUE8gQWR2aXNvcnMg U3BBMREwDwYDVQQHDAhTYW50aWFnbzELMAkGA1UEBhMCQ0wwHhcNMjQwMTE4MjEy NzE2WhcNMjYwMTE3MjEyNzE2WjB7MScwJQYDVQQDDB5SSUNBUkRPIEFOVE9OSU8g R09OWkFMRVogR0FFVEUxITAfBgkqhkiG9w0BCQEWEmtyZWFzb2Z0QGdtYWlsLmNv bTETMBEGA1UEBRMKMTEzMTQ3NTUtNTELMAkGA1UEBhMCQ0wxCzAJBgNVBAcMAlJN MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnMxFllg/ae7Awo2T+2/6 mMFfebVoTC4vBfqV5feMkAQ4YevKqh2nhBtjB4HKhMd4GEVn3O57BTRkjEdQIGy/ lVQBgBdZzaTW8e0YDqIXZQSh9qKRQqL9tQ7nhNl8Cq1eBMJqLInQVvlC0UYmvUEF e3t6/ws4QwdhRMK5WxNpb/r2WAeymQD0k9+jKnRda6zhgwyCMNrOifWAwG6vMNGw r+NZA2FHV9/6ecs6jfmKaVfDALjG4u9PW4ZH+GDrEWB8fwWsWj6e4umicxnbLIqW WwUxxM5PacSSahvpdk22oDjJWK1xuAFZkO/2mhKlnRaShh27GZgMRd9TxigV4QI/ 3QIDAQABo4ICVjCCAlIwCQYDVR0TBAIwADAfBgNVHSMEGDAWgBS73UrbfxA3iHRn RbLKuRKE4MZ4FjCBmAYDVR0gBIGQMIGNMIGKBgorBgEEAYOMHgEEMHwwLAYIKwYB BQUHAgEWIGh0dHBzOi8vcHNjLmlkb2suY2wvb3Blbi9jcHMucGRmMEwGCCsGAQUF BwICMEAePgBDAGUAcgB0AGkAZgBpAGMAYQBkAG8AIABwAGEAcgBhACAAdQBzAG8A IABUAHIAaQBiAHUAdABhAHIAaQBvMIIBEQYDVR0fBIIBCDCCAQQwggEAoDmgN4Y1 aHR0cHM6Ly9wc2MuaWRvay5jbC9vcGVuL0lET0tfRklSTUFfRUxFQ1RST05JQ0Ff NC5jcmyigcKkgb8wgbwxHjAcBgkqhkiG9w0BCQEWD3NvcG9ydGVAaWRvay5jbDEk MCIGA1UEAwwbSURPSyBGSVJNQSBFTEVDVFJPTklDQSAyMDIyMRcwFQYDVQQLDA5S VVQtNzY2MTA3MTgtNDEgMB4GA1UECwwXQXV0b3JpZGFkIENlcnRpZmljYWRvcmEx GTAXBgNVBAoMEEJQTyBBZHZpc29ycyBTcEExETAPBgNVBAcMCFNhbnRpYWdvMQsw CQYDVQQGEwJDTDAdBgNVHQ4EFgQUR1ca1G+NYS4s9jhYXYQDS5D/nDowCwYDVR0P BAQDAgSQMCMGA1UdEgQcMBqgGAYIKwYBBAHBAQKgDBYKNzY2MTA3MTgtNDAjBgNV HREEHDAaoBgGCCsGAQQBwQEBoAwWCjExMzE0NzU1LTUwDQYJKoZIhvcNAQELBQAD ggEBAG1cRq5yYhudo5t+mxvGDH8TbNrWyu7Tbvw8HFqBdQGnfJJu/Q04PGIjZzCz AFpYlT7FEGj6CKm0lsxkdbgTEficazP/XClwu7L6LprhB4HmGywJf9p40NOP/S8r 4NgQqzI9uRLrrnHzSB9pYmP9rTsqXNTXN/GC8faj0pdgSmwwotKcT95CVMHoVTuI irvbOiD7/lAy/znLRKDSDHiiNgCz80+/hkkDYmXuqIgteurC0NZ6NIzC5W3p2SC7 PQt9euX1gmx7a3mmz6aEgJbHjxvFx5+8uCsSEwQXqrXu3hz3mqeeA804bwU9rMIG Cg1jxEvGSraeRRX9btsOAWEZ0hk= </X509Certificate>
</X509Data>
</KeyInfo>
</Signature>
</DTE>
</SetDTE>
<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
<SignedInfo>
<CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
<SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>
<Reference URI="#ID74b2e30033e64606b9a1d4d54bd6b05f">
<Transforms>
<Transform Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
</Transforms>
<DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
<DigestValue>hIN6XB5CxQW3NbXoAZxhj7JPWCQ=</DigestValue>
</Reference>
</SignedInfo>
<SignatureValue> EgUz0KMyNg3JUnVXsvIeMJWJrx29WTrAPutCY5hHCao7MoeRQY6zcW2RkmxOjCKW 2VyTrsUoJ3XOibQRjgZOIaSAzd8iMbtvQ59GQMQbLUMpc/rKk0hAQA50qMgGFYdw mbsXtA+9kHJIzk7N7JdJTprBdb1P+cDBA54hD5FKODBvIY+RjlPsnE5FyMCi6rOF uxntZSEvChFZA2aShILOik2OLvoH2FeZJSIJ7s9Uso0SZmlAfjlAM4pqXz7jiVLl sDwoBETX6VLhhAcqnMJqKSmT80iPn3yxR20PW9rD1fqYif+z/jByZJ5ozdeHG1te KzcVf7pQTYVdMTw+sytozA== </SignatureValue>
<KeyInfo>
<KeyValue>
<RSAKeyValue>
<Modulus> mZyNOZGHPazOujYza5bj8qjBUwShdlmdABF+CJO5S1iGAMBXoyb+UTc5tqKaqLQr hxOJxZSZwpuMVbc2cJ+JtDwXsEj2asqB9GXjHGUH4HhJu7PI7qWw2YivtQm2p4R3 hsd+un1QECsfAyL8DQ4v8ulm7URFuOimYA8YK2ML8EmiBJ2AzXu9MTxIUBUkhxsv A3tffFuDudOtIK12FpHSM0jseAFvZJY7HSfV/oybdeUDeKX10rrgnIrsOHfwZQ9E TQ3lzbTZms1WCu40cG30aMn1o8c1TLMdfNPT8f2PULshH4TuykwHli4MVk8LD2TR 4hDdNt6JK2BUQJT2VeL8Fw== </Modulus>
<Exponent>AQAB</Exponent>
</RSAKeyValue>
</KeyValue>
<X509Data>
<X509Certificate> MIIGEDCCBPigAwIBAgIINo2mVCGpjRYwDQYJKoZIhvcNAQELBQAwgboxHjAcBgkq hkiG9w0BCQEWD3NvcG9ydGVAaWRvay5jbDEiMCAGA1UEAwwZSURPSyBGSVJNQSBF TEVDVFJPTklDQSBWMjEXMBUGA1UECwwOUlVULTc2NjEwNzE4LTQxIDAeBgNVBAsM F0F1dG9yaWRhZCBDZXJ0aWZpY2Fkb3JhMRkwFwYDVQQKDBBCUE8gQWR2aXNvcnMg U3BBMREwDwYDVQQHDAhTYW50aWFnbzELMAkGA1UEBhMCQ0wwHhcNMjIwNTIzMjI0 OTM1WhcNMjUwNTIyMjI0OTM1WjB9MSgwJgYDVQQDDB9DUklTVElBTiBVTElTRVMg Uk9KQVMgR1VUSUVSUkVaMSIwIAYJKoZIhvcNAQkBFhNjcm9qYXNAZ2RleHByZXNz LmNsMRMwEQYDVQQFEwoxMDk3NDM3Ny0xMQswCQYDVQQGEwJDTDELMAkGA1UEBwwC Uk0wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCZnI05kYc9rM66NjNr luPyqMFTBKF2WZ0AEX4Ik7lLWIYAwFejJv5RNzm2opqotCuHE4nFlJnCm4xVtzZw n4m0PBewSPZqyoH0ZeMcZQfgeEm7s8jupbDZiK+1CbanhHeGx366fVAQKx8DIvwN Di/y6WbtREW46KZgDxgrYwvwSaIEnYDNe70xPEhQFSSHGy8De198W4O5060grXYW kdIzSOx4AW9kljsdJ9X+jJt15QN4pfXSuuCciuw4d/BlD0RNDeXNtNmazVYK7jRw bfRoyfWjxzVMsx1809Px/Y9QuyEfhO7KTAeWLgxWTwsPZNHiEN023okrYFRAlPZV 4vwXAgMBAAGjggJUMIICUDAJBgNVHRMEAjAAMB8GA1UdIwQYMBaAFPBsM7+sl5NY eqHgzp7s6N77ZT76MIGYBgNVHSAEgZAwgY0wgYoGCisGAQQBg4weAQQwfDAsBggr BgEFBQcCARYgaHR0cHM6Ly9wc2MuaWRvay5jbC9vcGVuL2Nwcy5wZGYwTAYIKwYB BQUHAgIwQB4+AEMAZQByAHQAaQBmAGkAYwBhAGQAbwAgAHAAYQByAGEAIAB1AHMA bwAgAFQAcgBpAGIAdQB0AGEAcgBpAG8wggEPBgNVHR8EggEGMIIBAjCB/6A6oDiG Nmh0dHBzOi8vcHNjLmlkb2suY2wvb3Blbi9JRE9LX0ZJUk1BX0VMRUNUUk9OSUNB X1YyLmNybKKBwKSBvTCBujEeMBwGCSqGSIb3DQEJARYPc29wb3J0ZUBpZG9rLmNs MSIwIAYDVQQDDBlJRE9LIEZJUk1BIEVMRUNUUk9OSUNBIFYyMRcwFQYDVQQLDA5S VVQtNzY2MTA3MTgtNDEgMB4GA1UECwwXQXV0b3JpZGFkIENlcnRpZmljYWRvcmEx GTAXBgNVBAoMEEJQTyBBZHZpc29ycyBTcEExETAPBgNVBAcMCFNhbnRpYWdvMQsw CQYDVQQGEwJDTDAdBgNVHQ4EFgQUnR78AetPsNDqFh+h8AeExJY4aOgwCwYDVR0P BAQDAgSQMCMGA1UdEgQcMBqgGAYIKwYBBAHBAQKgDBYKNzY2MTA3MTgtNDAjBgNV HREEHDAaoBgGCCsGAQQBwQEBoAwWCjEwOTc0Mzc3LTEwDQYJKoZIhvcNAQELBQAD ggEBAA6KTv23rQSdvQrJMy1jxE/+gYgMDsPqx6VcSRrsDVl+tUjf4Bld1zBLmBak dtMPiyNhQ0kaOgEjo3QU8kQ/SV6fWysnmwwAutagLJvX5cix9YPrhAnGxe31kdR7 nj8h/xMTetxxgmOQ/+sKwM6GDPCyzVMZ0JuXr9rn3ozViDx0+Lu1tegCE0CMZgLi ynwZXrtR5bjbJH01QrxErY8GoFIY7BO8Iah/iBS0SfClWYaEH6JOjcGUSIwDapa3 Th0+GYEUgSektb8aHqyl2XEDJtAem4PSWmsdOBZZaXA07eUVxI20qq4FeKdl38Mi t/WiFQvQ0chqv6iEPJZqx/3FVIU= </X509Certificate>
</X509Data>
</KeyInfo>
</Signature>
</EnvioDTE>'''
    
    if request.method == 'POST':
        try:
            from facturacion_electronica.dtebox_service import DTEBoxService
            
            dtebox = DTEBoxService(request.empresa)
            
            # Enviar el XML de ejemplo exacto
            resultado = dtebox.timbrar_dte(xml_ejemplo)
            
            if resultado['success']:
                messages.success(request, f'✅ Éxito! TED obtenido: {len(resultado["ted"])} caracteres')
            else:
                error = resultado['error']
                messages.error(request, f'❌ Error: {error}')
                
        except Exception as e:
            error = str(e)
            messages.error(request, f'❌ Error inesperado: {error}')
            import traceback
            traceback.print_exc()
    
    context = {
        'resultado': resultado,
        'error': error,
        'empresa': request.empresa,
        'xml_ejemplo_preview': xml_ejemplo[:500] + '...' if len(xml_ejemplo) > 500 else xml_ejemplo,
    }
    
    return render(request, 'facturacion_electronica/probar_dtebox_xml_ejemplo.html', context)


@login_required
@requiere_empresa
def descargar_pdf_gdexpress(request, dte_id):
    """
    Descarga el PDF de un DTE desde GDExpress/DTEBox (Alias de compatibilidad)
    """
    return sincronizar_con_gdexpress(request, dte_id)


@login_required
@requiere_empresa
def sincronizar_con_gdexpress(request, dte_id):
    """
    Trae PDF y XML desde GDExpress, sincroniza el TED localmente y ofrece descarga del PDF.
    """
    from .dtebox_service import DTEBoxService
    from .models import DocumentoTributarioElectronico
    from django.contrib import messages
    from django.shortcuts import redirect, get_object_or_404
    from django.http import HttpResponse
    import base64
    from lxml import etree
    
    try:
        # Obtener el DTE
        dte = get_object_or_404(DocumentoTributarioElectronico, pk=dte_id, empresa=request.empresa)
        
        # Verificar que DTEBox esté habilitado
        if not request.empresa.dtebox_habilitado:
            messages.error(request, 'DTEBox/GDExpress no está habilitado para esta empresa.')
            return redirect('facturacion_electronica:dte_list')
        
        # Inicializar servicio DTEBox
        dtebox_service = DTEBoxService(request.empresa)
        
        print(f"[GDExpress] Sincronizando DTE ID {dte.id}, Folio {dte.folio}")
        sincronizado_xml = False
        
        # 1. Intentar traer XML para sincronizar el Timbre (TED)
        try:
            res_xml = dtebox_service.descargar_xml(dte)
            if res_xml['success']:
                xml_content = res_xml['xml_content']
                # Intentar extraer el nodo <TED> para tener el timbre oficial
                parser = etree.XMLParser(recover=True, encoding='ISO-8859-1')
                root = etree.fromstring(xml_content.encode('ISO-8859-1'), parser=parser)
                
                # Namespace del SII
                ns = {"sii": "http://www.sii.cl/SiiDte"}
                
                # Buscar el TED (Timbre Electrónico DTE)
                ted_node = root.find(".//sii:TED", namespaces=ns)
                if ted_node is None:
                    ted_node = root.find(".//TED")
                
                if ted_node is not None:
                    # Guardar el fragmento XML del TED
                    dte.timbre_electronico = etree.tostring(ted_node, encoding='unicode')
                    
                    # También buscar el TmstFirma si es posible
                    tmst_node = root.find(".//sii:TmstFirma", namespaces=ns)
                    if tmst_node is None:
                        tmst_node = root.find(".//TmstFirma")
                    
                    if tmst_node is not None:
                        dte.tmst_firma = tmst_node.text
                    
                    # Guardar cambios
                    dte.save()
                    
                    # Regenerar la imagen PDF417 localmente usando el TED oficial
                    from .pdf417_generator import PDF417Generator
                    if PDF417Generator.guardar_pdf417_en_dte(dte):
                        print(f"[GDExpress] Imagen PDF417 regenerada exitosamente.")
                    
                    sincronizado_xml = True
                    print(f"[GDExpress] Timbre (TED) sincronizado exitosamente.")
        except Exception as e_xml:
            print(f"[GDExpress] Error al intentar sincronizar XML: {str(e_xml)}")

        # 2. Descargar el PDF para el usuario
        resultado_pdf = dtebox_service.descargar_pdf(dte)
        
        if resultado_pdf['success']:
            # Crear respuesta HTTP con el PDF
            response = HttpResponse(resultado_pdf['pdf_content'], content_type='application/pdf')
            # Establecer nombre de archivo
            filename = f"DTE_{dte.tipo_dte}_{dte.folio}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            msg = f'Documento {dte.folio} sincronizado correctamente.'
            if sincronizado_xml:
                msg += ' El timbre (TED) ha sido actualizado en el sistema local.'
            
            messages.success(request, msg)
            return response
        else:
            if sincronizado_xml:
                messages.success(request, f'El timbre del folio {dte.folio} fue sincronizado, pero no se pudo recuperar el PDF de GDExpress: {resultado_pdf.get("error")}')
            else:
                messages.error(request, f'No se pudo sincronizar el documento {dte.folio}: {resultado_pdf.get("error")}')
            
            return redirect(reverse('ventas:libro_ventas') + f'#row-{dte.id}')
            
    except Exception as e:
        messages.error(request, f'Error durante la sincronización: {str(e)}')
        import traceback
        traceback.print_exc()
        return redirect('ventas:libro_ventas')


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
            return redirect(reverse('ventas:libro_ventas') + f'#row-{dte.id}')

    if dte.tipo_dte == '52':
        transferencia = getattr(dte, 'transferencias', None)
        if transferencia:
            transferencia = transferencia.first()
        if not transferencia:
            messages.error(request, 'Esta guía no está asociada a una transferencia. No se puede regenerar el XML.')
            return redirect('facturacion_electronica:dte_list')
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

            ted_xml = None
            if getattr(request.empresa, 'dtebox_habilitado', False):
                try:
                    from facturacion_electronica.dtebox_service import DTEBoxService
                    dtebox = DTEBoxService(request.empresa)
                    res_dtebox = dtebox.timbrar_dte(xml_firmado, '52')
                    if res_dtebox.get('success') and res_dtebox.get('ted'):
                        ted_xml = res_dtebox['ted']
                except Exception:
                    pass
            if not ted_xml:
                dte_service = DTEService(request.empresa)
                datos_caf = {}
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
        return redirect(reverse('ventas:libro_ventas') + f'#row-{dte.id}')

    messages.error(request, 'Solo se puede regenerar XML de Boletas (39) o Guías de Despacho (52) asociadas a una transferencia.')
    return redirect(reverse('ventas:libro_ventas') + f'#row-{dte.id}')


@login_required
@requiere_empresa
def enviar_gdexpress_directo(request, dte_id):
    """
    Envía un DTE directamente a GDExpress/DTEBox
    """
    from .dtebox_service import DTEBoxService
    
    dte = get_object_or_404(DocumentoTributarioElectronico, pk=dte_id, empresa=request.empresa)
    
    try:
        service = DTEBoxService(request.empresa)
        resultado = service.timbrar_dte(dte.xml_firmado, dte.tipo_dte)
        
        if resultado.get('success'):
            dte.timbre_electronico = resultado.get('ted', '')
            dte.track_id = resultado.get('track_id', f'DTEBOX-{dte.folio}')
            dte.estado_sii = 'enviado'
            dte.error_envio = ''
            dte.save()
            messages.success(request, f'Folio {dte.folio} enviado a GDExpress - Track: {dte.track_id}')
        else:
            error = resultado.get('error', 'Error desconocido')
            dte.error_envio = error
            dte.save()
            messages.error(request, f'Error enviando folio {dte.folio}: {error[:100]}')
            
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        import traceback
    return redirect(reverse('ventas:libro_ventas') + f'#row-{dte.id}')
