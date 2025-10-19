"""
Servicio integrador para generación, firma y envío de DTE
"""
from django.db import transaction
from django.utils import timezone
from .models import DocumentoTributarioElectronico, ArchivoCAF, EnvioDTE
from .dte_generator import DTEXMLGenerator
from .firma_electronica import FirmadorDTE
from .cliente_sii import ClienteSII
from .services import FolioService
from .pdf417_generator import PDF417Generator
import os


class DTEService:
    """Servicio principal para gestión de DTE"""
    
    def __init__(self, empresa):
        """
        Inicializa el servicio de DTE
        
        Args:
            empresa: Instancia de Empresa
        """
        self.empresa = empresa
        
        # Verificar que la empresa tenga FE activada
        if not empresa.facturacion_electronica:
            raise ValueError("La empresa no tiene facturación electrónica activada")
        
        # Verificar certificado digital
        if not empresa.certificado_digital:
            raise ValueError("La empresa no tiene certificado digital configurado")
        
        print(f"🏢 DTEService inicializado para: {empresa.nombre}")
    
    def generar_dte_desde_venta(self, venta, tipo_dte='39'):
        """
        Genera un DTE completo desde una venta
        
        Args:
            venta: Instancia de Venta
            tipo_dte: Código del tipo de DTE (33, 39, etc.)
            
        Returns:
            DocumentoTributarioElectronico: DTE generado y firmado
        """
        try:
            with transaction.atomic():
                # 1. Obtener folio
                print(f"\n📋 Paso 1: Obteniendo folio para tipo {tipo_dte}")
                folio, caf = FolioService.obtener_siguiente_folio(self.empresa, tipo_dte)
                
                if folio is None:
                    raise ValueError(f"No hay folios disponibles para tipo de documento {tipo_dte}")
                
                print(f"✅ Folio asignado: {folio}")
                
                # 2. Generar XML del DTE
                print(f"\n📄 Paso 2: Generando XML del DTE")
                generator = DTEXMLGenerator(self.empresa, venta, tipo_dte, folio, caf)
                xml_sin_firmar = generator.generar_xml()
                
                print(f"✅ XML generado ({len(xml_sin_firmar)} bytes)")
                
                # 3. Firmar el XML
                print(f"\n🔐 Paso 3: Firmando XML")
                firmador = self._obtener_firmador()
                xml_firmado = firmador.firmar_xml(xml_sin_firmar)
                
                print(f"✅ XML firmado")
                
                # 4. Generar TED (Timbre Electrónico)
                print(f"\n🎫 Paso 4: Generando TED")
                ted_xml = self._generar_ted(venta, tipo_dte, folio, caf, firmador)
                
                print(f"✅ TED generado")
                
                # 5. Generar datos para PDF417
                print(f"\n📊 Paso 5: Generando datos PDF417")
                pdf417_data = firmador.generar_datos_pdf417(ted_xml)
                
                # 6. Crear registro del DTE
                print(f"\n💾 Paso 6: Guardando DTE en base de datos")
                dte = self._crear_registro_dte(
                    venta=venta,
                    tipo_dte=tipo_dte,
                    folio=folio,
                    caf=caf,
                    xml_sin_firmar=xml_sin_firmar,
                    xml_firmado=xml_firmado,
                    ted_xml=ted_xml,
                    pdf417_data=pdf417_data
                )
                
                print(f"✅ DTE guardado - ID: {dte.id}")
                
                # 7. Generar imagen PDF417 del timbre
                print(f"\n🖼️ Paso 7: Generando imagen PDF417")
                PDF417Generator.guardar_pdf417_en_dte(dte)
                
                print(f"\n🎉 DTE generado exitosamente: Tipo {tipo_dte}, Folio {folio}")
                
                return dte
                
        except Exception as e:
            print(f"\n❌ Error al generar DTE: {str(e)}")
            raise
    
    def enviar_dte_al_sii(self, dte):
        """
        Envía un DTE al SII
        
        Args:
            dte: Instancia de DocumentoTributarioElectronico
            
        Returns:
            dict: Respuesta del SII
        """
        try:
            print(f"\n🌐 Enviando DTE al SII - Tipo {dte.tipo_dte}, Folio {dte.folio}")
            
            # 1. Inicializar cliente SII
            cliente_sii = ClienteSII(ambiente=self.empresa.ambiente_sii)
            
            # 2. Obtener firmador
            firmador = self._obtener_firmador()
            
            # 3. Obtener semilla
            print(f"🔑 Obteniendo semilla del SII...")
            semilla = cliente_sii.obtener_semilla()
            
            # 4. Obtener token
            print(f"🎟️ Obteniendo token de autenticación...")
            token = cliente_sii.obtener_token(semilla, firmador)
            
            # 5. Crear SetDTE
            print(f"📦 Creando SetDTE...")
            caratula = {
                'rut_emisor': self.empresa.rut,
                'rut_envia': self.empresa.rut,  # Puede ser diferente si es un intermediario
                'fecha_resolucion': self.empresa.resolucion_fecha.strftime('%Y-%m-%d'),
                'numero_resolucion': self.empresa.resolucion_numero,
            }
            
            set_dte_xml = cliente_sii.crear_set_dte([dte.xml_firmado], caratula)
            
            # 6. Firmar el SetDTE
            print(f"🔐 Firmando SetDTE...")
            set_dte_firmado = firmador.firmar_xml(set_dte_xml)
            
            # 7. Enviar al SII
            print(f"📤 Enviando al SII...")
            respuesta = cliente_sii.enviar_dte(
                xml_envio=set_dte_firmado,
                token=token,
                rut_emisor=self.empresa.rut,
                rut_envia=self.empresa.rut
            )
            
            # 8. Actualizar estado del DTE
            with transaction.atomic():
                dte.estado_sii = 'enviado'
                dte.track_id = respuesta.get('track_id')
                dte.fecha_envio_sii = timezone.now()
                dte.respuesta_sii = respuesta.get('respuesta_completa')
                dte.save()
            
            print(f"✅ DTE enviado exitosamente - Track ID: {respuesta.get('track_id')}")
            
            return respuesta
            
        except Exception as e:
            print(f"❌ Error al enviar DTE al SII: {str(e)}")
            
            # Actualizar estado del DTE
            with transaction.atomic():
                dte.estado_sii = 'error_envio'
                dte.error_envio = str(e)
                dte.save()
            
            raise
    
    def consultar_estado_dte(self, dte):
        """
        Consulta el estado de un DTE en el SII
        
        Args:
            dte: Instancia de DocumentoTributarioElectronico
            
        Returns:
            dict: Estado del DTE
        """
        try:
            if not dte.track_id:
                raise ValueError("El DTE no tiene Track ID. Debe ser enviado primero.")
            
            print(f"\n🔍 Consultando estado del DTE - Track ID: {dte.track_id}")
            
            # Inicializar cliente SII
            cliente_sii = ClienteSII(ambiente=self.empresa.ambiente_sii)
            
            # Obtener firmador y token
            firmador = self._obtener_firmador()
            semilla = cliente_sii.obtener_semilla()
            token = cliente_sii.obtener_token(semilla, firmador)
            
            # Consultar estado
            estado = cliente_sii.consultar_estado_dte(
                track_id=dte.track_id,
                token=token,
                rut_emisor=self.empresa.rut
            )
            
            # Actualizar estado del DTE
            with transaction.atomic():
                if estado['estado'] == 'ACEPTADO':
                    dte.estado_sii = 'aceptado'
                elif estado['estado'] == 'RECHAZADO':
                    dte.estado_sii = 'rechazado'
                
                dte.glosa_sii = estado.get('glosa')
                dte.fecha_consulta_estado = timezone.now()
                dte.save()
            
            print(f"✅ Estado consultado: {estado['estado']}")
            
            return estado
            
        except Exception as e:
            print(f"❌ Error al consultar estado: {str(e)}")
            raise
    
    def _obtener_firmador(self):
        """Obtiene una instancia del firmador con el certificado de la empresa"""
        certificado_path = self.empresa.certificado_digital.path
        password = self.empresa.password_certificado
        
        return FirmadorDTE(certificado_path, password)
    
    def _generar_ted(self, venta, tipo_dte, folio, caf, firmador):
        """Genera el TED (Timbre Electrónico Digital)"""
        # Preparar datos del DTE
        dte_data = {
            'rut_emisor': self.empresa.rut,
            'tipo_dte': tipo_dte,
            'folio': folio,
            'fecha_emision': venta.fecha.strftime('%Y-%m-%d'),
            'rut_receptor': venta.cliente.rut if venta.cliente else '66666666-6',
            'razon_social_receptor': (venta.cliente.razon_social if venta.cliente 
                                     else 'Cliente Genérico'),
            'monto_total': venta.total,
            'item_1': 'Documento Tributario Electrónico',
        }
        
        # Preparar datos del CAF
        caf_data = {
            'rut_emisor': self.empresa.rut,
            'razon_social': self.empresa.razon_social_sii or self.empresa.razon_social,
            'tipo_documento': tipo_dte,
            'folio_desde': caf.folio_desde,
            'folio_hasta': caf.folio_hasta,
            'fecha_autorizacion': caf.fecha_autorizacion.strftime('%Y-%m-%d'),
            'modulo': 'MODULO_RSA',  # Extraer del CAF real
            'exponente': 'EXPONENTE_RSA',  # Extraer del CAF real
            'firma': caf.firma_electronica,
        }
        
        return firmador.generar_ted(dte_data, caf_data)
    
    def _crear_registro_dte(self, venta, tipo_dte, folio, caf, xml_sin_firmar, 
                           xml_firmado, ted_xml, pdf417_data):
        """Crea el registro del DTE en la base de datos"""
        
        # Datos del receptor
        if venta.cliente:
            rut_receptor = venta.cliente.rut
            razon_social_receptor = venta.cliente.razon_social or venta.cliente.nombre
            direccion_receptor = venta.cliente.direccion or ''
            comuna_receptor = venta.cliente.comuna or ''
        else:
            rut_receptor = '66666666-6'
            razon_social_receptor = 'Cliente Genérico'
            direccion_receptor = ''
            comuna_receptor = ''
        
        # Crear el DTE
        dte = DocumentoTributarioElectronico.objects.create(
            empresa=self.empresa,
            venta=venta,
            caf_utilizado=caf,
            tipo_dte=tipo_dte,
            folio=folio,
            fecha_emision=venta.fecha,
            
            # Emisor
            rut_emisor=self.empresa.rut,
            razon_social_emisor=self.empresa.razon_social_sii or self.empresa.razon_social,
            giro_emisor=self.empresa.giro_sii or self.empresa.giro,
            direccion_emisor=self.empresa.direccion_casa_matriz or self.empresa.direccion,
            comuna_emisor=self.empresa.comuna_casa_matriz or self.empresa.comuna,
            
            # Receptor
            rut_receptor=rut_receptor,
            razon_social_receptor=razon_social_receptor,
            direccion_receptor=direccion_receptor,
            comuna_receptor=comuna_receptor,
            
            # Montos
            monto_neto=venta.subtotal,
            monto_iva=venta.iva,
            monto_total=venta.total,
            
            # XML y Timbre
            xml_dte=xml_sin_firmar,
            xml_firmado=xml_firmado,
            timbre_electronico=ted_xml,
            datos_pdf417=pdf417_data,
            
            # Estado
            estado_sii='generado',
        )
        
        return dte
