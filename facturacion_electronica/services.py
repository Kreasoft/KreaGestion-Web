"""
Servicios para Facturación Electrónica
"""
from django.db import transaction
from django.utils import timezone
from .models import ArchivoCAF, DocumentoTributarioElectronico
import base64
import qrcode
from io import BytesIO


class FolioService:
    """Servicio para gestionar folios de documentos tributarios"""
    
    @staticmethod
    def obtener_siguiente_folio(empresa, tipo_documento):
        """
        Obtiene el siguiente folio disponible para un tipo de documento

        Args:
            empresa: Instancia de Empresa
            tipo_documento: Código del tipo de documento (33, 39, etc.)

        Returns:
            tuple: (folio, caf) si hay folios disponibles
            tuple: (None, None) si no hay folios disponibles
        """
        # Verificar si está en modo de reutilización de folios (solo para certificación)
        modo_reutilizacion = empresa.modo_reutilizacion_folios
        es_certificacion = empresa.ambiente_sii == 'certificacion'

        if modo_reutilizacion and es_certificacion:
            return FolioService._obtener_folio_modo_prueba(empresa, tipo_documento)

        # Modo normal: consumir folios reales
        with transaction.atomic():
            # Buscar CAFs activos para este tipo de documento
            cafs_activos = ArchivoCAF.objects.filter(
                empresa=empresa,
                tipo_documento=tipo_documento,
                estado='activo'
            ).select_for_update().order_by('folio_desde')

            if not cafs_activos.exists():
                print(f"No hay CAFs activos para tipo documento {tipo_documento}")
                return None, None

            # Intentar obtener folio del primer CAF disponible
            for caf in cafs_activos:
                # VERIFICAR VIGENCIA DEL CAF (6 meses desde autorización)
                if not caf.esta_vigente():
                    print(f"CAF vencido: {caf.tipo_documento} ({caf.folio_desde}-{caf.folio_hasta}), autorizado el {caf.fecha_autorizacion}")
                    caf.estado = 'vencido'
                    caf.save()
                    continue

                # Verificar folios disponibles
                if caf.folios_disponibles() > 0:
                    # Incrementar el folio actual
                    caf.folio_actual += 1
                    caf.folios_utilizados += 1

                    folio = caf.folio_actual

                    # Verificar si se agotaron los folios
                    if caf.folios_disponibles() == 0:
                        caf.estado = 'agotado'
                        caf.fecha_agotamiento = timezone.now()
                        print(f"CAF agotado: {caf.tipo_documento} ({caf.folio_desde}-{caf.folio_hasta})")

                    caf.save()

                    print(f"Folio asignado: {folio} (CAF: {caf.folio_desde}-{caf.folio_hasta})")
                    return folio, caf

            # No hay folios disponibles en ningún CAF
            print(f"Todos los CAFs están agotados para tipo documento {tipo_documento}")
            return None, None

    @staticmethod
    def _obtener_folio_modo_prueba(empresa, tipo_documento):
        """
        Obtiene un folio para pruebas sin consumir folios reales

        Args:
            empresa: Instancia de Empresa
            tipo_documento: Código del tipo de documento

        Returns:
            tuple: (folio, caf) para pruebas
        """
        # Buscar CAFs activos para este tipo de documento
        cafs_activos = ArchivoCAF.objects.filter(
            empresa=empresa,
            tipo_documento=tipo_documento,
            estado='activo'
        ).order_by('folio_desde')

        if not cafs_activos.exists():
            print(f"No hay CAFs activos para tipo documento {tipo_documento}")
            return None, None

        # Usar el primer CAF disponible
        caf = cafs_activos.first()

        # VERIFICAR VIGENCIA DEL CAF
        if not caf.esta_vigente():
            print(f"CAF vencido: {caf.tipo_documento} ({caf.folio_desde}-{caf.folio_hasta})")
            caf.estado = 'vencido'
            caf.save()
            return None, None

        # Buscar un folio de prueba ÚNICO no usado aún para evitar colisión al guardar DTE
        usados = set(DocumentoTributarioElectronico.objects.filter(
            empresa=empresa,
            tipo_dte=tipo_documento
        ).values_list('folio', flat=True))

        folio_prueba = caf.folio_desde
        while folio_prueba in usados and folio_prueba <= caf.folio_hasta:
            folio_prueba += 1

        if folio_prueba > caf.folio_hasta:
            print(f"MODO PRUEBA - No hay folios libres dentro del rango del CAF {caf.folio_desde}-{caf.folio_hasta}")
            return None, None

        print(f"MODO PRUEBA - Folio asignado: {folio_prueba} (CAF: {caf.folio_desde}-{caf.folio_hasta})")
        print(f"ADVERTENCIA: Este folio NO consume del CAF real - solo para pruebas")

        return folio_prueba, caf
    
    @staticmethod
    def verificar_folios_disponibles(empresa, tipo_documento):
        """
        Verifica cuántos folios quedan disponibles para un tipo de documento
        
        Args:
            empresa: Instancia de Empresa
            tipo_documento: Código del tipo de documento
        
        Returns:
            int: Cantidad de folios disponibles
        """
        cafs_activos = ArchivoCAF.objects.filter(
            empresa=empresa,
            tipo_documento=tipo_documento,
            estado='activo'
        )
        
        total_disponibles = sum([caf.folios_disponibles() for caf in cafs_activos])
        return total_disponibles
    
    @staticmethod
    def obtener_caf_para_folio(empresa, tipo_documento, folio):
        """
        Obtiene el CAF que corresponde a un folio específico
        
        Args:
            empresa: Instancia de Empresa
            tipo_documento: Código del tipo de documento
            folio: Número de folio
        
        Returns:
            ArchivoCAF o None
        """
        try:
            caf = ArchivoCAF.objects.get(
                empresa=empresa,
                tipo_documento=tipo_documento,
                folio_desde__lte=folio,
                folio_hasta__gte=folio
            )
            return caf
        except ArchivoCAF.DoesNotExist:
            return None


class DTEService:
    """Servicio para generar y gestionar DTEs"""
    
    # Mapeo de tipos de documento de ventas a códigos SII
    TIPO_DOCUMENTO_VENTAS_TO_SII = {
        'factura': '33',        # Factura Electrónica
        'boleta': '39',         # Boleta Electrónica
        'nota_credito': '61',   # Nota de Crédito Electrónica
        'nota_debito': '56',    # Nota de Débito Electrónica
        'guia': '52',           # Guía de Despacho Electrónica
    }
    
    @staticmethod
    def mapear_tipo_documento(tipo_documento_venta):
        """
        Mapea el tipo de documento de venta al código SII
        
        Args:
            tipo_documento_venta: Tipo de documento en el sistema (factura, boleta, etc.)
        
        Returns:
            str: Código SII del documento
        """
        return DTEService.TIPO_DOCUMENTO_VENTAS_TO_SII.get(
            tipo_documento_venta,
            '39'  # Por defecto Boleta Electrónica
        )
    
    @staticmethod
    def crear_dte_desde_venta(venta, usuario=None):
        """
        Crea un DTE a partir de una venta

        Args:
            venta: Instancia de Venta
            usuario: Usuario que crea el DTE (opcional)

        Returns:
            DocumentoTributarioElectronico o None
        """
        # Verificar que la empresa tenga FE activada
        if not venta.empresa.facturacion_electronica:
            print(f"❌ La empresa {venta.empresa.nombre} no tiene FE activada")
            return None
        
        # Mapear tipo de documento
        tipo_doc_sii = DTEService.mapear_tipo_documento(venta.tipo_documento)
        
        # Obtener folio
        folio, caf = FolioService.obtener_siguiente_folio(venta.empresa, tipo_doc_sii)
        
        if folio is None:
            print(f"❌ No hay folios disponibles para {venta.tipo_documento}")
            return None
        
        # Crear el DTE
        with transaction.atomic():
            # Generar timbre electrónico
            timbre_electronico = DTEService.generar_timbre_electronico(dte)

            # Generar imagen PDF417
            pdf417_imagen = DTEService.generar_pdf417_imagen(dte)

            dte = DocumentoTributarioElectronico.objects.create(
                empresa=venta.empresa,
                tipo_documento=tipo_doc_sii,
                folio=folio,
                fecha_emision=venta.fecha,
                usuario_creacion=usuario or venta.usuario_creacion,

                # Datos del emisor (empresa)
                rut_emisor=venta.empresa.rut,
                razon_social_emisor=venta.empresa.get_razon_social_dte(),
                giro_emisor=venta.empresa.get_giro_dte(),
                direccion_emisor=venta.empresa.get_direccion_dte(),
                comuna_emisor=venta.empresa.get_comuna_dte(),
                ciudad_emisor=venta.empresa.get_ciudad_dte(),

                # Datos del receptor (cliente)
                rut_receptor=venta.cliente.rut if venta.cliente else '66666666-6',
                razon_social_receptor=venta.cliente.razon_social if venta.cliente else 'Cliente Genérico',
                giro_receptor=venta.cliente.giro if venta.cliente else '',
                direccion_receptor=venta.cliente.direccion if venta.cliente else '',
                comuna_receptor=venta.cliente.comuna if venta.cliente else '',
                ciudad_receptor=venta.cliente.ciudad if venta.cliente else '',

                # Montos
                monto_neto=venta.subtotal,
                monto_iva=venta.iva,
                monto_total=venta.total,

                # Timbre electrónico y PDF417
                timbre_electronico=timbre_electronico,

                # Referencias
                venta=venta,
                caf=caf,

                # Estado inicial
                estado_sii='generado',
                estado_envio='no_enviado'
            )

            # Guardar imagen PDF417 si se generó correctamente
            if pdf417_imagen:
                from django.core.files.base import ContentFile
                dte.timbre_pdf417.save(
                    f'pdf417_{dte.id}.png',
                    ContentFile(pdf417_imagen),
                    save=True
                )
            
            print(f"✅ DTE creado: Tipo {tipo_doc_sii}, Folio {folio}")
            return dte
    
    @staticmethod
    def verificar_disponibilidad_folios(empresa):
        """
        Verifica la disponibilidad de folios para todos los tipos de documento
        
        Args:
            empresa: Instancia de Empresa
        
        Returns:
            dict: Diccionario con la disponibilidad por tipo de documento
        """
        disponibilidad = {}
        
        for tipo_venta, tipo_sii in DTEService.TIPO_DOCUMENTO_VENTAS_TO_SII.items():
            folios_disponibles = FolioService.verificar_folios_disponibles(empresa, tipo_sii)
            disponibilidad[tipo_venta] = {
                'tipo_sii': tipo_sii,
                'folios_disponibles': folios_disponibles,
                'disponible': folios_disponibles > 0
            }
        
        return disponibilidad

    @staticmethod
    def generar_timbre_electronico(dte):
        """
        Genera el Timbre Electrónico Digital (TED) para un DTE

        Args:
            dte: Instancia de DocumentoTributarioElectronico

        Returns:
            str: TED en formato XML
        """
        # Crear el TED según formato SII
        ted_xml = f'''<?xml version="1.0" encoding="ISO-8859-1"?>
<TED version="1.0">
    <DD>
        <RE>{dte.empresa.rut}</RE>
        <TD>{dte.tipo_documento}</TD>
        <F>{dte.folio}</F>
        <FE>{dte.fecha_emision.strftime('%Y-%m-%d')}</FE>
        <RR>{dte.rut_receptor}</RR>
        <RSR>{dte.razon_social_receptor}</RSR>
        <MNT>{int(dte.monto_total)}</MNT>
        <IT1>{dte.get_tipo_documento_display()}</IT1>
        <CAF version="1.0">
            <DA>
                <RE>{dte.caf.empresa.rut}</RE>
                <RS>{dte.caf.empresa.razon_social_sii or dte.caf.empresa.razon_social}</RS>
                <TD>{dte.caf.tipo_documento}</TD>
                <RNG>
                    <D>{dte.caf.folio_desde}</D>
                    <H>{dte.caf.folio_hasta}</H>
                </RNG>
                <FA>{dte.caf.fecha_autorizacion.strftime('%Y-%m-%d')}</FA>
                <RSAPK>
                    <M>{dte.caf.firma_electronica}</M>
                    <E>N</E>
                </RSAPK>
            </DA>
            <FRMA algoritmo="SHA1withRSA">
                <signature>{dte.caf.firma_electronica}</signature>
            </FRMA>
        </CAF>
        <TSTED>{timezone.now().strftime('%Y-%m-%dT%H:%M:%S')}</TSTED>
    </DD>
</TED>'''

        return ted_xml

    @staticmethod
    def generar_pdf417_data(dte):
        """
        Genera los datos para el código PDF417 según formato SII

        Args:
            dte: Instancia de DocumentoTributarioElectronico

        Returns:
            str: Datos para generar el PDF417
        """
        # Formato requerido por SII para PDF417
        pdf417_data = (
            f"{dte.empresa.rut}|"  # RUT Emisor
            f"{dte.tipo_documento}|"  # Tipo Documento
            f"{dte.folio}|"  # Folio
            f"{dte.fecha_emision.strftime('%Y%m%d')}|"  # Fecha Emisión
            f"{dte.rut_receptor}|"  # RUT Receptor
            f"{int(dte.monto_total)}|"  # Monto Total
            f"{dte.caf.firma_electronica}"  # Firma Electrónica
        )

        return pdf417_data

    @staticmethod
    def generar_pdf417_imagen(dte):
        """
        Genera la imagen del código PDF417 para el DTE

        Args:
            dte: Instancia de DocumentoTributarioElectronico

        Returns:
            bytes: Imagen PNG del código PDF417
        """
        try:
            # Datos para el PDF417
            pdf417_data = DTEService.generar_pdf417_data(dte)

            # Generar código QR (PDF417 es un tipo de código 2D)
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(pdf417_data)
            qr.make(fit=True)

            # Crear imagen
            img = qr.make_image(fill_color="black", back_color="white")

            # Convertir a bytes
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            return buffer.getvalue()

        except Exception as e:
            print(f"Error generando imagen PDF417: {e}")
            return None

