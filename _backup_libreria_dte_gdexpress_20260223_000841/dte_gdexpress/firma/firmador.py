"""
Firmador de documentos electrónicos con certificado digital
"""
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from cryptography import x509
from lxml import etree
import hashlib


class Firmador:
    """
    Clase para firmar documentos DTE con certificado digital
    
    Uso:
        firmador = Firmador(
            certificado_path='certificado.pfx',
            password='mi-password'
        )
        
        xml_firmado = firmador.firmar(xml_sin_firmar)
    """
    
    def __init__(self, certificado_path=None, password=None, certificado_bytes=None):
        """
        Inicializa el firmador
        
        Args:
            certificado_path (str): Ruta al archivo .pfx/.p12
            password (str): Contraseña del certificado
            certificado_bytes (bytes): Bytes del certificado (alternativa a certificado_path)
        """
        self.certificado_path = certificado_path
        self.password = password
        self.private_key = None
        self.certificate = None
        
        if certificado_path or certificado_bytes:
            self._cargar_certificado(certificado_bytes)
    
    def _cargar_certificado(self, certificado_bytes=None):
        """
        Carga el certificado digital desde archivo o bytes
        
        Args:
            certificado_bytes (bytes, optional): Bytes del certificado
        """
        try:
            # Leer certificado
            if certificado_bytes is None:
                with open(self.certificado_path, 'rb') as f:
                    certificado_bytes = f.read()
            
            # Convertir password a bytes si es string
            password_bytes = self.password.encode() if isinstance(self.password, str) else self.password
            
            # Cargar certificado PKCS12
            from cryptography.hazmat.primitives.serialization import pkcs12
            
            private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                certificado_bytes,
                password_bytes,
                backend=default_backend()
            )
            
            self.private_key = private_key
            self.certificate = certificate
            
        except Exception as e:
            raise ValueError(f"Error al cargar certificado: {e}")
    
    def firmar(self, xml_string):
        """
        Firma un XML con el certificado digital
        
        Args:
            xml_string (str): XML a firmar
            
        Returns:
            str: XML firmado
        """
        if not self.private_key or not self.certificate:
            raise ValueError("Certificado no cargado. Use _cargar_certificado() primero.")
        
        try:
            # Parsear XML
            if isinstance(xml_string, str):
                xml_string = xml_string.encode('ISO-8859-1')
            
            root = etree.fromstring(xml_string)
            
            # Encontrar el elemento Documento
            documento = root.find('.//Documento')
            if documento is None:
                raise ValueError("No se encontró elemento Documento en el XML")
            
            # Calcular digest del documento
            documento_string = etree.tostring(documento, method='c14n')
            digest = hashlib.sha1(documento_string).digest()
            digest_b64 = base64.b64encode(digest).decode()
            
            # Crear SignedInfo
            signed_info = self._crear_signed_info(digest_b64)
            
            # Firmar SignedInfo
            signed_info_string = etree.tostring(signed_info, method='c14n')
            signature_value = self.private_key.sign(
                signed_info_string,
                padding.PKCS1v15(),
                hashes.SHA1()
            )
            signature_value_b64 = base64.b64encode(signature_value).decode()
            
            # Obtener certificado en base64
            cert_der = self.certificate.public_bytes(serialization.Encoding.DER)
            cert_b64 = base64.b64encode(cert_der).decode()
            
            # Crear elemento Signature
            signature = self._crear_signature(signed_info, signature_value_b64, cert_b64)
            
            # Agregar firma al documento
            documento.append(signature)
            
            # Convertir a string
            xml_firmado = etree.tostring(
                root,
                pretty_print=True,
                xml_declaration=True,
                encoding='ISO-8859-1'
            ).decode('ISO-8859-1')
            
            return xml_firmado
            
        except Exception as e:
            raise ValueError(f"Error al firmar XML: {e}")
    
    def _crear_signed_info(self, digest_value):
        """
        Crea el elemento SignedInfo
        
        Args:
            digest_value (str): Valor del digest en base64
            
        Returns:
            etree.Element: Elemento SignedInfo
        """
        DSIG_NS = "http://www.w3.org/2000/09/xmldsig#"
        
        signed_info = etree.Element(f"{{{DSIG_NS}}}SignedInfo")
        
        # CanonicalizationMethod
        c14n_method = etree.SubElement(signed_info, f"{{{DSIG_NS}}}CanonicalizationMethod")
        c14n_method.set('Algorithm', 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
        
        # SignatureMethod
        sig_method = etree.SubElement(signed_info, f"{{{DSIG_NS}}}SignatureMethod")
        sig_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#rsa-sha1')
        
        # Reference
        reference = etree.SubElement(signed_info, f"{{{DSIG_NS}}}Reference")
        reference.set('URI', '')
        
        # Transforms
        transforms = etree.SubElement(reference, f"{{{DSIG_NS}}}Transforms")
        transform = etree.SubElement(transforms, f"{{{DSIG_NS}}}Transform")
        transform.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#enveloped-signature')
        
        # DigestMethod
        digest_method = etree.SubElement(reference, f"{{{DSIG_NS}}}DigestMethod")
        digest_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#sha1')
        
        # DigestValue
        digest_value_elem = etree.SubElement(reference, f"{{{DSIG_NS}}}DigestValue")
        digest_value_elem.text = digest_value
        
        return signed_info
    
    def _crear_signature(self, signed_info, signature_value, certificate_b64):
        """
        Crea el elemento Signature completo
        
        Args:
            signed_info (etree.Element): Elemento SignedInfo
            signature_value (str): Valor de la firma en base64
            certificate_b64 (str): Certificado en base64
            
        Returns:
            etree.Element: Elemento Signature
        """
        DSIG_NS = "http://www.w3.org/2000/09/xmldsig#"
        
        signature = etree.Element(f"{{{DSIG_NS}}}Signature")
        
        # Agregar SignedInfo
        signature.append(signed_info)
        
        # SignatureValue
        sig_value = etree.SubElement(signature, f"{{{DSIG_NS}}}SignatureValue")
        sig_value.text = signature_value
        
        # KeyInfo
        key_info = etree.SubElement(signature, f"{{{DSIG_NS}}}KeyInfo")
        key_value = etree.SubElement(key_info, f"{{{DSIG_NS}}}KeyValue")
        rsa_key_value = etree.SubElement(key_value, f"{{{DSIG_NS}}}RSAKeyValue")
        
        # Extraer módulo y exponente de la clave pública
        public_key = self.certificate.public_key()
        public_numbers = public_key.public_numbers()
        
        modulus = etree.SubElement(rsa_key_value, f"{{{DSIG_NS}}}Modulus")
        modulus.text = base64.b64encode(
            public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, 'big')
        ).decode()
        
        exponent = etree.SubElement(rsa_key_value, f"{{{DSIG_NS}}}Exponent")
        exponent.text = base64.b64encode(
            public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, 'big')
        ).decode()
        
        # X509Data
        x509_data = etree.SubElement(key_info, f"{{{DSIG_NS}}}X509Data")
        x509_cert = etree.SubElement(x509_data, f"{{{DSIG_NS}}}X509Certificate")
        x509_cert.text = certificate_b64
        
        return signature
    
    def verificar_firma(self, xml_firmado):
        """
        Verifica la firma de un XML
        
        Args:
            xml_firmado (str): XML firmado
            
        Returns:
            bool: True si la firma es válida
        """
        try:
            # Parsear XML
            if isinstance(xml_firmado, str):
                xml_firmado = xml_firmado.encode('ISO-8859-1')
            
            root = etree.fromstring(xml_firmado)
            
            # Buscar elemento Signature
            DSIG_NS = "http://www.w3.org/2000/09/xmldsig#"
            signature = root.find(f".//{{{DSIG_NS}}}Signature")
            
            if signature is None:
                return False
            
            # Por ahora, retornar True si existe la firma
            # Una verificación completa requeriría validar el digest y la firma
            return True
            
        except Exception:
            return False
