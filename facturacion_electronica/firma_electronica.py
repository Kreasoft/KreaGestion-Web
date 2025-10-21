"""
Servicio de Firma Electrónica para DTE
Firma XML según estándar XMLDSig del SII
"""
from lxml import etree
from signxml import XMLSigner, XMLVerifier, methods
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import base64
from datetime import datetime


class FirmadorDTE:
    """Servicio para firmar documentos tributarios electrónicos"""
    
    def __init__(self, certificado_path, password):
        """
        Inicializa el firmador con el certificado digital
        
        Args:
            certificado_path: Ruta al archivo .p12/.pfx
            password: Contraseña del certificado
        """
        self.certificado_path = certificado_path
        self.password = password
        self.private_key = None
        self.certificate = None
        self._cargar_certificado()
    
    def _cargar_certificado(self):
        """Carga el certificado digital desde el archivo .p12/.pfx"""
        try:
            # Leer el archivo del certificado
            with open(self.certificado_path, 'rb') as f:
                pfx_data = f.read()
            
            # Cargar el certificado PKCS12
            private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                pfx_data,
                self.password.encode() if isinstance(self.password, str) else self.password,
                backend=default_backend()
            )
            
            self.private_key = private_key
            self.certificate = certificate
            
            print(f"Certificado cargado exitosamente")
            print(f"   Subject: {certificate.subject}")
            print(f"   Issuer: {certificate.issuer}")
            print(f"   Valid from: {certificate.not_valid_before}")
            print(f"   Valid until: {certificate.not_valid_after}")
            
        except Exception as e:
            raise ValueError(f"Error al cargar el certificado: {str(e)}")
    
    def firmar_token_request(self, xml_string):
        """
        Firma una solicitud de token (getToken) para el SII
        Formato esperado: <getToken><item><Semilla>XXX</Semilla></item></getToken>
        
        Args:
            xml_string: String con el XML de solicitud de token (sin declaración XML)
            
        Returns:
            str: XML firmado (sin declaración XML para embeber en SOAP)
        """
        try:
            # Parsear el XML
            if isinstance(xml_string, str):
                xml_string = xml_string.encode('utf-8')
            
            root = etree.fromstring(xml_string)
            
            # Para getToken, firmamos el elemento raíz directamente
            # Monkey-patch para permitir SHA1 (requerido por SII Chile)
            import signxml.signer
            original_check = signxml.signer.XMLSigner.check_deprecated_methods
            signxml.signer.XMLSigner.check_deprecated_methods = lambda self: None
            
            signer = XMLSigner(
                method=methods.enveloped,
                signature_algorithm="rsa-sha1",
                digest_algorithm="sha1",
                c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
            )
            
            # Restaurar el check original
            signxml.signer.XMLSigner.check_deprecated_methods = original_check
            
            # Firmar el documento
            signed_root = signer.sign(
                root,
                key=self.private_key,
                cert=[self.certificate]
            )
            
            # Convertir a string SIN declaración XML (para embeber en SOAP)
            xml_firmado = etree.tostring(
                signed_root,
                pretty_print=False,  # Compacto
                xml_declaration=False,  # Sin declaración XML
                encoding='unicode'
            )
            
            print(f"Solicitud de token firmada exitosamente")
            
            return xml_firmado
            
        except Exception as e:
            print(f"ERROR al firmar solicitud de token: {str(e)}")
            raise
    
    def firmar_xml(self, xml_string):
        """
        Firma un XML según el estándar XMLDSig del SII
        
        Args:
            xml_string: String con el XML a firmar
            
        Returns:
            str: XML firmado
        """
        try:
            # Parsear el XML
            if isinstance(xml_string, str):
                xml_string = xml_string.encode('ISO-8859-1')
            
            root = etree.fromstring(xml_string)
            
            # Buscar el elemento Documento que debe ser firmado
            documento = root.find('.//{http://www.sii.cl/SiiDte}Documento')
            if documento is None:
                documento = root.find('.//Documento')
            
            if documento is None:
                raise ValueError("No se encontró el elemento Documento en el XML")
            
            # Crear el firmador
            # Nota: El SII de Chile requiere SHA1, aunque esté deprecado
            # Monkey-patch para permitir SHA1 (requerido por SII Chile)
            import signxml.signer
            original_check = signxml.signer.XMLSigner.check_deprecated_methods
            signxml.signer.XMLSigner.check_deprecated_methods = lambda self: None
            
            signer = XMLSigner(
                method=methods.enveloped,
                signature_algorithm="rsa-sha1",
                digest_algorithm="sha1",
                c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
            )
            
            # Restaurar el check original (buena práctica)
            signxml.signer.XMLSigner.check_deprecated_methods = original_check
            
            # Firmar el documento
            signed_root = signer.sign(
                root,
                key=self.private_key,
                cert=[self.certificate],  # signxml espera una lista de certificados
                reference_uri=f"#{documento.get('ID')}"
            )
            
            # Convertir a string
            xml_firmado = etree.tostring(
                signed_root,
                pretty_print=True,
                xml_declaration=True,
                encoding='ISO-8859-1'
            ).decode('ISO-8859-1')
            
            print(f"XML firmado exitosamente")
            
            return xml_firmado
            
        except Exception as e:
            print(f"ERROR al firmar XML: {str(e)}")
            raise
    
    def generar_ted(self, dte_data, caf_data):
        """
        Genera el Timbre Electrónico Digital (TED)
        
        Args:
            dte_data: Diccionario con datos del DTE
            caf_data: Diccionario con datos del CAF
            
        Returns:
            str: XML del TED
        """
        try:
            # Crear el elemento TED
            ted = etree.Element("TED", version="1.0")
            
            # DD - Datos del Documento
            dd = etree.SubElement(ted, "DD")
            
            # RE - RUT Emisor
            etree.SubElement(dd, "RE").text = dte_data['rut_emisor']
            
            # TD - Tipo de Documento
            etree.SubElement(dd, "TD").text = dte_data['tipo_dte']
            
            # F - Folio
            etree.SubElement(dd, "F").text = str(dte_data['folio'])
            
            # FE - Fecha de Emisión
            etree.SubElement(dd, "FE").text = dte_data['fecha_emision']
            
            # RR - RUT Receptor
            etree.SubElement(dd, "RR").text = dte_data['rut_receptor']
            
            # RSR - Razón Social Receptor
            etree.SubElement(dd, "RSR").text = dte_data['razon_social_receptor'][:40]
            
            # MNT - Monto Total
            etree.SubElement(dd, "MNT").text = str(int(dte_data['monto_total']))
            
            # IT1 - Item 1 (descripción del documento)
            etree.SubElement(dd, "IT1").text = dte_data.get('item_1', 'Documento Tributario Electrónico')[:40]
            
            # CAF - Código de Autorización de Folios
            caf_element = etree.SubElement(dd, "CAF", version="1.0")
            da = etree.SubElement(caf_element, "DA")
            
            # Datos del CAF
            etree.SubElement(da, "RE").text = caf_data['rut_emisor']
            etree.SubElement(da, "RS").text = caf_data['razon_social'][:100]
            etree.SubElement(da, "TD").text = caf_data['tipo_documento']
            
            # Rango de folios
            rng = etree.SubElement(da, "RNG")
            etree.SubElement(rng, "D").text = str(caf_data['folio_desde'])
            etree.SubElement(rng, "H").text = str(caf_data['folio_hasta'])
            
            # Fecha de autorización
            etree.SubElement(da, "FA").text = caf_data['fecha_autorizacion']
            
            # Clave pública RSA
            rsapk = etree.SubElement(da, "RSAPK")
            etree.SubElement(rsapk, "M").text = caf_data['modulo']
            etree.SubElement(rsapk, "E").text = caf_data['exponente']
            
            # IDK
            if 'idk' in caf_data:
                etree.SubElement(da, "IDK").text = caf_data['idk']
            
            # Firma del CAF
            frma_caf = etree.SubElement(caf_element, "FRMA", algoritmo="SHA1withRSA")
            frma_caf.text = caf_data['firma']
            
            # TSTED - Timestamp
            etree.SubElement(dd, "TSTED").text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            
            # Convertir DD a string para firmar
            dd_string = etree.tostring(dd, method='c14n')
            
            # Firmar el DD con la clave privada del certificado
            signature = self.private_key.sign(
                dd_string,
                padding.PKCS1v15(),
                hashes.SHA1()
            )
            
            # Agregar la firma al TED
            frmt = etree.SubElement(ted, "FRMT", algoritmo="SHA1withRSA")
            frmt.text = base64.b64encode(signature).decode('ascii')
            
            # Convertir TED a string
            ted_string = etree.tostring(
                ted,
                pretty_print=True,
                xml_declaration=True,
                encoding='ISO-8859-1'
            ).decode('ISO-8859-1')
            
            print(f"TED generado exitosamente")
            
            return ted_string
            
        except Exception as e:
            print(f"ERROR al generar TED: {str(e)}")
            raise
    
    def verificar_firma(self, xml_firmado):
        """
        Verifica la firma de un XML
        
        Args:
            xml_firmado: String con el XML firmado
            
        Returns:
            bool: True si la firma es válida
        """
        try:
            if isinstance(xml_firmado, str):
                xml_firmado = xml_firmado.encode('ISO-8859-1')
            
            root = etree.fromstring(xml_firmado)
            
            # Verificar la firma
            verifier = XMLVerifier()
            verified_data = verifier.verify(root, x509_cert=self.certificate)
            
            print(f"Firma verificada exitosamente")
            return True
            
        except Exception as e:
            print(f"ERROR al verificar firma: {str(e)}")
            return False
    
    def obtener_info_certificado(self):
        """
        Obtiene información del certificado cargado
        
        Returns:
            dict: Información del certificado
        """
        if not self.certificate:
            return None
        
        return {
            'subject': str(self.certificate.subject),
            'issuer': str(self.certificate.issuer),
            'serial_number': self.certificate.serial_number,
            'not_valid_before': self.certificate.not_valid_before,
            'not_valid_after': self.certificate.not_valid_after,
            'is_valid': datetime.now() < self.certificate.not_valid_after,
        }
    
    def generar_datos_pdf417(self, ted_xml):
        """
        Genera los datos para el código PDF417 a partir del TED
        
        Args:
            ted_xml: String con el XML del TED
            
        Returns:
            str: Datos codificados para PDF417
        """
        try:
            # El PDF417 contiene el TED completo en base64
            ted_bytes = ted_xml.encode('ISO-8859-1')
            pdf417_data = base64.b64encode(ted_bytes).decode('ascii')
            
            return pdf417_data
            
        except Exception as e:
            print(f"ERROR al generar datos PDF417: {str(e)}")
            raise
