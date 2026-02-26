"""
Prueba de obtención de token con firma correcta según estándar SII
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree
import requests
import html
import base64
from empresas.models import Empresa


def firmar_xml_con_certificado(xml_string, private_key, certificate):
    """
    Firma un XML usando la biblioteca signxml
    """
    from signxml import XMLSigner, methods
    
    # Parsear el XML
    root = etree.fromstring(xml_string.encode('utf-8'))
    
    # Monkey-patch para permitir SHA1 (requerido por SII)
    import signxml.signer
    original_check = signxml.signer.XMLSigner.check_deprecated_methods
    signxml.signer.XMLSigner.check_deprecated_methods = lambda self: None
    
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha1",
        digest_algorithm="sha1",
        c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
    )
    
    # Restaurar
    signxml.signer.XMLSigner.check_deprecated_methods = original_check
    
    # Firmar
    signed_root = signer.sign(
        root,
        key=private_key,
        cert=[certificate]
    )
    
    # Convertir a string
    xml_firmado = etree.tostring(
        signed_root,
        pretty_print=False,
        xml_declaration=False,
        encoding='unicode'
    )
    
    return xml_firmado


def obtener_token_sii():
    """
    Obtiene un token del SII usando el certificado de la empresa
    """
    # Cargar empresa
    empresa = Empresa.objects.get(pk=1)
    
    print(f"Empresa: {empresa.nombre}")
    print(f"RUT: {empresa.rut}")
    print(f"Certificado: {empresa.certificado_digital.path}")
    
    # Cargar certificado
    with open(empresa.certificado_digital.path, 'rb') as f:
        pfx_data = f.read()
    
    private_key, certificate, additional = pkcs12.load_key_and_certificates(
        pfx_data,
        empresa.password_certificado.encode(),
        backend=default_backend()
    )
    
    # 1. Obtener semilla
    print("\n1. Obteniendo semilla...")
    url_semilla = "https://maullin.sii.cl/DTEWS/CrSeed.jws?WSDL"
    
    try:
        from zeep import Client
        client = Client(url_semilla)
        respuesta = client.service.getSeed()
        print(f"Respuesta getSeed: {respuesta}")
        
        # Extraer semilla del XML
        root = etree.fromstring(respuesta.encode('utf-8'))
        semilla_elem = root.find('.//SEMILLA')
        if semilla_elem is not None:
            semilla = semilla_elem.text
            print(f"✅ Semilla obtenida: {semilla}")
        else:
            print("❌ No se encontró semilla en la respuesta")
            return
            
    except Exception as e:
        print(f"❌ Error al obtener semilla: {e}")
        return
    
    # 2. Crear y firmar getToken
    print("\n2. Creando y firmando getToken...")
    
    gettoken = etree.Element("getToken")
    item = etree.SubElement(gettoken, "item")
    semilla_elem = etree.SubElement(item, "Semilla")
    semilla_elem.text = semilla
    
    gettoken_string = etree.tostring(
        gettoken,
        pretty_print=False,
        xml_declaration=False,
        encoding='unicode'
    )
    
    print(f"XML a firmar: {gettoken_string}")
    
    # Firmar
    try:
        gettoken_firmado = firmar_xml_con_certificado(gettoken_string, private_key, certificate)
        print(f"✅ XML firmado correctamente")
        print(f"XML firmado: {gettoken_firmado[:200]}...")
        
        # Guardar para debug
        with open('gettoken_firmado_prueba.xml', 'w', encoding='utf-8') as f:
            f.write(gettoken_firmado)
        print("   Guardado en: gettoken_firmado_prueba.xml")
        
    except Exception as e:
        print(f"❌ Error al firmar: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. Enviar a getToken
    print("\n3. Enviando a getToken...")
    url_token = "https://maullin.sii.cl/DTEWS/GetTokenFromSeed.jws?WSDL"
    
    # Escapar el XML firmado
    gettoken_escapado = html.escape(gettoken_firmado)
    
    # Crear SOAP request
    soap_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                  xmlns:def="http://DefaultNamespace">
   <soapenv:Header/>
   <soapenv:Body>
      <def:getToken>{gettoken_escapado}</def:getToken>
   </soapenv:Body>
</soapenv:Envelope>"""
    
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': '',
    }
    
    try:
        response = requests.post(
            url_token.replace('?WSDL', ''),
            data=soap_request.encode('utf-8'),
            headers=headers,
            timeout=30,
            verify=True
        )
        
        print(f"Status: {response.status_code}")
        print(f"Respuesta:\n{response.text[:1000]}")
        
        if response.status_code == 200:
            # Parsear respuesta
            root = etree.fromstring(response.content)
            token_return = root.find('.//{http://DefaultNamespace}getTokenReturn')
            if token_return is None:
                token_return = root.find('.//getTokenReturn')
            
            if token_return is not None and token_return.text:
                xml_decodificado = html.unescape(token_return.text)
                print(f"\n✅ XML decodificado: {xml_decodificado[:500]}")
                
                # Parsear el XML interno
                root_interno = etree.fromstring(xml_decodificado.encode('utf-8'))
                token_elem = root_interno.find('.//TOKEN')
                if token_elem is not None:
                    print(f"\n🎉 TOKEN OBTENIDO: {token_elem.text}")
                else:
                    print("\n❌ No se encontró TOKEN en la respuesta")
                    # Buscar error
                    estado = root_interno.find('.//ESTADO')
                    if estado is not None:
                        print(f"   Estado: {estado.text}")
        else:
            print(f"\n❌ Error HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error al enviar: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    obtener_token_sii()
