import json
import base64
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime


def buscar_documentos_recibidos(empresa, query_base64=None, pagina=0, tamano_pagina=300, fecha_desde=None, fecha_hasta=None):
    """
    Busca documentos recibidos en DTEBox
    
    Args:
        empresa: Instancia de Empresa
        query_base64: Query de búsqueda en Base64 (opcional)
        pagina: Número de página (0-indexed)
        tamano_pagina: Cantidad de documentos por página (máx 500)
        fecha_desde: String YYYY-MM-DD (opcional)
        fecha_hasta: String YYYY-MM-DD (opcional)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Configuración
    ambiente = 'T' if empresa.ambiente == 'CERTIFICACION' else 'P'
    grupo = 'R'  # R = Recibidos
    
    # Si no se proporciona query, usar un query que traiga documentos recientes
    # DTEBox usa sintaxis tipo Lucene: (Campo:Valor AND Campo:Valor)
    if not query_base64:
        from datetime import datetime, timedelta
        
        # Obtener RUT de la empresa (receptor de documentos)
        # DTEBox necesita el RUT CON guión (ej: 77117239-3)
        rut_receptor = empresa.rut.replace('.', '').replace(' ', '').strip()
        
        # Rango de fechas
        if not fecha_desde:
            # Por defecto últimos 30 días si no se especifica
            fecha_desde = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
        if not fecha_hasta:
            fecha_hasta = datetime.now().strftime('%Y-%m-%d')


        
        # Query con rango de fechas: FchEmis:[YYYY-MM-DD TO YYYY-MM-DD]
        query_string = f"(RUTRecep:{rut_receptor} AND FchEmis:[{fecha_desde} TO {fecha_hasta}] AND (TipoDTE:33 OR TipoDTE:34 OR TipoDTE:61 OR TipoDTE:56))"
        
        query_base64 = base64.b64encode(query_string.encode('utf-8')).decode('utf-8')
    
    # Construcción de URL y Credenciales
    base_url = empresa.url_servicio
    auth_key = empresa.api_key
    
    # Detección inteligente: Si api_key contiene una URL, usarla como base_url
    if auth_key and ('http://' in auth_key or 'https://' in auth_key):
        base_url = auth_key
        # Si la URL estaba en api_key, probamos usar llave_key como la verdadera api_key
        auth_key = empresa.llave_key
    
    # Si no hay URL o es localhost (valor por defecto), usar la IP de DTEBox por defecto
    if not base_url or 'localhost' in base_url or '127.0.0.1' in base_url:
        base_url = "http://200.6.118.43"
    
    # Asegurar que tenga http://
    if not base_url.startswith('http'):
        base_url = f"http://{base_url}"
    
    # Limpiar trailing slashes y espacios
    base_url = base_url.strip().rstrip('/')
    
    # Si la URL ya contiene /api/Core.svc/Core o /api/Core.svc/core, extraer solo la base
    if '/api/Core.svc/' in base_url:
        # Extraer solo hasta antes de /api
        base_url = base_url.split('/api/')[0]
    
    # Construir URL completa (la API usa 'core' en minúscula)
    url = f"{base_url}/api/Core.svc/core/PaginatedSearch/{ambiente}/{grupo}/{query_base64}/{pagina}/{tamano_pagina}"
    
    logger.info(f"Consultando URL: {url}")

    
    try:
        req = urllib.request.Request(url)
        if auth_key and not ('http' in auth_key): # Solo añadir auth si no es una URL (por seguridad)
             req.add_header('AuthKey', auth_key)
             
        req.add_header('Content-Type', 'application/json')
        req.add_header('Accept', 'application/json')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                return {
                    'success': False,
                    'error': f'Error HTTP {response.status}',
                    'total_documents': 0,
                    'documentos': []
                }
            
            data = json.loads(response.read().decode('utf-8'))
        
        # Parsear respuesta (Result viene como string)
        result = str(data.get('Result', '1'))
        if result != '0':
            error_msg = data.get('Description', 'Error desconocido')
            return {
                'success': False,
                'error': error_msg,
                'total_documents': 0,
                'documentos': []
            }
        
        # Procesar documentos
        documentos = []
        data_base64 = data.get('Data')
        
        if data_base64:
            try:
                # Data es un XML completo en Base64, no una lista
                xml_bytes = base64.b64decode(data_base64)
                
                # Intentar decodificar con diferentes encodings
                # El XML declara ISO-8859-1 pero a veces viene en UTF-8
                xml_string = None
                for encoding in ['utf-8', 'iso-8859-1', 'latin-1']:
                    try:
                        xml_string = xml_bytes.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                # Si ninguno funciona, usar UTF-8 con reemplazo de caracteres inválidos
                if xml_string is None:
                    xml_string = xml_bytes.decode('utf-8', errors='replace')
                
                # Parsear el XML contenedor
                import xml.etree.ElementTree as ET
                root = ET.fromstring(xml_string)
                
                # Buscar elementos <document>
                doc_elements = root.findall('.//document')
                
                # Buscar documentos individuales dentro de <documents>
                # El formato puede ser <documents><document>...</document></documents>
                for idx, doc_element in enumerate(doc_elements):
                    try:
                        # Convertir el elemento a string XML
                        doc_xml = ET.tostring(doc_element, encoding='unicode')
                        
                        # Parsear documento individual
                        doc_data = parsear_xml_documento_recibido(doc_xml)
                        
                        if doc_data:
                            doc_data['xml_original'] = doc_xml
                            documentos.append(doc_data)
                    except Exception as e:
                        logger.error(f"Error al parsear documento {idx + 1}/{len(doc_elements)}: {e}")
                        # Continuar con el siguiente documento
                        continue
                        
            except Exception as e:
                logger.error(f"Error al decodificar Data: {e}")
        
        return {
            'success': True,
            'total_documents': data.get('TotalDocuments', len(documentos)),
            'search_time': data.get('SearchTime', 0),
            'documentos': documentos,
            'error': None
        }
        
    except urllib.error.URLError as e:
        logger.error(f"Error de conexión: {e}")
        return {
            'success': False,
            'error': f'Error de conexión: {str(e)}',
            'total_documents': 0,
            'documentos': []
        }
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        return {
            'success': False,
            'error': str(e),
            'total_documents': 0,
            'documentos': []
        }


def parsear_xml_documento_recibido(xml_string):
    """
    Parsea el XML de un documento recibido desde DTEBox y extrae los datos principales.
    NOTA: DTEBox devuelve un formato propietario, NO el XML DTE estándar del SII.
    
    Returns:
        dict con datos del documento o None si hay error
    """
    try:
        # Parsear XML
        root = ET.fromstring(xml_string)
        
        # Extraer campos directamente del formato DTEBox
        # (no es el formato estándar DTE del SII)
        
        # Tipo de DTE
        tipo_dte_elem = root.find('.//TipoDTE')
        if tipo_dte_elem is None:
            tipo_dte_elem = root.find('.//DTEType')
        
        # Folio
        folio_elem = root.find('.//Folio')
        
        # Fechas
        fecha_emis_elem = root.find('.//FchEmis')
        if fecha_emis_elem is None:
            fecha_emis_elem = root.find('.//EmissionDate')
        
        fecha_venc_elem = root.find('.//FchVenc')
        if fecha_venc_elem is None:
            fecha_venc_elem = root.find('.//DueDate')
        
        # Emisor (Proveedor)
        rut_emisor_elem = root.find('.//RUTEmisor')
        if rut_emisor_elem is None:
            rut_emisor_elem = root.find('.//IssuerRUT')
        
        razon_social_elem = root.find('.//RznSoc')
        if razon_social_elem is None:
            razon_social_elem = root.find('.//IssuerName')
        
        # Totales
        mnt_neto_elem = root.find('.//MntNeto')
        if mnt_neto_elem is None:
            mnt_neto_elem = root.find('.//NetoAmount')
        
        mnt_exento_elem = root.find('.//ExeAmount')
        
        iva_elem = root.find('.//IVA')
        if iva_elem is None:
            iva_elem = root.find('.//Iva')
        
        mnt_total_elem = root.find('.//MntTotal')
        if mnt_total_elem is None:
            mnt_total_elem = root.find('.//TotalAmount')
        
        # Validar campos obligatorios
        if tipo_dte_elem is None or folio_elem is None or rut_emisor_elem is None:
            return None
        
        # Mapeo de tipos de documento
        tipo_doc_map = {
            '33': 'FACTURA',
            '34': 'FACTURA_EXENTA',
            '61': 'NOTA_CREDITO',
            '56': 'NOTA_DEBITO',
            '52': 'GUIA',
            '39': 'BOLETA'
        }
        
        tipo_dte_codigo = tipo_dte_elem.text.strip()
        
        # Parsear fecha (puede venir como "2025-10-01T00:00:00" o "2025-10-01")
        fecha_emision_str = fecha_emis_elem.text if fecha_emis_elem is not None else None
        if fecha_emision_str:
            # Tomar solo la parte de la fecha (YYYY-MM-DD)
            fecha_emision_str = fecha_emision_str.split('T')[0]
        
        fecha_venc_str = fecha_venc_elem.text if fecha_venc_elem is not None else None
        if fecha_venc_str:
            fecha_venc_str = fecha_venc_str.split('T')[0]
        
        # Extraer URL de descarga del DTE original (si existe)
        download_url_elem = root.find('.//DownloadCustomerDocumentUrl')
        download_url = download_url_elem.text if download_url_elem is not None else None
        
        resultado = {
            'tipo_documento': tipo_doc_map.get(tipo_dte_codigo, 'FACTURA'),
            'tipo_dte_codigo': tipo_dte_codigo,
            'numero': folio_elem.text.strip(),
            'fecha_emision': fecha_emision_str,
            'fecha_vencimiento': fecha_venc_str,
            'rut_emisor': rut_emisor_elem.text.strip(),
            'razon_social_emisor': razon_social_elem.text.strip() if razon_social_elem is not None else '',
            'giro_emisor': '',  # No viene en el formato DTEBox
            'direccion_emisor': '',  # No viene en el formato DTEBox
            'comuna_emisor': root.find('.//CmnaOrigen').text if root.find('.//CmnaOrigen') is not None else '',
            'neto': float(mnt_neto_elem.text) if mnt_neto_elem is not None and mnt_neto_elem.text else 0,
            'exento': float(mnt_exento_elem.text) if mnt_exento_elem is not None and mnt_exento_elem.text else 0,
            'iva': float(iva_elem.text) if iva_elem is not None and iva_elem.text else 0,
            'total': float(mnt_total_elem.text) if mnt_total_elem is not None and mnt_total_elem.text else 0,
            'download_url': download_url,
        }
        
        return resultado
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error al parsear XML: {e}")
        return None
