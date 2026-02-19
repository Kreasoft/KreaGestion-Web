"""
Método timbrar_dte corregido basado en libreria_dte_gdexpress
Copiar este código al método timbrar_dte en dtebox_service.py
"""

def timbrar_dte(self, xml_firmado):
    """
    Envía el XML a DTEBox para obtener el TED.
    Implementación basada en libreria_dte_gdexpress/cliente.py
    """
    try:
        import base64
        import urllib.request
        import urllib.error
        
        # 1. Limpieza del XML usando lxml (NO regex)
        from lxml import etree
        
        # Asegurar bytes
        if isinstance(xml_firmado, str):
            xml_bytes = xml_firmado.encode('ISO-8859-1')
        else:
            xml_bytes = xml_firmado
            
        root_xml = etree.fromstring(xml_bytes)
        
        # Si es EnvioDTE, extraer el DTE interno
        if 'EnvioDTE' in root_xml.tag:
            print("[DTEBox] Detectado EnvioDTE, extrayendo DTE interno...")
            ns_sii = "http://www.sii.cl/SiiDte"
            dte_interno = root_xml.find(f'.//{{{ns_sii}}}DTE')
            if dte_interno is None:
                dte_interno = root_xml.find('.//DTE')
            
            if dte_interno is not None:
                root_xml = dte_interno
                print("[DTEBox] DTE interno extraído")
        
        # Remover Signature
        ns_dsig = "http://www.w3.org/2000/09/xmldsig#"
        for sig in root_xml.findall(f'.//{{{ns_dsig}}}Signature'):
            sig.getparent().remove(sig)
        
        # Remover TED
        ns_sii = "http://www.sii.cl/SiiDte"
        for ted_elem in root_xml.findall(f'.//{{{ns_sii}}}TED'):
            ted_elem.getparent().remove(ted_elem)
        for ted_elem in root_xml.findall('.//TED'):
            ted_elem.getparent().remove(ted_elem)
            
        # Serializar XML limpio
        xml_clean = etree.tostring(root_xml, encoding='ISO-8859-1')
        
        # Codificar a Base64
        xml_b64 = base64.b64encode(xml_clean).decode('ascii')
        
        print(f"[DTEBox] XML limpio: {len(xml_clean)} bytes")
        print(f"[DTEBox] Base64: {len(xml_b64)} caracteres")
        
        # 2. Validar datos de resolución
        if not self.empresa.resolucion_fecha:
            return {
                'success': False,
                'ted': None,
                'error': 'La fecha de resolución SII no está configurada'
            }
        
        if not self.empresa.resolucion_numero:
            return {
                'success': False,
                'ted': None,
                'error': 'El número de resolución SII no está configurado'
            }
        
        # 3. Construir Request XML (EXACTO como libreria_dte_gdexpress)
        ambiente_codigo = self.ambiente  # Ya viene como 'T' o 'P'
        resolution_date = self.empresa.resolucion_fecha.strftime('%Y-%m-%d')
        resolution_number = int(self.empresa.resolucion_numero)
        
        import xml.etree.ElementTree as ET
        
        req_root = ET.Element("SendDocumentAsXMLRequest")
        req_root.set("xmlns", "http://gdexpress.cl/api")
        
        ET.SubElement(req_root, "Environment").text = ambiente_codigo
        ET.SubElement(req_root, "Content").text = xml_b64
        ET.SubElement(req_root, "ResolutionNumber").text = str(resolution_number)
        ET.SubElement(req_root, "ResolutionDate").text = resolution_date
        ET.SubElement(req_root, "PDF417Columns").text = "5"
        ET.SubElement(req_root, "PDF417Level").text = "2"
        ET.SubElement(req_root, "PDF417Type").text = "1"
        ET.SubElement(req_root, "TED").text = ""
        
        # Serializar request
        xml_request = b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(req_root, encoding='utf-8', method='xml')
        
        print(f"[DTEBox] Request construido: {len(xml_request)} bytes")
        print(f"[DTEBox] URL: {self.url}")
        print(f"[DTEBox] Ambiente: {ambiente_codigo}")
        print(f"[DTEBox] Resolución: {resolution_number} del {resolution_date}")
        
        # 4. Enviar Request
        headers = {
            'AuthKey': self.auth_key,
            'Content-Type': 'application/xml',
            'Accept': 'application/xml'
        }
        
        req = urllib.request.Request(self.url, data=xml_request, headers=headers, method='POST')
        
        try:
            response_obj = urllib.request.urlopen(req, timeout=60)
            response_data = response_obj.read().decode('utf-8')
            response_obj.close()
            
            print(f"[DTEBox] Respuesta recibida: {len(response_data)} caracteres")
            
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode('utf-8') if e.fp else str(e)
            print(f"[DTEBox] ERROR HTTP {e.code}: {error_msg[:500]}")
            return {
                'success': False,
                'ted': None,
                'error': f'HTTP Error {e.code}: {error_msg}'
            }
        
        # 5. Procesar respuesta
        # Intentar parsear como JSON primero
        try:
            import json
            respuesta = json.loads(response_data)
        except json.JSONDecodeError:
            # Si no es JSON, asumir XML directo
            print("[DTEBox] Respuesta no es JSON, asumiendo XML")
            if "<TrackId>" in response_data:
                return {
                    'success': True,
                    'xml_respuesta': response_data,
                    'track_id': 'VER_XML_RESPUESTA',
                    'ted': ''
                }
            else:
                respuesta = {'Data': '', 'Error': response_data}
        
        # Procesar respuesta JSON
        if respuesta and 'Data' in respuesta:
            data_b64 = respuesta['Data']
            data_xml = base64.b64decode(data_b64).decode('utf-8', errors='replace')
            
            # Parsear XML de respuesta
            try:
                root_resp = etree.fromstring(data_xml.encode('utf-8'))
                track_id = root_resp.findtext('.//TrackId', default='')
                estado = root_resp.findtext('.//Estado', default='')
                glosa = root_resp.findtext('.//Glosa', default='')
            except:
                track_id = ''
                estado = 'DESCONOCIDO'
                glosa = ''
            
            print(f"[DTEBox] Estado: {estado}, TrackId: {track_id}")
            
            return {
                'success': estado == 'OK' or 'EPR' in estado or (track_id != ''),
                'estado': estado,
                'glosa': glosa,
                'track_id': track_id,
                'xml_respuesta': data_xml,
                'ted': ''  # TED viene en xml_respuesta
            }
        else:
            return {
                'success': False,
                'error': 'Respuesta inválida de DTEBox',
                'detalle': str(respuesta),
                'ted': None
            }

    except Exception as e:
        print(f"[DTEBox] EXCEPCIÓN: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e),
            'ted': None
        }
