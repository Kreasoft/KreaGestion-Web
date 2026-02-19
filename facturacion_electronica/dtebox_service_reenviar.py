"""
Método reenviar_documento para DTEBoxService
Agregar al final de la clase DTEBoxService en dtebox_service.py
"""

def reenviar_documento(self, xml_completo):
    """
    Reenvía un documento ya timbrado a DTEBox
    
    Este método envía el XML completo del documento (con TED timbrado)
    al servidor DTEBox para reenviarlo.
    
    Args:
        xml_completo: String con el XML completo del documento (incluyendo TED timbrado)
        
    Returns:
        dict: {
            'success': bool,
            'message': str o None,
            'error': str o None
        }
    """
    try:
        # Validar que tenemos el XML
        if not xml_completo or not xml_completo.strip():
            return {
                'success': False,
                'message': None,
                'error': 'El XML del documento está vacío'
            }
        
        print(f"[DTEBox] Reenviando documento...")
        print(f"[DTEBox] XML tamaño: {len(xml_completo)} caracteres")
        
        # Obtener datos de resolución de la empresa
        if not self.empresa.resolucion_numero or not self.empresa.resolucion_fecha:
            return {
                'success': False,
                'message': None,
                'error': 'Los datos de resolución no están configurados en la empresa'
            }
        
        resolution_date = self.empresa.resolucion_fecha.strftime('%Y-%m-%d')
        resolution_number = self.empresa.resolucion_numero
        
        print(f"[DTEBox] Resolución: {resolution_number} del {resolution_date}")
        print(f"[DTEBox] Ambiente: {self.ambiente}")
        
        # Codificar XML en Base64 (preservar encoding ISO-8859-1)
        try:
            xml_bytes = xml_completo.encode('ISO-8859-1')
        except UnicodeEncodeError:
            # Si falla, intentar con UTF-8
            xml_bytes = xml_completo.encode('UTF-8')
        
        documento_base64 = base64.b64encode(xml_bytes).decode('utf-8')
        
        print(f"[DTEBox] XML codificado en base64: {len(documento_base64)} caracteres")
        
        # Construir request XML según documentación
        import xml.etree.ElementTree as ET
        
        root = ET.Element("SendDocumentAsXMLRequest", xmlns="http://gdexpress.cl/api")
        ET.SubElement(root, "Environment").text = str(self.ambiente)
        ET.SubElement(root, "Content").text = documento_base64
        ET.SubElement(root, "ResolutionDate").text = resolution_date
        ET.SubElement(root, "ResolutionNumber").text = str(int(resolution_number))
        
        # PDF417 (opcionales)
        pdf417_cols_elem = ET.SubElement(root, "PDF417Columns")
        if self.pdf417_columns:
            pdf417_cols_elem.text = str(self.pdf417_columns)
        
        pdf417_level_elem = ET.SubElement(root, "PDF417Level")
        if self.pdf417_level:
            pdf417_level_elem.text = str(self.pdf417_level)
        
        pdf417_type_elem = ET.SubElement(root, "PDF417Type")
        if self.pdf417_type:
            pdf417_type_elem.text = str(self.pdf417_type)
        
        # Para reenvío, el TED ya está en el XML, así que lo enviamos vacío
        ted_elem = ET.SubElement(root, "TED")
        # Dejar vacío ya que el TED está en el XML completo
        
        # Convertir a string
        xml_request_str = ET.tostring(root, encoding='unicode', method='xml')
        xml_request = xml_request_str.encode('utf-8')
        
        # Headers para XML
        headers_xml = {
            'AuthKey': self.auth_key,
            'Content-Type': 'application/xml',
            'Accept': 'application/xml'
        }
        
        print(f"[DTEBox] Enviando request de reenvío a: {self.url}")
        print(f"[DTEBox] Headers: AuthKey = {self.auth_key[:20]}...")
        
        # Realizar solicitud POST
        response = requests.post(
            self.url,
            data=xml_request,
            headers=headers_xml,
            timeout=30,
            verify=False
        )
        
        print(f"[DTEBox] Response Status: {response.status_code}")
        print(f"[DTEBox] Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        
        if response.status_code == 200:
            # Intentar parsear respuesta XML
            try:
                import xml.etree.ElementTree as ET
                root_resp = ET.fromstring(response.text)
                
                # Buscar Result y Description
                result_elem = (root_resp.find('.//{http://gdexpress.cl/api}Result') or 
                              root_resp.find('.//Result') or
                              root_resp.find('.//{*}Result'))
                description_elem = (root_resp.find('.//{http://gdexpress.cl/api}Description') or 
                                    root_resp.find('.//Description') or
                                    root_resp.find('.//{*}Description'))
                
                result_value = result_elem.text if result_elem is not None else None
                description = description_elem.text if description_elem is not None else ""
                
                # Result = 0 significa éxito, Result = 1 significa error
                if result_value == "0" or result_value == 0:
                    print(f"[DTEBox] ✅ Documento reenviado exitosamente")
                    return {
                        'success': True,
                        'message': description or 'Documento reenviado exitosamente',
                        'error': None
                    }
                else:
                    error_msg = description or 'Error al reenviar documento'
                    print(f"[DTEBox] ❌ Error al reenviar: {error_msg}")
                    return {
                        'success': False,
                        'message': None,
                        'error': error_msg
                    }
            
            except Exception as e:
                # Si no se puede parsear como XML, intentar como JSON
                try:
                    json_response = response.json()
                    result = json_response.get('Result', json_response.get('result'))
                    description = json_response.get('Description', json_response.get('description', ''))
                    
                    if result == 0 or result == "0":
                        print(f"[DTEBox] ✅ Documento reenviado exitosamente")
                        return {
                            'success': True,
                            'message': description or 'Documento reenviado exitosamente',
                            'error': None
                        }
                    else:
                        error_msg = description or 'Error al reenviar documento'
                        print(f"[DTEBox] ❌ Error al reenviar: {error_msg}")
                        return {
                            'success': False,
                            'message': None,
                            'error': error_msg
                        }
                except:
                    # Si tampoco es JSON, devolver respuesta como texto
                    if 'success' in response.text.lower() or 'ok' in response.text.lower():
                        print(f"[DTEBox] ✅ Documento reenviado exitosamente")
                        return {
                            'success': True,
                            'message': 'Documento reenviado exitosamente',
                            'error': None
                        }
                    else:
                        error_msg = f"Respuesta no reconocida: {response.text[:500]}"
                        print(f"[DTEBox] ❌ {error_msg}")
                        return {
                            'success': False,
                            'message': None,
                            'error': error_msg
                        }
        
        elif response.status_code == 401:
            error_msg = "No autorizado (401) - Verificar AuthKey"
            print(f"[DTEBox] ❌ {error_msg}")
            return {
                'success': False,
                'message': None,
                'error': error_msg
            }
        elif response.status_code == 404:
            error_msg = "Endpoint no encontrado (404) - Verificar URL"
            print(f"[DTEBox] ❌ {error_msg}")
            return {
                'success': False,
                'message': None,
                'error': error_msg
            }
        elif response.status_code == 500:
            error_msg = f"Error del servidor (500): {response.text[:500]}"
            print(f"[DTEBox] ❌ {error_msg}")
            return {
                'success': False,
                'message': None,
                'error': error_msg
            }
        else:
            error_msg = f"Status code no esperado ({response.status_code}): {response.text[:500]}"
            print(f"[DTEBox] ❌ {error_msg}")
            return {
                'success': False,
                'message': None,
                'error': error_msg
            }
    
    except requests.exceptions.ConnectionError as e:
        error_msg = f"Error de conexión: {str(e)}"
        print(f"[DTEBox] ❌ {error_msg}")
        return {
            'success': False,
            'message': None,
            'error': error_msg
        }
    except requests.exceptions.Timeout as e:
        error_msg = f"Timeout: {str(e)}"
        print(f"[DTEBox] ❌ {error_msg}")
        return {
            'success': False,
            'message': None,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f"Error inesperado: {str(e)}"
        print(f"[DTEBox] ❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'message': None,
            'error': error_msg
        }







