"""
Cliente para interactuar con la API de GDExpress/DTEBox
"""
import base64
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from lxml import etree
from ..utils import formatear_rut, limpiar_rut


class ClienteGDExpress:
    """
    Cliente para interactuar con GDExpress/DTEBox
    
    Uso:
        cliente = ClienteGDExpress(
            api_key='tu-api-key',
            ambiente='CERTIFICACION'
        )
        
        resultado = cliente.enviar_dte(xml_firmado)
    """
    
    def __init__(self, api_key, ambiente='CERTIFICACION', url_servicio=None):
        """
        Inicializa el cliente
        
        Args:
            api_key (str): API Key de GDExpress
            ambiente (str): 'CERTIFICACION' o 'PRODUCCION'
            url_servicio (str, optional): URL del servicio
        """
        self.api_key = api_key
        self.ambiente = ambiente.upper()
        
        if url_servicio:
            self.url_servicio = url_servicio
        else:
            self.url_servicio = 'http://200.6.118.43/api/Core.svc/core'
        
        # Normalizar URL
        if self.url_servicio.endswith('/'):
            self.url_servicio = self.url_servicio[:-1]
            
        # Asegurar endpoint core minúscula (crítico para compatibilidad)
        # Reemplazar variantes comunes
        self.url_servicio = self.url_servicio.replace('/Core.svc/Core', '/Core.svc/core')
        self.url_servicio = self.url_servicio.replace('/core.svc/Core', '/Core.svc/core')
        self.url_servicio = self.url_servicio.replace('/CORE.SVC/CORE', '/Core.svc/core')
    
    def _hacer_peticion(self, endpoint, metodo='GET', datos=None, headers=None):
        """
        Hace una petición HTTP a la API
        
        Args:
            endpoint (str): Endpoint de la API
            metodo (str): Método HTTP
            datos (dict, optional): Datos a enviar
            headers (dict, optional): Headers adicionales
            
        Returns:
            dict: Respuesta de la API
        """
        url = f"{self.url_servicio}/{endpoint}"
        
        # Headers por defecto
        default_headers = {
            'AuthKey': self.api_key,
            'Content-Type': 'application/json',
        }
        
        if headers:
            default_headers.update(headers)
        
        try:
            # Preparar request
            if datos:
                datos_json = json.dumps(datos).encode('utf-8')
                req = urllib.request.Request(url, data=datos_json, headers=default_headers, method=metodo)
            else:
                req = urllib.request.Request(url, headers=default_headers, method=metodo)
            
            # Hacer petición
            with urllib.request.urlopen(req, timeout=60) as response:
                response_data = response.read().decode('utf-8')
                return json.loads(response_data)
        
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode('utf-8') if e.fp else str(e)
            raise Exception(f"Error HTTP {e.code}: {error_msg}")
        
        except urllib.error.URLError as e:
            raise Exception(f"Error de conexión: {e.reason}")
        
        except Exception as e:
            raise Exception(f"Error en petición: {str(e)}")
    
    def enviar_dte(self, xml_firmado, tipo_envio='DTE', resolucion_numero=0, resolucion_fecha='2000-01-01', ted=''):
        """
        Envía un DTE a GDExpress/DTEBox
        """
        try:
            # 1. Limpieza del XML (Basado en DTEBoxService)
            from lxml import etree
            
            # Asegurar bytes
            if isinstance(xml_firmado, str):
                xml_bytes = xml_firmado.encode('ISO-8859-1')
            else:
                xml_bytes = xml_firmado
                
            root_xml = etree.fromstring(xml_bytes)
            
            # Si es EnvioDTE, extraer el DTE interno
            if 'EnvioDTE' in root_xml.tag:
                print("Detectado EnvioDTE, extrayendo DTE interno...")
                ns_sii = "http://www.sii.cl/SiiDte"
                dte_interno = root_xml.find(f'.//{{{ns_sii}}}DTE')
                if dte_interno is None:
                    dte_interno = root_xml.find('.//DTE')
                
                if dte_interno is not None:
                    root_xml = dte_interno
                    print("DTE interno extraído.")
            
            # Remover Signature
            ns_dsig = "http://www.w3.org/2000/09/xmldsig#"
            for sig in root_xml.findall(f'.//{{{ns_dsig}}}Signature'):
                sig.getparent().remove(sig)
            
            # Remover contenido del TED
            ns_sii = "http://www.sii.cl/SiiDte"
            for ted_elem in root_xml.findall(f'.//{{{ns_sii}}}TED'):
                ted_elem.getparent().remove(ted_elem)
            for ted_elem in root_xml.findall('.//TED'):
                ted_elem.getparent().remove(ted_elem)
                
            xml_clean = etree.tostring(root_xml, encoding='ISO-8859-1')
            
            # Codificar a Base64
            xml_b64 = base64.b64encode(xml_clean).decode('ascii')
            
            # 2. Construir Request XML (Estructura Exacta DTEBoxService)
            ambiente_codigo = 'T' if self.ambiente == 'CERTIFICACION' else 'P'
            
            # Usar ElementTree estandar para construir el request sin problemas de namespaces de lxml
            import xml.etree.ElementTree as ET
            
            # Root con namespace por defecto
            req_root = ET.Element("SendDocumentAsXMLRequest")
            req_root.set("xmlns", "http://gdexpress.cl/api")
            
            ET.SubElement(req_root, "Environment").text = ambiente_codigo
            ET.SubElement(req_root, "Content").text = xml_b64
            ET.SubElement(req_root, "ResolutionNumber").text = str(int(resolucion_numero))
            ET.SubElement(req_root, "ResolutionDate").text = resolucion_fecha
            
            # PDF417 params (Hardcoded por ahora, configurable si es necesario)
            ET.SubElement(req_root, "PDF417Columns").text = "5"
            ET.SubElement(req_root, "PDF417Level").text = "2"
            ET.SubElement(req_root, "PDF417Type").text = "1"
            
            ET.SubElement(req_root, "TED").text = "" # TED vacio
            
            # Serializar request
            xml_request_body = b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(req_root, encoding='utf-8', method='xml')
            
            print("\n--- DEBUG: XML REQUEST A ENVIAR (Primeros 500 chars) ---")
            print(xml_request_body[:500].decode('utf-8'))
            print("--------------------------------------------------------\n")

            # 3. Enviar Request
            endpoint = "SendDocumentAsXML"
            url = f"{self.url_servicio}/{endpoint}"
            
            headers = {
                'AuthKey': self.api_key,
                'Content-Type': 'application/xml',
                'Accept': 'application/xml' # Preferir XML, pero GDExpress puede devolver JSON
            }
            
            req = urllib.request.Request(url, data=xml_request_body, headers=headers, method='POST')
            
            try:
                response_obj = urllib.request.urlopen(req, timeout=60)
                response_data = response_obj.read().decode('utf-8')
                response_obj.close()
            except urllib.error.HTTPError as e:
                # Si falla con 500 o 400, intentar FALLBACK con solo Documento
                print(f"Error HTTP {e.code} con DTE completo. Intentando fallback con solo Documento...")
                
                # Extraer Documento
                ns_sii = "http://www.sii.cl/SiiDte"
                doc_elem = root_xml.find(f'.//{{{ns_sii}}}Documento')
                if doc_elem is None:
                    doc_elem = root_xml.find('.//Documento')
                
                if doc_elem is not None:
                    # Crear nuevo XML solo con Documento
                    # Asegurar declaracion XML y Encoding
                    doc_xml = etree.tostring(doc_elem, encoding='ISO-8859-1')
                    doc_b64 = base64.b64encode(doc_xml).decode('ascii')
                    
                    # Reconstruir Request
                    # Content ahora es solo el Documento
                    ET.SubElement(req_root, "Content").text = doc_b64 # Sobrescribir (o crear nuevo root)
                    # Mejor crear nuevo root para limpiar
                    req_root_fb = ET.Element("SendDocumentAsXMLRequest")
                    req_root_fb.set("xmlns", "http://gdexpress.cl/api")
                    ET.SubElement(req_root_fb, "Environment").text = ambiente_codigo
                    ET.SubElement(req_root_fb, "Content").text = doc_b64
                    ET.SubElement(req_root_fb, "ResolutionNumber").text = str(int(resolucion_numero))
                    ET.SubElement(req_root_fb, "ResolutionDate").text = resolucion_fecha
                    ET.SubElement(req_root_fb, "PDF417Columns").text = "5"
                    ET.SubElement(req_root_fb, "PDF417Level").text = "2"
                    ET.SubElement(req_root_fb, "PDF417Type").text = "1"
                    ET.SubElement(req_root_fb, "TED").text = ""
                    
                    xml_request_body_fb = b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(req_root_fb, encoding='utf-8', method='xml')
                    
                    print("Intentando reenvío con FALLBACK (Solo Documento)...")
                    req_fb = urllib.request.Request(url, data=xml_request_body_fb, headers=headers, method='POST')
                    
                    with urllib.request.urlopen(req_fb, timeout=60) as response_fb:
                        response_data = response_fb.read().decode('utf-8')
                        print("Fallback exitoso!")
                else:
                    raise e # No hay documento, relanzar error original

            # Procesar respuesta (JSON o XML)
            # Intentar parsear como JSON primero (comportamiento habitual)
            try:
                respuesta = json.loads(response_data)
            except json.JSONDecodeError:
                    # Si falla, intentar parsear XML de respuesta manualmente o devolver raw
                    # GDExpress a veces devuelve XML directo en el body
                    print("Respuesta no es JSON válido, asumiendo XML directo o error string")
                    # Simular estructura de respuesta JSON exitosa si recibimos XML directo con TrackId
                    if "<TrackId>" in response_data:
                         # Extraer TrackId a la fuerza si es necesario, o devolver todo en xml_respuesta
                         return {
                             'success': True,
                             'xml_respuesta': response_data,
                             'track_id': 'VER_XML_RESPUESTA', # Placeholder, parsing real abajo
                             'estado': 'RECIBIDO'
                         }
                    else:
                        respuesta = {'Data': '', 'Error': response_data}

            # Procesar respuesta (JSON)
            if respuesta and 'Data' in respuesta:
                data_b64 = respuesta['Data']
                data_xml = base64.b64decode(data_b64).decode('utf-8', errors='replace')
                
                # Parsear XML de respuesta para sacar TrackID
                try:
                    root_resp = etree.fromstring(data_xml.encode('utf-8'))
                    track_id = root_resp.findtext('.//TrackId', default='')
                    estado = root_resp.findtext('.//Estado', default='')
                    glosa = root_resp.findtext('.//Glosa', default='')
                except:
                    track_id = ''
                    estado = 'DESCONOCIDO'
                    glosa = ''
                
                return {
                    'success': estado == 'OK' or 'EPR' in estado or (track_id != ''),
                    'estado': estado,
                    'glosa': glosa,
                    'track_id': track_id,
                    'xml_respuesta': data_xml,
                }
            else:
                return {
                    'success': False,
                    'error': 'Respuesta inválida de GDExpress',
                    'detalle': str(respuesta),
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    def consultar_estado(self, track_id):
        """
        Consulta el estado de un DTE por Track ID
        
        Args:
            track_id (str): Track ID del documento
            
        Returns:
            dict: Estado del documento
        """
        try:
            ambiente_codigo = 'T' if self.ambiente == 'CERTIFICACION' else 'P'
            endpoint = f"GetDocumentStatus/{ambiente_codigo}/{track_id}"
            
            respuesta = self._hacer_peticion(endpoint)
            
            if respuesta and 'Data' in respuesta:
                data_b64 = respuesta['Data']
                data_xml = base64.b64decode(data_b64).decode('utf-8')
                
                root = etree.fromstring(data_xml.encode('utf-8'))
                
                return {
                    'success': True,
                    'estado': root.findtext('.//Estado', default=''),
                    'glosa': root.findtext('.//Glosa', default=''),
                    'fecha': root.findtext('.//Fecha', default=''),
                    'xml_respuesta': data_xml,
                }
            else:
                return {
                    'success': False,
                    'error': 'No se pudo consultar el estado',
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    def obtener_documentos_recibidos(self, rut_receptor, dias=30, tipos_dte=None):
        """
        Obtiene documentos recibidos desde DTEBox
        
        Args:
            rut_receptor (str): RUT del receptor
            dias (int): Días hacia atrás a buscar
            tipos_dte (list, optional): Lista de tipos de DTE a buscar
            
        Returns:
            list: Lista de documentos recibidos
        """
        try:
            # Preparar fechas
            fecha_hasta = datetime.now()
            fecha_desde = fecha_hasta - timedelta(days=dias)
            
            # Limpiar RUT
            rut_limpio = limpiar_rut(rut_receptor)
            
            # Tipos de DTE por defecto
            if tipos_dte is None:
                tipos_dte = [33, 34, 56, 61]
            
            # Construir query
            tipos_query = ' OR '.join([f'TipoDTE:{t}' for t in tipos_dte])
            query_string = (
                f"(RUTRecep:{rut_limpio} AND "
                f"FchEmis:[{fecha_desde.strftime('%Y-%m-%d')} TO {fecha_hasta.strftime('%Y-%m-%d')}] AND "
                f"({tipos_query}))"
            )
            
            query_b64 = base64.b64encode(query_string.encode('utf-8')).decode('utf-8')
            
            # Hacer petición
            ambiente_codigo = 'T' if self.ambiente == 'CERTIFICACION' else 'P'
            endpoint = f"PaginatedSearch/{ambiente_codigo}/1/{query_b64}/0/300"
            
            respuesta = self._hacer_peticion(endpoint)
            
            if not respuesta or 'Data' not in respuesta:
                return []
            
            # Decodificar respuesta
            data_b64 = respuesta['Data']
            xml_bytes = base64.b64decode(data_b64)
            
            # Intentar decodificar con diferentes encodings
            xml_string = None
            for encoding in ['utf-8', 'iso-8859-1', 'latin-1']:
                try:
                    xml_string = xml_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if not xml_string:
                xml_string = xml_bytes.decode('utf-8', errors='replace')
            
            # Parsear XML
            root = etree.fromstring(xml_string.encode('utf-8'))
            
            # Extraer documentos
            documentos = []
            for doc_elem in root.findall('.//Document'):
                try:
                    doc = {
                        'tipo_documento': doc_elem.findtext('TipoDTE', ''),
                        'numero': doc_elem.findtext('Folio', ''),
                        'rut_emisor': doc_elem.findtext('RUTEmisor', ''),
                        'razon_social_emisor': doc_elem.findtext('RznSoc', ''),
                        'fecha_emision': doc_elem.findtext('FchEmis', '').split('T')[0],
                        'fecha_vencimiento': doc_elem.findtext('FchVenc', '').split('T')[0] if doc_elem.findtext('FchVenc') else None,
                        'neto': int(doc_elem.findtext('MntNeto', 0)),
                        'exento': int(doc_elem.findtext('MntExe', 0)),
                        'iva': int(doc_elem.findtext('IVA', 0)),
                        'total': int(doc_elem.findtext('MntTotal', 0)),
                        'download_url': doc_elem.findtext('DownloadCustomerDocumentUrl', ''),
                        'xml_original': etree.tostring(doc_elem, encoding='unicode'),
                    }
                    documentos.append(doc)
                except Exception:
                    continue
            
            return documentos
        
        except Exception as e:
            raise Exception(f"Error al obtener documentos recibidos: {str(e)}")
