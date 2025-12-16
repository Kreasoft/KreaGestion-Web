#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de prueba para la API DTEBox - SendDocumentAsXML
Prueba el servicio con la configuración proporcionada
"""
import os
import sys
import django
import base64
from datetime import datetime

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa
from facturacion_electronica.dtebox_service import DTEBoxService


def crear_xml_dte_prueba():
    """
    Crea un XML de DTE de prueba basado en el ejemplo proporcionado
    """
    xml_ejemplo = """<?xml version="1.0" encoding="ISO-8859-1"?>
<DTE version="1.0">
    <Exportaciones ID="F181T112">
        <Encabezado>
            <IdDoc>
                <TipoDTE>112</TipoDTE>
                <Folio>181</Folio>
                <FchEmis>2018-07-30</FchEmis>
            </IdDoc>
            <Emisor>
                <RUTEmisor>77117239-3</RUTEmisor>
                <RznSoc>KREASOFT SPA</RznSoc>
            </Emisor>
            <Receptor>
                <RUTRecep>12345678-9</RUTRecep>
                <RznSocRecep>CLIENTE DE PRUEBA</RznSocRecep>
            </Receptor>
            <Totales>
                <MntTotal>10000</MntTotal>
            </Totales>
        </Encabezado>
        <Detalle>
            <NroLinDet>1</NroLinDet>
            <NmbItem>PRODUCTO DE PRUEBA</NmbItem>
            <QtyItem>1</QtyItem>
            <PrcItem>10000</PrcItem>
            <MntItem>10000</MntItem>
        </Detalle>
        <Documento>
            <TED version="1.0">
                <DD></DD>
                <FRMT algoritmo="SHA1withRSA"></FRMT>
            </TED>
        </Documento>
    </Exportaciones>
</DTE>"""
    return xml_ejemplo


def probar_dtebox_directo():
    """
    Prueba directa de la API DTEBox usando requests
    """
    import requests
    import xml.etree.ElementTree as ET
    
    print("=" * 80)
    print("PRUEBA DIRECTA DE API DTEBox - SendDocumentAsXML")
    print("=" * 80)
    print()
    
    # Configuración según ejemplo proporcionado
    url_base = "http://200.6.118.43/api/Core.svc/core/SendDocumentAsXML"
    auth_key = "0a1c295d-7853-4e2e-ac90-d7d2fd46ecf0"
    
    print(f"URL: {url_base}")
    print(f"Auth Key: {auth_key[:20]}...")
    print()
    
    # Crear XML de prueba
    xml_dte = crear_xml_dte_prueba()
    print("XML DTE generado:")
    print(xml_dte[:500])
    print("...")
    print()
    
    # Codificar en Base64
    xml_bytes = xml_dte.encode('ISO-8859-1')
    xml_base64 = base64.b64encode(xml_bytes).decode('ascii')
    print(f"XML codificado en Base64: {len(xml_base64)} caracteres")
    print(f"Base64 (primeros 200 chars): {xml_base64[:200]}...")
    print()
    
    # Crear request XML según documentación
    root = ET.Element("SendDocumentAsXMLRequest")
    root.set("xmlns", "http://gdexpress.cl/api")
    
    ET.SubElement(root, "Environment").text = "T"
    ET.SubElement(root, "Content").text = xml_base64
    # Datos reales de resolución proporcionados por el usuario
    ET.SubElement(root, "ResolutionDate").text = "2014-08-22"  # 22-08-2014
    ET.SubElement(root, "ResolutionNumber").text = "80"
    ET.SubElement(root, "PDF417Columns").text = "5"
    ET.SubElement(root, "PDF417Level").text = "2"
    ET.SubElement(root, "PDF417Type").text = "1"
    ET.SubElement(root, "TED").text = ""
    
    xml_request_str = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding='unicode', method='xml')
    xml_request = xml_request_str.encode('utf-8')
    
    print("Request XML generado:")
    print(xml_request_str)
    print()
    
    # Headers
    headers = {
        "AuthKey": auth_key,
        "Content-Type": "application/xml",
        "Accept": "application/xml"
    }
    
    print("Headers:")
    for key, value in headers.items():
        if key == "AuthKey":
            print(f"  {key}: {value[:20]}...")
        else:
            print(f"  {key}: {value}")
    print()
    
    # Enviar request
    print("Enviando request a DTEBox...")
    print("-" * 80)
    
    try:
        response = requests.post(
            url_base,
            data=xml_request,
            headers=headers,
            timeout=30,
            verify=False
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print()
        print("Response Content:")
        print(response.text)
        print()
        
        # Intentar parsear respuesta
        if response.status_code == 200:
            try:
                root_resp = ET.fromstring(response.text)
                result_elem = root_resp.find('.//{http://gdexpress.cl/api}Result') or root_resp.find('.//Result')
                description_elem = root_resp.find('.//{http://gdexpress.cl/api}Description') or root_resp.find('.//Description')
                ted_elem = root_resp.find('.//{http://gdexpress.cl/api}TED') or root_resp.find('.//TED')
                
                if result_elem is not None:
                    result = int(result_elem.text) if result_elem.text else 1
                    description = description_elem.text if description_elem is not None and description_elem.text else ''
                    ted_base64 = ted_elem.text if ted_elem is not None and ted_elem.text else ''
                    
                    print("=" * 80)
                    print("RESULTADO PARSEADO:")
                    print("=" * 80)
                    print(f"Result: {result} ({'Éxito' if result == 0 else 'Error'})")
                    print(f"Description: {description}")
                    print(f"TED recibido: {'Sí' if ted_base64 else 'No'}")
                    
                    if result == 0 and ted_base64:
                        ted_bytes = base64.b64decode(ted_base64)
                        ted_text = ted_bytes.decode('ISO-8859-1')
                        print(f"TED decodificado ({len(ted_text)} caracteres):")
                        print(ted_text[:500])
                        if len(ted_text) > 500:
                            print("...")
                    print("=" * 80)
            except Exception as e:
                print(f"Error al parsear respuesta XML: {str(e)}")
                # Intentar como JSON
                try:
                    import json
                    resp_json = response.json()
                    print("Respuesta JSON:")
                    print(json.dumps(resp_json, indent=2))
                except:
                    pass
        
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR: No se pudo conectar al servidor DTEBox")
        print(f"Error: {str(e)}")
        print()
        print("Posibles causas:")
        print("1. El servidor DTEBox no está accesible desde esta red")
        print("2. La URL es incorrecta")
        print("3. Hay un firewall bloqueando la conexión")
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


def probar_con_servicio_django():
    """
    Prueba usando el servicio DTEBoxService de Django
    """
    print("=" * 80)
    print("PRUEBA CON SERVICIO DTEBoxService DE DJANGO")
    print("=" * 80)
    print()
    
    try:
        # Buscar empresa con DTEBox habilitado o crear configuración de prueba
        empresa = Empresa.objects.filter(dtebox_habilitado=True).first()
        
        if not empresa:
            print("No se encontró ninguna empresa con DTEBox habilitado.")
            print("Creando configuración de prueba...")
            print()
            
            # Usar empresa existente o crear una de prueba
            empresa = Empresa.objects.first()
            if not empresa:
                print("ERROR: No hay empresas en la base de datos")
                return
            
            # Configurar DTEBox para prueba
            empresa.dtebox_habilitado = True
            empresa.dtebox_url = "http://200.6.118.43/api/Core.svc/Core"
            empresa.dtebox_auth_key = "0a1c295d-7853-4e2e-ac90-d7d2fd46ecf0"
            empresa.dtebox_ambiente = "T"
            empresa.dtebox_pdf417_columns = 5
            empresa.dtebox_pdf417_level = 2
            empresa.dtebox_pdf417_type = 1
            
            # Configurar resolución si no existe (datos reales proporcionados)
            if not empresa.resolucion_fecha:
                from datetime import date
                empresa.resolucion_fecha = date(2014, 8, 22)  # 22-08-2014
            if not empresa.resolucion_numero:
                empresa.resolucion_numero = 80
            
            print(f"Usando empresa: {empresa.nombre}")
            print(f"URL DTEBox: {empresa.dtebox_url}")
            print(f"Ambiente: {empresa.dtebox_ambiente}")
            print()
        
        # Crear XML de prueba
        xml_dte = crear_xml_dte_prueba()
        print("XML DTE de prueba generado")
        print()
        
        # Inicializar servicio
        print("Inicializando servicio DTEBoxService...")
        dtebox_service = DTEBoxService(empresa)
        print()
        
        # Timbrar DTE
        print("Enviando DTE a DTEBox para obtener TED...")
        print("-" * 80)
        
        resultado = dtebox_service.timbrar_dte(xml_dte)
        
        print()
        print("=" * 80)
        print("RESULTADO:")
        print("=" * 80)
        print(f"Éxito: {resultado['success']}")
        
        if resultado['success']:
            print("[OK] DTE timbrado exitosamente!")
            print(f"TED recibido: {len(resultado['ted'])} caracteres")
            print()
            print("TED (primeros 500 caracteres):")
            print(resultado['ted'][:500])
            if len(resultado['ted']) > 500:
                print("...")
        else:
            print("[ERROR] Error al timbrar DTE")
            print(f"Error: {resultado['error']}")
        print("=" * 80)
        
    except ValueError as e:
        print(f"ERROR de configuración: {str(e)}")
        print()
        print("Asegúrate de que la empresa tenga:")
        print("- dtebox_habilitado = True")
        print("- dtebox_url configurada")
        print("- dtebox_auth_key configurada")
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Configurar encoding para Windows
    import sys
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    print()
    print("=" * 80)
    print(" " * 20 + "PRUEBA DE API DTEBox" + " " * 40)
    print("=" * 80)
    print()
    
    # Opción 1: Prueba directa con requests
    print("OPCIÓN 1: Prueba directa con requests")
    print("-" * 80)
    probar_dtebox_directo()
    print()
    print()
    
    # Opción 2: Prueba con servicio Django
    print("OPCIÓN 2: Prueba con servicio Django DTEBoxService")
    print("-" * 80)
    probar_con_servicio_django()
    print()

