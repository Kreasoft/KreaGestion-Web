"""
Servicio para integración con DTEBox (Timbraje Offline)
"""
import requests
import base64
import json
import os
from django.utils import timezone
from django.conf import settings
from datetime import datetime


class DTEBoxService:
    """Servicio para comunicación con DTEBox API"""
    
    def __init__(self, empresa):
        """
        Inicializa el servicio DTEBox
        
        Args:
            empresa: Instancia de Empresa con configuración DTEBox
        """
        self.empresa = empresa
        
        if not empresa.dtebox_habilitado:
            raise ValueError("DTEBox no está habilitado para esta empresa")
        
        if not empresa.dtebox_url:
            raise ValueError("DTEBox URL no está configurada")
        
        if not empresa.dtebox_auth_key:
            raise ValueError("DTEBox Auth Key no está configurada")
        
        # Normalizar URL - asegurar que termine con el endpoint correcto
        url_base = empresa.dtebox_url.strip()
        
        # Remover barra final si existe
        url_base = url_base.rstrip('/')
        
        # Construir URL completa según la documentación: http://[ip-dtebox]/api/Core.svc/core/SendDocumentAsXML
        # CRÍTICO: El endpoint debe ser /core/SendDocumentAsXML (con minúscula 'core')
        
        # Normalizar: convertir /Core a /core
        url_base_normalized = url_base.replace('/Core', '/core').replace('/CORE', '/core')
        
        if url_base_normalized.endswith('/SendDocumentAsXML'):
            # Ya tiene el endpoint completo
            self.url = url_base_normalized
        elif url_base_normalized.endswith('/core/SendDocumentAsXML'):
            # Ya tiene el endpoint completo
            self.url = url_base_normalized
        elif '/SendDocumentAsXML' in url_base_normalized:
            # Tiene el endpoint pero puede estar mal ubicado, usar tal cual
            self.url = url_base_normalized
        elif url_base_normalized.endswith('/core'):
            # Termina en /core, solo agregar /SendDocumentAsXML
            self.url = f"{url_base_normalized}/SendDocumentAsXML"
        elif '/api/Core.svc/core' in url_base_normalized or '/api/core.svc/core' in url_base_normalized:
            # Tiene la ruta base pero falta el endpoint
            self.url = f"{url_base_normalized}/SendDocumentAsXML"
        elif '/api/Core.svc' in url_base_normalized or '/api/core.svc' in url_base_normalized:
            # Tiene hasta Core.svc, agregar /core/SendDocumentAsXML
            # Si termina en /Core o /CORE, ya fue normalizado a /core
            if url_base_normalized.endswith('/core'):
                self.url = f"{url_base_normalized}/SendDocumentAsXML"
            else:
                self.url = f"{url_base_normalized}/core/SendDocumentAsXML"
        elif '/api' in url_base_normalized:
            # Tiene hasta /api, agregar /Core.svc/core/SendDocumentAsXML
            self.url = f"{url_base_normalized}/Core.svc/core/SendDocumentAsXML"
        else:
            # Solo IP/servidor, construir ruta completa
            self.url = f"{url_base_normalized}/api/Core.svc/core/SendDocumentAsXML"
        
        print(f"[DTEBox] URL base configurada: {empresa.dtebox_url}")
        print(f"[DTEBox] URL final construida: {self.url}")
        
        self.auth_key = empresa.dtebox_auth_key
        self.ambiente = empresa.dtebox_ambiente or 'T'
        self.pdf417_columns = empresa.dtebox_pdf417_columns or 5
        self.pdf417_level = empresa.dtebox_pdf417_level or 2
        self.pdf417_type = empresa.dtebox_pdf417_type or 1
        
        print(f"[DTEBox] Servicio inicializado - URL: {self.url}, Ambiente: {self.ambiente}")
    
    def _parsear_xml_con_encoding(self, xml_string):
        """
        Parsea XML manejando correctamente el encoding ISO-8859-1 y UTF-8
        
        Args:
            xml_string: String con el XML
            
        Returns:
            lxml.etree.Element: Elemento raíz del XML parseado
        """
        from lxml import etree as lxml_etree
        
        # Intentar detectar encoding desde la declaración XML
        encoding = 'ISO-8859-1'  # Por defecto para DTE chilenos
        
        if '<?xml' in xml_string:
            import re
            encoding_match = re.search(r'encoding=["\']([^"\']+)["\']', xml_string)
            if encoding_match:
                encoding = encoding_match.group(1).upper()
        
        # Intentar parsear con diferentes encodings
        encodings_to_try = [encoding, 'ISO-8859-1', 'UTF-8', 'latin1']
        
        for enc in encodings_to_try:
            try:
                xml_bytes = xml_string.encode(enc)
                root = lxml_etree.fromstring(xml_bytes)
                print(f"[DTEBox] XML parseado correctamente con encoding: {enc}")
                return root
            except (UnicodeEncodeError, UnicodeDecodeError, ValueError) as e:
                continue
            except Exception as e:
                # Si es otro error (no de encoding), intentar siguiente encoding
                continue
        
        # Último intento: usar errors='ignore' o 'replace'
        try:
            xml_bytes = xml_string.encode('ISO-8859-1', errors='replace')
            root = lxml_etree.fromstring(xml_bytes)
            print(f"[DTEBox] XML parseado con encoding ISO-8859-1 (errors=replace)")
            return root
        except Exception as e:
            print(f"[DTEBox] Error crítico al parsear XML: {str(e)}")
            raise
    
    def _extraer_documento_xml(self, xml_firmado):
        """
        Extrae el elemento Documento del XML firmado.
        DTEBox podría necesitar solo el Documento interno, no el wrapper DTE completo.
        
        Args:
            xml_firmado: String con el XML del DTE firmado
            
        Returns:
            str: XML del Documento extraído (o el XML original si no se puede extraer)
        """
        try:
            import xml.etree.ElementTree as ET
            
            # Parsear el XML
            root = ET.fromstring(xml_firmado)
            
            # Buscar el elemento Documento (con o sin namespace)
            documento = root.find('.//{http://www.sii.cl/SiiDte}Documento')
            if documento is None:
                documento = root.find('.//Documento')
            
            if documento is not None:
                # Convertir el Documento a string con su contenido completo
                documento_str = ET.tostring(documento, encoding='unicode', method='xml')
                # Agregar declaración XML
                documento_xml = '<?xml version="1.0" encoding="ISO-8859-1"?>\n' + documento_str
                print(f"[DTEBox] Extraído elemento Documento del XML (tamaño: {len(documento_xml)} chars)")
                return documento_xml
            else:
                print(f"[DTEBox] ⚠️ No se encontró elemento Documento, usando XML completo")
                return xml_firmado
        except Exception as e:
            print(f"[DTEBox] ⚠️ Error al extraer Documento: {str(e)}, usando XML completo")
            return xml_firmado
    
    def _extraer_dte_desde_enviodte(self, xml_firmado):
        """
        Extrae el DTE interno de un EnvioDTE completo.
        Si el XML es un EnvioDTE, extrae solo el DTE interno.
        
        Args:
            xml_firmado: String con el XML (puede ser EnvioDTE o DTE)
            
        Returns:
            str: XML del DTE extraído (o el XML original si no es EnvioDTE)
        """
        try:
            # Verificar si es un EnvioDTE
            if '<EnvioDTE' not in xml_firmado and 'EnvioDTE' not in xml_firmado:
                return xml_firmado
            
            from lxml import etree as lxml_etree
            
            # Parsear el XML
            root = lxml_etree.fromstring(xml_firmado.encode('ISO-8859-1'))
            
            # Buscar el elemento DTE dentro del EnvioDTE
            ns_sii = "http://www.sii.cl/SiiDte"
            dte = root.find(f'.//{{{ns_sii}}}DTE')
            if dte is None:
                dte = root.find('.//DTE')
            
            if dte is not None:
                # Convertir el DTE a string
                dte_xml = lxml_etree.tostring(
                    dte,
                    pretty_print=True,
                    xml_declaration=True,
                    encoding='ISO-8859-1'
                ).decode('ISO-8859-1')
                
                print(f"[DTEBox] ✅ Extraído DTE desde EnvioDTE (tamaño: {len(dte_xml)} chars)")
                return dte_xml
            
            return xml_firmado
        except Exception as e:
            print(f"[DTEBox] ⚠️ Error al extraer DTE desde EnvioDTE: {str(e)}, usando XML original")
            return xml_firmado
    
    def _remover_ted_timbrado(self, xml_firmado):
        """
        Remueve el TED timbrado del XML y lo reemplaza con un TED vacío.
        DTEBox necesita generar el TED, no recibir uno ya timbrado.
        
        Args:
            xml_firmado: String con el XML del DTE firmado
            
        Returns:
            str: XML con el TED removido/reemplazado por uno vacío
        """
        try:
            from lxml import etree as lxml_etree
            
            # Parsear el XML
            root = lxml_etree.fromstring(xml_firmado.encode('ISO-8859-1'))
            
            ns_sii = "http://www.sii.cl/SiiDte"
            
            # Buscar el elemento Documento
            documento = root.find(f'.//{{{ns_sii}}}Documento')
            if documento is None:
                documento = root.find('.//Documento')
            
            if documento is not None:
                # Buscar el TED existente
                ted_existente = documento.find(f'.//{{{ns_sii}}}TED')
                if ted_existente is None:
                    ted_existente = documento.find('.//TED')
                
                if ted_existente is not None:
                    # Verificar si el TED tiene contenido (está timbrado)
                    dd = ted_existente.find(f'.//{{{ns_sii}}}DD')
                    if dd is None:
                        dd = ted_existente.find('.//DD')
                    
                    # Si el DD tiene contenido, el TED está timbrado y debemos removerlo
                    if dd is not None and len(dd) > 0:
                        # Remover el TED timbrado
                        parent = ted_existente.getparent()
                        parent.remove(ted_existente)
                        
                        # Agregar TED vacío
                        ted_vacio = lxml_etree.SubElement(documento, f"{{{ns_sii}}}TED")
                        ted_vacio.set("version", "1.0")
                        dd_vacio = lxml_etree.SubElement(ted_vacio, f"{{{ns_sii}}}DD")
                        frmt_vacio = lxml_etree.SubElement(ted_vacio, f"{{{ns_sii}}}FRMT")
                        frmt_vacio.set("algoritmo", "SHA1withRSA")
                        
                        print(f"[DTEBox] ✅ Removido TED timbrado y agregado TED vacío")
                        
                        # Convertir de vuelta a string
                        xml_sin_ted = lxml_etree.tostring(
                            root,
                            pretty_print=True,
                            xml_declaration=True,
                            encoding='ISO-8859-1'
                        ).decode('ISO-8859-1')
                        
                        return xml_sin_ted
            
            return xml_firmado
        except Exception as e:
            print(f"[DTEBox] ⚠️ Error al remover TED timbrado: {str(e)}, usando XML original")
            return xml_firmado
    
    def _agregar_ted_vacio(self, xml_firmado):
        """
        Agrega el elemento TED vacío al XML del DTE si no existe.
        DTEBox requiere que el XML tenga la estructura completa con el elemento TED.
        
        Args:
            xml_firmado: String con el XML del DTE firmado
            
        Returns:
            str: XML con el elemento TED agregado (si no existía)
        """
        try:
            # Verificar si ya tiene TED usando búsqueda de texto (más rápido y evita parsear)
            if '<TED' in xml_firmado or '<ns0:TED' in xml_firmado or '<ns1:TED' in xml_firmado:
                # Verificar si el TED está vacío o timbrado
                # Si tiene contenido dentro de DD, está timbrado y debemos removerlo
                if '<DD>' in xml_firmado and '</DD>' in xml_firmado:
                    # Verificar si DD tiene contenido (no está vacío)
                    import re
                    dd_match = re.search(r'<DD[^>]*>(.*?)</DD>', xml_firmado, re.DOTALL)
                    if dd_match and dd_match.group(1).strip():
                        # El TED está timbrado, removerlo
                        return self._remover_ted_timbrado(xml_firmado)
                
                print(f"[DTEBox] ✅ El XML ya tiene elemento TED (vacío)")
                return xml_firmado
            
            # Usar lxml para mejor control del formato y evitar prefijos de namespace
            try:
                from lxml import etree as lxml_etree
                
                # Usar función auxiliar para parsear con manejo correcto de encoding
                root = self._parsear_xml_con_encoding(xml_firmado)
                
                # Buscar el elemento Documento
                ns_sii = "http://www.sii.cl/SiiDte"
                documento = root.find(f'.//{{{ns_sii}}}Documento')
                if documento is None:
                    documento = root.find('.//Documento')
                
                if documento is not None:
                    # Verificar si ya tiene TED
                    ted_existente = documento.find(f'.//{{{ns_sii}}}TED')
                    if ted_existente is None:
                        ted_existente = documento.find('.//TED')
                    
                    if ted_existente is None:
                        # Agregar elemento TED con estructura básica según el ejemplo del usuario
                        # El TED debe tener al menos los elementos DD y FRMT
                        ted_elem = lxml_etree.SubElement(documento, f"{{{ns_sii}}}TED")
                        ted_elem.set("version", "1.0")
                        
                        # Agregar elemento DD (Datos del Documento) vacío
                        dd_elem = lxml_etree.SubElement(ted_elem, f"{{{ns_sii}}}DD")
                        
                        # Agregar elemento FRMT (Firma del Timbre) vacío
                        frmt_elem = lxml_etree.SubElement(ted_elem, f"{{{ns_sii}}}FRMT")
                        frmt_elem.set("algoritmo", "SHA1withRSA")
                        
                        print(f"[DTEBox] ✅ Agregado elemento TED con estructura básica al XML del DTE")
                        
                        # Convertir de vuelta a string preservando el formato original sin prefijos
                        try:
                            xml_con_ted = lxml_etree.tostring(
                                root,
                                pretty_print=True,
                                xml_declaration=True,
                                encoding='ISO-8859-1'
                            ).decode('ISO-8859-1')
                        except UnicodeDecodeError:
                            # Si falla, intentar sin pretty_print
                            xml_con_ted = lxml_etree.tostring(
                                root,
                                xml_declaration=True,
                                encoding='ISO-8859-1'
                            ).decode('ISO-8859-1')
                        
                        return xml_con_ted
                
                return xml_firmado
            except ImportError:
                # Fallback a ElementTree estándar si lxml no está disponible
                import xml.etree.ElementTree as ET
                root = ET.fromstring(xml_firmado)
                
                documento = root.find('.//{http://www.sii.cl/SiiDte}Documento')
                if documento is None:
                    documento = root.find('.//Documento')
                
                if documento is not None:
                    ted_existente = documento.find('.//{http://www.sii.cl/SiiDte}TED')
                    if ted_existente is None:
                        ted_existente = documento.find('.//TED')
                    
                    if ted_existente is None:
                        ted_elem = ET.SubElement(documento, "{http://www.sii.cl/SiiDte}TED")
                        ted_elem.set("version", "1.0")
                        dd_elem = ET.SubElement(ted_elem, "{http://www.sii.cl/SiiDte}DD")
                        frmt_elem = ET.SubElement(ted_elem, "{http://www.sii.cl/SiiDte}FRMT")
                        frmt_elem.set("algoritmo", "SHA1withRSA")
                        
                        xml_con_ted = ET.tostring(root, encoding='unicode', method='xml')
                        if not xml_con_ted.strip().startswith('<?xml'):
                            xml_con_ted = '<?xml version="1.0" encoding="ISO-8859-1"?>\n' + xml_con_ted
                        return xml_con_ted
                
                return xml_firmado
            
        except Exception as e:
            print(f"[DTEBox] ⚠️ Error al agregar TED vacío: {str(e)}, usando XML original")
            import traceback
            traceback.print_exc()
            return xml_firmado
    
    def _extraer_dte_desde_enviodte(self, xml_firmado):
        """
        Extrae el DTE interno de un EnvioDTE completo.
        Si el XML es un EnvioDTE, extrae solo el DTE interno.
        
        Args:
            xml_firmado: String con el XML (puede ser EnvioDTE o DTE)
            
        Returns:
            str: XML del DTE extraído (o el XML original si no es EnvioDTE)
        """
        try:
            # Verificar si es un EnvioDTE
            if '<EnvioDTE' not in xml_firmado and 'EnvioDTE' not in xml_firmado:
                return xml_firmado
            
            from lxml import etree as lxml_etree
            
            # Parsear el XML
            root = lxml_etree.fromstring(xml_firmado.encode('ISO-8859-1'))
            
            # Buscar el elemento DTE dentro del EnvioDTE
            ns_sii = "http://www.sii.cl/SiiDte"
            dte = root.find(f'.//{{{ns_sii}}}DTE')
            if dte is None:
                dte = root.find('.//DTE')
            
            if dte is not None:
                # Convertir el DTE a string
                dte_xml = lxml_etree.tostring(
                    dte,
                    pretty_print=True,
                    xml_declaration=True,
                    encoding='ISO-8859-1'
                ).decode('ISO-8859-1')
                
                print(f"[DTEBox] ✅ Extraído DTE desde EnvioDTE (tamaño: {len(dte_xml)} chars)")
                return dte_xml
            
            return xml_firmado
        except Exception as e:
            print(f"[DTEBox] ⚠️ Error al extraer DTE desde EnvioDTE: {str(e)}, usando XML original")
            return xml_firmado
    
    def _remover_ted_timbrado(self, xml_firmado):
        """
        Remueve el TED timbrado del XML y lo reemplaza con un TED vacío.
        DTEBox necesita generar el TED, no recibir uno ya timbrado.
        
        Args:
            xml_firmado: String con el XML del DTE firmado
            
        Returns:
            str: XML con el TED removido/reemplazado por uno vacío
        """
        try:
            from lxml import etree as lxml_etree
            
            # Parsear el XML
            root = lxml_etree.fromstring(xml_firmado.encode('ISO-8859-1'))
            
            ns_sii = "http://www.sii.cl/SiiDte"
            
            # Buscar el elemento Documento
            documento = root.find(f'.//{{{ns_sii}}}Documento')
            if documento is None:
                documento = root.find('.//Documento')
            
            if documento is not None:
                # Buscar el TED existente
                ted_existente = documento.find(f'.//{{{ns_sii}}}TED')
                if ted_existente is None:
                    ted_existente = documento.find('.//TED')
                
                if ted_existente is not None:
                    # Verificar si el TED tiene contenido (está timbrado)
                    dd = ted_existente.find(f'.//{{{ns_sii}}}DD')
                    if dd is None:
                        dd = ted_existente.find('.//DD')
                    
                    # Si el DD tiene contenido, el TED está timbrado y debemos removerlo
                    if dd is not None and len(dd) > 0:
                        # Remover el TED timbrado
                        parent = ted_existente.getparent()
                        parent.remove(ted_existente)
                        
                        # Agregar TED vacío
                        ted_vacio = lxml_etree.SubElement(documento, f"{{{ns_sii}}}TED")
                        ted_vacio.set("version", "1.0")
                        dd_vacio = lxml_etree.SubElement(ted_vacio, f"{{{ns_sii}}}DD")
                        frmt_vacio = lxml_etree.SubElement(ted_vacio, f"{{{ns_sii}}}FRMT")
                        frmt_vacio.set("algoritmo", "SHA1withRSA")
                        
                        print(f"[DTEBox] ✅ Removido TED timbrado y agregado TED vacío")
                        
                        # Convertir de vuelta a string
                        xml_sin_ted = lxml_etree.tostring(
                            root,
                            pretty_print=True,
                            xml_declaration=True,
                            encoding='ISO-8859-1'
                        ).decode('ISO-8859-1')
                        
                        return xml_sin_ted
            
            return xml_firmado
        except Exception as e:
            print(f"[DTEBox] ⚠️ Error al remover TED timbrado: {str(e)}, usando XML original")
            return xml_firmado
    
    def timbrar_dte(self, xml_firmado):
        """
        Envía el XML firmado a DTEBox para obtener el TED
        
        Endpoint: POST http://[ip-dtebox]/api/Core.svc/core/SendDocumentAsXML
        API URL ejemplo: http://200.6.118.43/api/Core.svc/Core
        API Key ejemplo: 0a1c295d-7853-4e2e-ac90-d7d2fd46ecf0
        
        Formato del request según documentación oficial:
        - XML: SendDocumentAsXMLRequest con namespace http://gdexpress.cl/api
        - JSON: Objeto con Environment, Content (base64), ResolutionDate, ResolutionNumber, etc.
        
        Headers requeridos:
        - AuthKey: [Llave de cada box]
        - Content-Type: application/xml o application/json
        - Accept: application/xml o application/json
        
        Args:
            xml_firmado: String con el XML del DTE firmado
            
        Returns:
            dict: {
                'success': bool,
                'ted': str (TED en texto plano, decodificado desde base64),
                'error': str (mensaje de error si hay)
            }
        """
        try:
            # 1. Validar que el XML no esté vacío
            if not xml_firmado or len(xml_firmado.strip()) == 0:
                return {
                    'success': False,
                    'ted': None,
                    'error': 'El XML del DTE está vacío'
                }
            
            # 1.5. Si es un EnvioDTE, extraer solo el DTE interno
            xml_firmado = self._extraer_dte_desde_enviodte(xml_firmado)
            
            # 1.6. Remover TED timbrado si existe y agregar TED vacío (DTEBox debe generarlo)
            xml_firmado = self._agregar_ted_vacio(xml_firmado)
            
            # 2. Validar datos de resolución
            if not self.empresa.resolucion_fecha:
                return {
                    'success': False,
                    'ted': None,
                    'error': 'La fecha de resolución SII no está configurada en la empresa'
                }
            
            if not self.empresa.resolucion_numero:
                return {
                    'success': False,
                    'ted': None,
                    'error': 'El número de resolución SII no está configurado en la empresa'
                }
            
            # 3. Intentar extraer solo el Documento (DTEBox podría necesitar solo esto)
            # Primero intentamos con el XML completo, luego con solo el Documento si falla
            xml_para_enviar = xml_firmado
            
            # 4. Codificar XML en base64
            xml_bytes = xml_para_enviar.encode('ISO-8859-1')
            xml_base64 = base64.b64encode(xml_bytes).decode('ascii')
            
            print(f"[DTEBox] XML original: {len(xml_firmado)} caracteres")
            print(f"[DTEBox] XML original (primeros 500 chars):\n{xml_firmado[:500]}")
            print(f"[DTEBox] XML codificado en base64: {len(xml_base64)} caracteres")
            print(f"[DTEBox] Base64 (primeros 200 chars): {xml_base64[:200]}")
            
            # 4. Preparar datos de resolución
            resolution_date = self.empresa.resolucion_fecha.strftime('%Y-%m-%d')
            resolution_number = self.empresa.resolucion_numero
            
            print(f"[DTEBox] Resolución: {resolution_number} del {resolution_date}")
            print(f"[DTEBox] Ambiente: {self.ambiente}")
            print(f"[DTEBox] PDF417 - Columns: {self.pdf417_columns}, Level: {self.pdf417_level}, Type: {self.pdf417_type}")
            
            # 5. Preparar request - Intentar primero con XML (según documentación)
            # La documentación muestra XML como ejemplo principal
            print(f"[DTEBox] ========== REQUEST DETALLES ==========")
            print(f"[DTEBox] URL completa: {self.url}")
            print(f"[DTEBox] Método: POST")
            print(f"[DTEBox] Intentando primero con formato XML (según documentación)...")
            
            # Generar XML según la documentación oficial
            # Formato exacto según ejemplo proporcionado:
            # <SendDocumentAsXMLRequest xmlns="http://gdexpress.cl/api">
            #   <Environment>T</Environment>
            #   <Content>Base64[]</Content>
            #   <ResolutionDate>2019-01-01</ResolutionDate>
            #   <ResolutionNumber>80</ResolutionNumber>
            #   <PDF417Columns></PDF417Columns>
            #   <PDF417Level></PDF417Level>
            #   <PDF417Type></PDF417Type>
            #   <TED></TED>
            # </SendDocumentAsXMLRequest>
            import xml.etree.ElementTree as ET
            
            # Crear el elemento raíz con namespace por defecto (sin prefijos)
            root = ET.Element("SendDocumentAsXMLRequest")
            root.set("xmlns", "http://gdexpress.cl/api")
            
            # Crear elementos hijos sin namespace explícito (usarán el namespace por defecto)
            env_elem = ET.SubElement(root, "Environment")
            env_elem.text = str(self.ambiente)
            
            content_elem = ET.SubElement(root, "Content")
            content_elem.text = xml_base64
            
            res_date_elem = ET.SubElement(root, "ResolutionDate")
            res_date_elem.text = resolution_date
            
            res_num_elem = ET.SubElement(root, "ResolutionNumber")
            res_num_elem.text = str(int(resolution_number))
            
            # PDF417 - según documentación pueden estar vacíos (se envían como elementos vacíos)
            pdf417_cols_elem = ET.SubElement(root, "PDF417Columns")
            pdf417_cols_elem.text = str(self.pdf417_columns) if self.pdf417_columns else ""
            
            pdf417_level_elem = ET.SubElement(root, "PDF417Level")
            pdf417_level_elem.text = str(self.pdf417_level) if self.pdf417_level else ""
            
            pdf417_type_elem = ET.SubElement(root, "PDF417Type")
            pdf417_type_elem.text = str(self.pdf417_type) if self.pdf417_type else ""
            
            # TED - se envía vacío cuando se usa Timbraje Offline (DTEBox genera el TED)
            ted_elem = ET.SubElement(root, "TED")
            ted_elem.text = ""
            
            # Convertir a string con declaración XML
            # Usar method='xml' para evitar prefijos de namespace
            xml_request_str = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding='unicode', method='xml')
            xml_request = xml_request_str.encode('utf-8')
            
            # Guardar XML del request en archivo para debugging
            try:
                debug_dir = os.path.join(settings.BASE_DIR, 'logs', 'dtebox_debug')
                os.makedirs(debug_dir, exist_ok=True)
                debug_file = os.path.join(debug_dir, f'dtebox_request_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xml')
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(xml_request_str)
                print(f"[DTEBox] XML del request guardado en: {debug_file}")
            except Exception as e:
                print(f"[DTEBox] ⚠️ No se pudo guardar archivo de debug: {str(e)}")
            
            # Headers según documentación oficial:
            # XML: AuthKey, Content-Type: application/xml, Accept: application/xml
            # JSON: AuthKey, Content-Type: application/json, Accept: application/json
            headers_xml = {
                "AuthKey": self.auth_key,
                "Content-Type": "application/xml",
                "Accept": "application/xml"
            }
            
            print(f"[DTEBox] Headers: {headers_xml}")
            print(f"[DTEBox] AuthKey (primeros 10 chars): {self.auth_key[:10]}...")
            print(f"[DTEBox] XML Request completo:\n{xml_request_str}")
            print(f"[DTEBox] XML Request length: {len(xml_request_str)} caracteres")
            print(f"[DTEBox] ========================================")
            
            try:
                response = requests.post(
                    self.url,
                    data=xml_request,
                    headers=headers_xml,
                    timeout=30,
                    verify=False
                )
            except requests.exceptions.ConnectionError as e:
                return {
                    'success': False,
                    'ted': None,
                    'error': f'Error de conexión: No se pudo conectar al servidor DTEBox. Verifique que la URL sea correcta y el servidor esté accesible. URL: {self.url}. Error: {str(e)}'
                }
            
            # Si recibimos 404 o 500 con XML completo, intentar solo con el Documento interno
            if response.status_code in [404, 500]:
                print(f"[DTEBox] ⚠️ Error {response.status_code} con XML completo, intentando solo con elemento Documento...")
                try:
                    # Extraer solo el Documento
                    documento_xml = self._extraer_documento_xml(xml_firmado)
                    documento_bytes = documento_xml.encode('ISO-8859-1')
                    documento_base64 = base64.b64encode(documento_bytes).decode('ascii')
                    
                    # Regenerar XML del request con el Documento extraído (sin prefijos de namespace)
                    root = ET.Element("SendDocumentAsXMLRequest")
                    root.set("xmlns", "http://gdexpress.cl/api")
                    
                    env_elem = ET.SubElement(root, "Environment")
                    env_elem.text = str(self.ambiente)
                    
                    content_elem = ET.SubElement(root, "Content")
                    content_elem.text = documento_base64
                    
                    res_date_elem = ET.SubElement(root, "ResolutionDate")
                    res_date_elem.text = resolution_date
                    
                    res_num_elem = ET.SubElement(root, "ResolutionNumber")
                    res_num_elem.text = str(int(resolution_number))
                    
                    pdf417_cols_elem = ET.SubElement(root, "PDF417Columns")
                    if self.pdf417_columns:
                        pdf417_cols_elem.text = str(self.pdf417_columns)
                    
                    pdf417_level_elem = ET.SubElement(root, "PDF417Level")
                    if self.pdf417_level:
                        pdf417_level_elem.text = str(self.pdf417_level)
                    
                    pdf417_type_elem = ET.SubElement(root, "PDF417Type")
                    if self.pdf417_type:
                        pdf417_type_elem.text = str(self.pdf417_type)
                    
                    ted_elem = ET.SubElement(root, "TED")
                    ted_elem.text = ""
                    
                    xml_request_doc_str = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding='unicode', method='xml')
                    xml_request_doc = xml_request_doc_str.encode('utf-8')
                    
                    print(f"[DTEBox] Intentando con solo elemento Documento...")
                    response = requests.post(
                        self.url,
                        data=xml_request_doc,
                        headers=headers_xml,
                        timeout=30,
                        verify=False
                    )
                    print(f"[DTEBox] Response con Documento extraído - Status: {response.status_code}")
                    
                    # Si aún falla, intentar con JSON como último recurso
                    if response.status_code in [404, 500]:
                        print(f"[DTEBox] ⚠️ Error {response.status_code} con Documento, intentando con JSON como último recurso...")
                    # Formato JSON según documentación oficial:
                    # {
                    #   "Environment" : "T",
                    #   "Content" : "Base64[]",
                    #   "ResolutionDate" : "2019-01-01",
                    #   "ResolutionNumber" : "80",
                    #   "PDF417Columns" : "",
                    #   "PDF417Level" : "",
                    #   "PDF417Type" : "",
                    #   "TED" : ""
                    # }
                    request_data = {
                        "Environment": str(self.ambiente),
                        "Content": documento_base64,  # Usar el Documento extraído
                        "ResolutionDate": resolution_date,
                        "ResolutionNumber": str(int(resolution_number)),  # Como string según ejemplo
                        "PDF417Columns": str(self.pdf417_columns) if self.pdf417_columns else "",
                        "PDF417Level": str(self.pdf417_level) if self.pdf417_level else "",
                        "PDF417Type": str(self.pdf417_type) if self.pdf417_type else "",
                        "TED": ""
                    }
                    
                    headers_json = {
                        "AuthKey": self.auth_key,
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                    
                    print(f"[DTEBox] Intentando con formato JSON...")
                    response = requests.post(
                        self.url,
                        json=request_data,
                        headers=headers_json,
                        timeout=30,
                        verify=False
                    )
                    print(f"[DTEBox] Response con JSON - Status: {response.status_code}")
                except Exception as e_doc:
                    print(f"[DTEBox] Error al intentar con Documento extraído: {str(e_doc)}")
                    # Intentar con JSON como último recurso con XML completo
                    try:
                        request_data = {
                            "Environment": str(self.ambiente),
                            "Content": xml_base64,
                            "ResolutionDate": resolution_date,
                            "ResolutionNumber": int(resolution_number),
                            "PDF417Columns": str(self.pdf417_columns) if self.pdf417_columns else "",
                            "PDF417Level": str(self.pdf417_level) if self.pdf417_level else "",
                            "PDF417Type": str(self.pdf417_type) if self.pdf417_type else "",
                            "TED": ""
                        }
                        
                        headers_json = {
                            "AuthKey": self.auth_key,
                            "Content-Type": "application/json",
                            "Accept": "application/json"
                        }
                        
                        print(f"[DTEBox] Intentando con formato JSON (XML completo)...")
                        response = requests.post(
                            self.url,
                            json=request_data,
                            headers=headers_json,
                            timeout=30,
                            verify=False
                        )
                        print(f"[DTEBox] Response con JSON - Status: {response.status_code}")
                    except Exception as e_json:
                        print(f"[DTEBox] Error al intentar con JSON: {str(e_json)}")
                        # Continuar con el error original de XML
                print(f"[DTEBox] ⚠️ Error 404 con JSON, intentando con XML...")
                try:
                    # Generar XML según la documentación
                    import xml.etree.ElementTree as ET
                    # Crear elemento raíz con namespace
                    root = ET.Element("{http://gdexpress.cl/api}SendDocumentAsXMLRequest")
                    root.set("xmlns", "http://gdexpress.cl/api")
                    
                    ET.SubElement(root, "{http://gdexpress.cl/api}Environment").text = self.ambiente
                    ET.SubElement(root, "{http://gdexpress.cl/api}Content").text = xml_base64
                    ET.SubElement(root, "{http://gdexpress.cl/api}ResolutionDate").text = resolution_date
                    ET.SubElement(root, "{http://gdexpress.cl/api}ResolutionNumber").text = str(resolution_number)
                    # PDF417Columns, PDF417Level, PDF417Type pueden ser opcionales
                    if self.pdf417_columns:
                        ET.SubElement(root, "{http://gdexpress.cl/api}PDF417Columns").text = str(self.pdf417_columns)
                    else:
                        ET.SubElement(root, "{http://gdexpress.cl/api}PDF417Columns")
                    if self.pdf417_level:
                        ET.SubElement(root, "{http://gdexpress.cl/api}PDF417Level").text = str(self.pdf417_level)
                    else:
                        ET.SubElement(root, "{http://gdexpress.cl/api}PDF417Level")
                    if self.pdf417_type:
                        ET.SubElement(root, "{http://gdexpress.cl/api}PDF417Type").text = str(self.pdf417_type)
                    else:
                        ET.SubElement(root, "{http://gdexpress.cl/api}PDF417Type")
                    ET.SubElement(root, "{http://gdexpress.cl/api}TED").text = ""
                    
                    # Convertir a string con declaración XML
                    xml_request = b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding='utf-8')
                    print(f"[DTEBox] XML Request generado:\n{xml_request.decode('utf-8')[:500]}")
                    
                    headers_xml = {
                        "AuthKey": self.auth_key,
                        "Content-Type": "application/xml",
                        "Accept": "application/xml"
                    }
                    
                    print(f"[DTEBox] Intentando con formato XML...")
                    response = requests.post(
                        self.url,
                        data=xml_request,
                        headers=headers_xml,
                        timeout=30,
                        verify=False
                    )
                    print(f"[DTEBox] Response con XML - Status: {response.status_code}")
                except Exception as e_xml:
                    print(f"[DTEBox] Error al intentar con XML: {str(e_xml)}")
                    # Continuar con el error original de JSON
            
            print(f"[DTEBox] ========== RESPONSE DETALLES ==========")
            print(f"[DTEBox] Status Code: {response.status_code}")
            print(f"[DTEBox] Response Headers: {dict(response.headers)}")
            print(f"[DTEBox] Content-Type: {response.headers.get('Content-Type', 'No especificado')}")
            print(f"[DTEBox] Response Content COMPLETO:\n{response.text}")
            
            # Guardar respuesta en archivo para debugging
            try:
                debug_dir = os.path.join(settings.BASE_DIR, 'logs', 'dtebox_debug')
                os.makedirs(debug_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_file = os.path.join(debug_dir, f'dtebox_response_{timestamp}.txt')
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(f"Status Code: {response.status_code}\n")
                    f.write(f"URL: {self.url}\n")
                    f.write(f"Headers: {dict(response.headers)}\n")
                    f.write(f"\nRequest Headers enviados:\n{headers_xml}\n")
                    f.write(f"\nResponse Content COMPLETO:\n{response.text}\n")
                    f.write(f"\n\n=== XML ENVIADO (primeros 2000 chars) ===\n")
                    f.write(xml_request_str[:2000])
                print(f"[DTEBox] Respuesta guardada en: {debug_file}")
            except Exception as e:
                print(f"[DTEBox] ⚠️ No se pudo guardar respuesta de debug: {str(e)}")
            
            print(f"[DTEBox] ========================================")
            
            # 6. Procesar respuesta
            if response.status_code == 200:
                # Intentar parsear como XML primero (formato por defecto según documentación)
                try:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(response.text)
                    
                    # Respuesta según documentación oficial:
                    # Result: 0 (éxito) o 1 (error)
                    # Description: Descripción del error (vacío si es exitoso)
                    # TED: Base64[] con el TED generado
                    result_elem = (root.find('.//{http://gdexpress.cl/api}Result') or 
                                  root.find('.//Result') or
                                  root.find('.//{*}Result'))
                    description_elem = (root.find('.//{http://gdexpress.cl/api}Description') or 
                                        root.find('.//Description') or
                                        root.find('.//{*}Description'))
                    ted_elem = (root.find('.//{http://gdexpress.cl/api}TED') or 
                               root.find('.//TED') or
                               root.find('.//{*}TED'))
                    
                    result = int(result_elem.text) if result_elem is not None and result_elem.text else 1
                    description = description_elem.text if description_elem is not None and description_elem.text else ''
                    ted_base64 = ted_elem.text if ted_elem is not None and ted_elem.text else ''
                    
                    print(f"[DTEBox] Result: {result} (0=éxito, 1=error)")
                    print(f"[DTEBox] Description: {description}")
                    print(f"[DTEBox] TED recibido: {'Sí' if ted_base64 else 'No'}")
                    
                    # Result == 0 significa éxito según documentación
                    if result == 0 and ted_base64:
                        ted_bytes = base64.b64decode(ted_base64)
                        ted_text = ted_bytes.decode('ISO-8859-1')
                        
                        print(f"[DTEBox] ✅ TED recibido exitosamente: {len(ted_text)} caracteres")
                        
                        return {
                            'success': True,
                            'ted': ted_text,
                            'error': None
                        }
                    elif result != 0:
                        return {
                            'success': False,
                            'ted': None,
                            'error': f'Error DTEBox: {description}'
                        }
                    else:
                        return {
                            'success': False,
                            'ted': None,
                            'error': 'TED vacío en la respuesta'
                        }
                except Exception as e_xml:
                    print(f"[DTEBox] Error al parsear como XML: {str(e_xml)}, intentando como JSON...")
                    # Intentar parsear como JSON si falla XML
                    try:
                        # Parsear respuesta JSON según documentación oficial
                        response_data = response.json()
                        
                        result = response_data.get('Result', 1)  # 0=éxito, 1=error
                        description = response_data.get('Description', '')
                        ted_base64 = response_data.get('TED', '')
                        
                        print(f"[DTEBox] Result: {result} (0=éxito, 1=error)")
                        print(f"[DTEBox] Description: {description}")
                        print(f"[DTEBox] TED recibido: {'Sí' if ted_base64 else 'No'}")
                        
                        # Result == 0 significa éxito según documentación
                        if result == 0 and ted_base64:
                            ted_bytes = base64.b64decode(ted_base64)
                            ted_text = ted_bytes.decode('ISO-8859-1')
                            
                            print(f"[DTEBox] ✅ TED recibido exitosamente: {len(ted_text)} caracteres")
                            
                            return {
                                'success': True,
                                'ted': ted_text,
                                'error': None
                            }
                        elif result != 0:
                            return {
                                'success': False,
                                'ted': None,
                                'error': f'Error DTEBox: {description}'
                            }
                        else:
                            return {
                                'success': False,
                                'ted': None,
                                'error': 'TED vacío en la respuesta'
                            }
                    except Exception as e_json:
                        return {
                            'success': False,
                            'ted': None,
                            'error': f'Error al parsear respuesta (ni XML ni JSON): {str(e_json)}. Respuesta: {response.text[:300]}'
                        }
            else:
                # Error HTTP - intentar parsear respuesta
                error_msg = f'HTTP Error {response.status_code}'
                
                # Si es error 500, puede ser un Fault de SOAP/WCF
                if response.status_code == 500:
                    try:
                        # Intentar parsear como SOAP Fault
                        import xml.etree.ElementTree as ET
                        if response.text.strip().startswith('<') or '<Fault' in response.text:
                            root = ET.fromstring(response.text)
                            
                            # Buscar mensaje de error en el Fault
                            reason_elem = root.find('.//{http://schemas.microsoft.com/ws/2005/05/envelope/none}Reason')
                            if reason_elem is None:
                                reason_elem = root.find('.//Reason')
                            if reason_elem is None:
                                reason_elem = root.find('.//reason')
                            
                            text_elem = None
                            if reason_elem is not None:
                                text_elem = reason_elem.find('.//{http://schemas.microsoft.com/ws/2005/05/envelope/none}Text')
                                if text_elem is None:
                                    text_elem = reason_elem.find('.//Text')
                                if text_elem is None:
                                    text_elem = reason_elem.find('.//text')
                            
                            if text_elem is not None and text_elem.text:
                                error_msg += f': {text_elem.text}'
                            else:
                                # Buscar en otros lugares comunes
                                detail_elem = root.find('.//{http://schemas.microsoft.com/ws/2005/05/envelope/none}Detail')
                                if detail_elem is None:
                                    detail_elem = root.find('.//Detail')
                                if detail_elem is not None:
                                    error_msg += f': {ET.tostring(detail_elem, encoding="unicode")[:200]}'
                                else:
                                    error_msg += f': Error del servidor DTEBox - {response.text[:300]}'
                        else:
                            # Intentar parsear como JSON
                            if response.text.strip().startswith('{'):
                                error_json = response.json()
                                error_msg += f': {error_json.get("Description", error_json.get("error", error_json.get("message", response.text[:200])))}'
                            else:
                                error_msg += f': {response.text[:300]}'
                    except Exception as e_parse:
                        error_msg += f': Error del servidor DTEBox. Respuesta: {response.text[:300]}'
                elif 'text/html' in response.headers.get('Content-Type', ''):
                    # Si la respuesta es HTML (página de error), extraer información útil
                    import re
                    title_match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
                    if title_match:
                        error_msg += f': {title_match.group(1)}'
                    else:
                        error_msg += ': Página no encontrada (404) - Verifique que la URL del servidor DTEBox sea correcta'
                else:
                    # Intentar parsear como JSON o XML
                    try:
                        if response.text.strip().startswith('{'):
                            error_json = response.json()
                            error_msg += f': {error_json.get("Description", error_json.get("error", response.text[:200]))}'
                        elif response.text.strip().startswith('<'):
                            import xml.etree.ElementTree as ET
                            root = ET.fromstring(response.text)
                            error_elem = root.find('.//Description') or root.find('.//error') or root.find('.//message')
                            if error_elem is not None:
                                error_msg += f': {error_elem.text}'
                            else:
                                error_msg += f': {response.text[:200]}'
                        else:
                            error_msg += f': {response.text[:200]}'
                    except:
                        error_msg += f': {response.text[:200]}'
                
                # Agregar información adicional para debugging
                if response.status_code == 500:
                    error_msg += '\n\n⚠️ El servidor DTEBox está reportando un error interno (500).'
                    error_msg += '\n\nPosibles causas:'
                    error_msg += '\n1. El XML del DTE no es válido o está mal formado'
                    error_msg += '\n2. Los datos de resolución (fecha/número) no coinciden con los del servidor'
                    error_msg += '\n3. El formato del request XML no es el esperado por el servidor'
                    error_msg += '\n4. El servidor DTEBox necesita configuración adicional'
                    error_msg += '\n\nRevisa los logs del servidor Django para ver:'
                    error_msg += '\n- El XML del DTE enviado (primeros caracteres)'
                    error_msg += '\n- Los datos de resolución utilizados'
                    error_msg += '\n- El formato del request XML generado'
                
                return {
                    'success': False,
                    'ted': None,
                    'error': error_msg
                }
                
        except requests.exceptions.RequestException as e:
            print(f"[DTEBox] ❌ Error de conexión: {str(e)}")
            return {
                'success': False,
                'ted': None,
                'error': f'Error de conexión con DTEBox: {str(e)}'
            }
        except Exception as e:
            print(f"[DTEBox] ❌ Error inesperado: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'ted': None,
                'error': f'Error inesperado: {str(e)}'
            }
    
    def obtener_pdf(self, tipo_dte, folio, rut_emisor=None):
        """
        Obtiene el PDF de un documento desde DTEBox
        
        Args:
            tipo_dte: Tipo de documento (33=Factura, 34=Factura Exenta, etc.)
            folio: Número de folio del documento
            rut_emisor: RUT del emisor (opcional, usa el de la empresa si no se proporciona)
            
        Returns:
            dict: {
                'success': bool,
                'pdf': bytes o None,
                'error': str o None
            }
        """
        try:
            # Usar RUT de la empresa si no se proporciona
            if not rut_emisor:
                rut_emisor = self.empresa.rut
            
            # Formatear RUT: quitar puntos pero mantener guión
            rut_formateado = rut_emisor.replace('.', '')
            
            # Construir URL base
            url_base = self.empresa.dtebox_url.strip().rstrip('/')
            
            # Normalizar URL base
            if '/api/Core.svc' in url_base or '/api/core.svc' in url_base:
                base_url = url_base.split('/api/')[0] + '/api/Core.svc'
            else:
                base_url = url_base
            
            # Normalizar a minúsculas en /core
            base_url = base_url.replace('/Core.svc/Core', '/Core.svc/core').replace('/core.svc/core', '/Core.svc/core')
            
            # Construir endpoint completo según formato: /RecoverPDF_V2/{Ambiente}/E/{RUT}/{TipoDTE}/{Folio}
            endpoint = f"{base_url}/core/RecoverPDF_V2/{self.ambiente}/E/{rut_formateado}/{tipo_dte}/{folio}"
            
            print(f"[DTEBox] Obteniendo PDF - Tipo: {tipo_dte}, Folio: {folio}, RUT: {rut_formateado}")
            print(f"[DTEBox] Endpoint: {endpoint}")
            
            # Headers con AuthKey
            headers = {
                'AuthKey': self.auth_key,
                'Accept': 'application/pdf, application/json, */*'
            }
            
            # Realizar solicitud GET
            response = requests.get(
                endpoint,
                headers=headers,
                timeout=30,
                verify=False
            )
            
            print(f"[DTEBox] Response Status: {response.status_code}")
            print(f"[DTEBox] Content-Type: {response.headers.get('Content-Type', 'N/A')}")
            print(f"[DTEBox] Content-Length: {len(response.content)} bytes")
            
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '').lower()
                
                # Verificar si la respuesta es un PDF directo
                if 'application/pdf' in content_type or 'pdf' in content_type:
                    print(f"[DTEBox] ✅ PDF obtenido directamente")
                    return {
                        'success': True,
                        'pdf': response.content,
                        'error': None
                    }
                
                # Si la respuesta es JSON, puede contener el PDF en Base64
                elif 'application/json' in content_type:
                    try:
                        json_response = response.json()
                        
                        # Buscar campo PDF o Data en Base64
                        pdf_base64 = None
                        for key in ['PDF', 'Content', 'Document', 'File', 'Data']:
                            if key in json_response:
                                pdf_base64 = json_response[key]
                                break
                        
                        if pdf_base64:
                            pdf_bytes = base64.b64decode(pdf_base64)
                            print(f"[DTEBox] ✅ PDF obtenido desde Base64 ({len(pdf_bytes)} bytes)")
                            return {
                                'success': True,
                                'pdf': pdf_bytes,
                                'error': None
                            }
                        else:
                            error_msg = f"No se encontró campo PDF/Data en la respuesta JSON"
                            print(f"[DTEBox] ❌ {error_msg}")
                            return {
                                'success': False,
                                'pdf': None,
                                'error': error_msg
                            }
                    except json.JSONDecodeError as e:
                        error_msg = f"Error al parsear JSON: {str(e)}"
                        print(f"[DTEBox] ❌ {error_msg}")
                        return {
                            'success': False,
                            'pdf': None,
                            'error': error_msg
                        }
                
                # Si la respuesta es texto, puede ser Base64
                elif 'text' in content_type:
                    try:
                        pdf_base64 = response.text.strip()
                        pdf_bytes = base64.b64decode(pdf_base64)
                        print(f"[DTEBox] ✅ PDF obtenido desde Base64 (texto) ({len(pdf_bytes)} bytes)")
                        return {
                            'success': True,
                            'pdf': pdf_bytes,
                            'error': None
                        }
                    except Exception as e:
                        error_msg = f"No se pudo decodificar como Base64: {str(e)}"
                        print(f"[DTEBox] ❌ {error_msg}")
                        return {
                            'success': False,
                            'pdf': None,
                            'error': error_msg
                        }
                
                # Si es binario pero no PDF reconocido, verificar firma PDF
                elif len(response.content) > 0:
                    if response.content[:4] == b'%PDF':
                        print(f"[DTEBox] ✅ PDF obtenido (detectado por firma PDF) ({len(response.content)} bytes)")
                        return {
                            'success': True,
                            'pdf': response.content,
                            'error': None
                        }
                    else:
                        error_msg = f"Tipo de contenido no reconocido: {content_type}"
                        print(f"[DTEBox] ❌ {error_msg}")
                        return {
                            'success': False,
                            'pdf': None,
                            'error': error_msg
                        }
                else:
                    error_msg = "Respuesta vacía del servidor"
                    print(f"[DTEBox] ❌ {error_msg}")
                    return {
                        'success': False,
                        'pdf': None,
                        'error': error_msg
                    }
            
            elif response.status_code == 404:
                error_msg = f"Documento no encontrado (404) - Tipo: {tipo_dte}, Folio: {folio}"
                print(f"[DTEBox] ❌ {error_msg}")
                return {
                    'success': False,
                    'pdf': None,
                    'error': error_msg
                }
            elif response.status_code == 401:
                error_msg = "No autorizado (401) - Verificar AuthKey"
                print(f"[DTEBox] ❌ {error_msg}")
                return {
                    'success': False,
                    'pdf': None,
                    'error': error_msg
                }
            elif response.status_code == 403:
                error_msg = "Prohibido (403) - Sin permisos para acceder al recurso"
                print(f"[DTEBox] ❌ {error_msg}")
                return {
                    'success': False,
                    'pdf': None,
                    'error': error_msg
                }
            elif response.status_code == 500:
                error_msg = f"Error del servidor (500): {response.text[:500]}"
                print(f"[DTEBox] ❌ {error_msg}")
                return {
                    'success': False,
                    'pdf': None,
                    'error': error_msg
                }
            else:
                error_msg = f"Status code no esperado ({response.status_code}): {response.text[:500]}"
                print(f"[DTEBox] ❌ {error_msg}")
                return {
                    'success': False,
                    'pdf': None,
                    'error': error_msg
                }
        
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Error de conexión: {str(e)}"
            print(f"[DTEBox] ❌ {error_msg}")
            return {
                'success': False,
                'pdf': None,
                'error': error_msg
            }
        except requests.exceptions.Timeout as e:
            error_msg = f"Timeout: {str(e)}"
            print(f"[DTEBox] ❌ {error_msg}")
            return {
                'success': False,
                'pdf': None,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"Error inesperado: {str(e)}"
            print(f"[DTEBox] ❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'pdf': None,
                'error': error_msg
            }
    
    def _verificar_documento_timbrado(self, xml_completo):
        """
        Verifica si el documento XML tiene TED timbrado (ya aceptado por el SII)
        
        Args:
            xml_completo: String con el XML completo del documento
            
        Returns:
            dict: {
                'timbrado': bool,
                'tipo': str,  # 'timbrado', 'sin_ted', 'ted_vacio'
                'mensaje': str
            }
        """
        try:
            # Verificar si tiene elemento TED
            if '<TED' not in xml_completo and '<ns0:TED' not in xml_completo and '<ns1:TED' not in xml_completo:
                return {
                    'timbrado': False,
                    'tipo': 'sin_ted',
                    'mensaje': 'El documento no tiene elemento TED'
                }
            
            # Verificar si el TED tiene contenido (está timbrado)
            import re
            
            # Buscar el elemento DD dentro de TED (indica que está timbrado)
            ted_pattern = r'<TED[^>]*>.*?<DD[^>]*>(.*?)</DD>'
            match = re.search(ted_pattern, xml_completo, re.DOTALL | re.IGNORECASE)
            
            if match:
                dd_content = match.group(1).strip()
                # Si DD tiene contenido significativo (no solo espacios/lineas), está timbrado
                if dd_content and len(dd_content) > 10:  # Contenido mínimo esperado
                    # Verificar elementos específicos del TED timbrado
                    if '<RE>' in dd_content or '<TD>' in dd_content or '<F>' in dd_content:
                        return {
                            'timbrado': True,
                            'tipo': 'timbrado',
                            'mensaje': 'El documento ya tiene TED timbrado (aceptado por el SII)'
                        }
            
            # Si tiene TED pero está vacío o no tiene DD
            return {
                'timbrado': False,
                'tipo': 'ted_vacio',
                'mensaje': 'El documento tiene TED pero no está timbrado'
            }
            
        except Exception as e:
            print(f"[DTEBox] ⚠️ Error al verificar TED: {str(e)}")
            # En caso de error, asumir que puede estar timbrado
            return {
                'timbrado': True,
                'tipo': 'desconocido',
                'mensaje': f'No se pudo verificar el estado del TED: {str(e)}'
            }
    
    def reenviar_documento(self, xml_completo):
        """
        Reenvía un documento ya timbrado a DTEBox
        
        IMPORTANTE: Este método solo debe usarse para reenviar documentos que ya fueron
        timbrados pero que aún no han sido aceptados por el SII. Si el documento ya fue
        aceptado por el SII, DTEBox no permitirá reenviarlo.
        
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
            
            # Verificar si el documento tiene TED timbrado
            verificacion = self._verificar_documento_timbrado(xml_completo)
            print(f"[DTEBox] Estado del documento: {verificacion['mensaje']}")
            
            if verificacion['timbrado']:
                # El documento tiene TED timbrado, advertir al usuario
                print(f"[DTEBox] ⚠️ ADVERTENCIA: El documento tiene TED timbrado")
                print(f"[DTEBox] ⚠️ Si el documento ya fue aceptado por el SII, DTEBox no permitirá reenviarlo")
            
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
                # Intentar detectar si el error es porque el documento ya está timbrado/aceptado
                error_text = response.text.lower()
                
                # Verificar si el documento tiene TED timbrado
                verificacion = self._verificar_documento_timbrado(xml_completo)
                
                # Mensaje específico si el documento está timbrado
                if verificacion['timbrado']:
                    error_msg = (
                        "El documento ya está timbrado y no se puede reenviar. "
                        "Si el documento fue aceptado por el SII, DTEBox no permite reenviarlo. "
                        "Solo se pueden reenviar documentos timbrados que aún no han sido aceptados por el SII."
                    )
                    print(f"[DTEBox] ❌ {error_msg}")
                    return {
                        'success': False,
                        'message': None,
                        'error': error_msg
                    }
                else:
                    # Error genérico del servidor
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

