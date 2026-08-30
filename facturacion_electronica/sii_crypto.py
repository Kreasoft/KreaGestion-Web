import base64
from lxml import etree
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.primitives import hashes

def load_pfx(file_path, password):
    """Carga un archivo PFX y devuelve la llave privada y el certificado público en formato PEM."""
    with open(file_path, "rb") as f:
        pfx_data = f.read()
    
    if isinstance(password, str):
        password = password.encode('utf-8')
        
    private_key, certificate, _ = pkcs12.load_key_and_certificates(pfx_data, password)
    
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    return key_pem, cert_pem, private_key


def obtener_rut_certificado(pfx_path, password):
    """
    Extrae el RUT del titular del certificado digital (.pfx).
    El SII almacena el RUT en subjectAltName con OID 1.3.6.1.4.1.8321.1.
    Este RUT debe usarse como RutEnvia en el EnvioDTE/EnvioBOLETA.
    Retorna el RUT formateado (ej: '11314755-5') o None si no lo encuentra.
    """
    import re as _re
    try:
        with open(pfx_path, 'rb') as f:
            pfx_data = f.read()
        if isinstance(password, str):
            password = password.encode('utf-8')
        _, certificate, _ = pkcs12.load_key_and_certificates(pfx_data, password)

        # Buscar en subjectAltName (OID 1.3.6.1.4.1.8321.1 = RUT titular)
        from cryptography.x509 import SubjectAlternativeName, OtherName
        from cryptography.x509.oid import ExtensionOID
        try:
            san = certificate.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            )
            for name in san.value:
                if isinstance(name, OtherName):
                    raw = name.value
                    # El valor viene codificado como IA5String: bytes con prefijo \x16\x0a
                    decoded = raw.decode('latin-1', errors='ignore')
                    ruts = _re.findall(r'\d{7,8}-[\dKk]', decoded)
                    if ruts:
                        return ruts[0].upper()
        except Exception:
            pass

        # Fallback: buscar RUT en el SerialNumber del subject
        subject_str = str(certificate.subject)
        ruts = _re.findall(r'\d{7,8}-[\dKk]', subject_str)
        if ruts:
            return ruts[0].upper()

    except Exception:
        pass
    return None



def _int_to_bytes(i):
    return i.to_bytes((i.bit_length() + 7) // 8, byteorder='big')

def sign_xml_sii(xml_str, reference_id, key_pem, cert_pem, private_key):
    """
    Firma un XML usando XML-DSIG con el perfil exigido por el SII.
    Construye el bloque <Signature> como string puro para evitar que lxml
    agregue prefijos de namespace (ns0:Signature) que el SII rechaza.
    """
    import hashlib
    import re
    from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
    from cryptography.hazmat.primitives import serialization
    from cryptography.x509 import load_pem_x509_certificate

    # 1. Parsear y canonicalizar el elemento raíz para calcular digest
    if isinstance(xml_str, str):
        xml_bytes = xml_str.encode('ISO-8859-1')
    else:
        xml_bytes = xml_str
    root = etree.fromstring(xml_bytes)

    # Canonicalizar el elemento completo (getToken)
    documento_c14n = etree.tostring(root, method='c14n')
    digest = hashlib.sha1(documento_c14n).digest()
    digest_b64 = base64.b64encode(digest).decode()

    # 2. Construir SignedInfo canónico como string (sin prefijos)
    uri = f'#{reference_id}' if reference_id else ''
    signed_info_str = (
        '<SignedInfo xmlns="http://www.w3.org/2000/09/xmldsig#">'
        '<CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>'
        '<SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>'
        f'<Reference URI="{uri}">'
        '<Transforms>'
        '<Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>'
        '</Transforms>'
        '<DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>'
        f'<DigestValue>{digest_b64}</DigestValue>'
        '</Reference>'
        '</SignedInfo>'
    )

    # 3. Canonicalizar el SignedInfo para firmar
    signed_info_root = etree.fromstring(signed_info_str.encode('utf-8'))
    signed_info_c14n = etree.tostring(signed_info_root, method='c14n')

    # 4. Firmar
    signature_bytes = private_key.sign(
        signed_info_c14n,
        asym_padding.PKCS1v15(),
        hashes.SHA1()
    )
    sig_b64 = base64.b64encode(signature_bytes).decode()

    # 5. Certificado en base64
    cert_obj = load_pem_x509_certificate(cert_pem)
    cert_der = cert_obj.public_bytes(serialization.Encoding.DER)
    cert_b64 = base64.b64encode(cert_der).decode()

    # 6. Extraer módulo y exponente para KeyValue
    pub_numbers = cert_obj.public_key().public_numbers()
    mod_b64 = base64.b64encode(
        pub_numbers.n.to_bytes((pub_numbers.n.bit_length() + 7) // 8, 'big')
    ).decode()
    exp_b64 = base64.b64encode(
        pub_numbers.e.to_bytes((pub_numbers.e.bit_length() + 7) // 8, 'big')
    ).decode()

    # 7. Construir bloque Signature completo como string limpio (sin ns0:)
    signature_block = (
        '<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">'
        + signed_info_str
        + f'<SignatureValue>{sig_b64}</SignatureValue>'
        '<KeyInfo>'
        '<KeyValue>'
        '<RSAKeyValue>'
        f'<Modulus>{mod_b64}</Modulus>'
        f'<Exponent>{exp_b64}</Exponent>'
        '</RSAKeyValue>'
        '</KeyValue>'
        '<X509Data>'
        f'<X509Certificate>{cert_b64}</X509Certificate>'
        '</X509Data>'
        '</KeyInfo>'
        '</Signature>'
    )

    # 8. Inyectar el bloque Signature dentro del XML original (antes del cierre del elemento raíz)
    # Eliminar declaración XML si existe
    xml_out = xml_str if isinstance(xml_str, str) else xml_str.decode('ISO-8859-1')
    xml_out = re.sub(r'^\s*<\?xml[^?]*\?>\s*', '', xml_out).strip()

    # Insertar Signature al final del elemento raíz (antes del último tag de cierre)
    last_close = xml_out.rfind('</')
    if last_close == -1:
        xml_out = xml_out + signature_block
    else:
        xml_out = xml_out[:last_close] + signature_block + xml_out[last_close:]

    return "<?xml version='1.0' encoding='ISO-8859-1'?>\n" + xml_out
