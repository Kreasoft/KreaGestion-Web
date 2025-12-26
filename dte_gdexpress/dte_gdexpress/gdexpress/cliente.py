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
            self.url_servicio = 'http://200.6.118.43/api/Core.svc/Core'
        
        # Normalizar URL
        if self.url_servicio.endswith('/'):
            self.url_servicio = self.url_servicio[:-1]
    
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
    
    def enviar_dte(self, xml_firmado, tipo_envio='DTE'):
        """
        Envía un DTE a GDExpress
        
        Args:
            xml_firmado (str): XML del DTE firmado
            tipo_envio (str): 'DTE' o 'EnvioBOLETA'
            
        Returns:
            dict: Resultado del envío
        """
        try:
            # Codificar XML en base64
            if isinstance(xml_firmado, str):
                xml_firmado = xml_firmado.encode('ISO-8859-1')
            
            xml_b64 = base64.b64encode(xml_firmado).decode('utf-8')
            
            # Determinar ambiente
            ambiente_codigo = 'T' if self.ambiente == 'CERTIFICACION' else 'P'
            
            # Endpoint según tipo de envío
            if tipo_envio == 'EnvioBOLETA':
                endpoint = f"SendDocumentAsXML/{ambiente_codigo}/1/{xml_b64}"
            else:
                endpoint = f"SendDocumentAsXML/{ambiente_codigo}/0/{xml_b64}"
            
            # Enviar
            respuesta = self._hacer_peticion(endpoint, metodo='POST')
            
            # Procesar respuesta
            if respuesta and 'Data' in respuesta:
                # Decodificar respuesta
                data_b64 = respuesta['Data']
                data_xml = base64.b64decode(data_b64).decode('utf-8')
                
                # Parsear XML de respuesta
                root = etree.fromstring(data_xml.encode('utf-8'))
                
                # Extraer información
                estado = root.findtext('.//Estado', default='')
                glosa = root.findtext('.//Glosa', default='')
                track_id = root.findtext('.//TrackId', default='')
                
                return {
                    'success': estado == 'OK' or 'EPR' in estado,
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
