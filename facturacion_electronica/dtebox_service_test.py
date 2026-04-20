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
        
        # Construir URL: /api/Core.svc/core/SendDocumentAsXML
        # IMPORTANTE: Core.svc con C mayúscula, /core con c minúscula
        url_base = empresa.dtebox_url.strip().rstrip('/')
        
        # Remover /Core o /core final si existe
        if url_base.endswith('/Core') or url_base.endswith('/core'):
            url_base = url_base[:-5]
        
        # Construir URL final
        if '/SendDocumentAsXML' in url_base:
            self.url = url_base
        elif 'Core.svc' in url_base:
            self.url = f"{url_base}/core/SendDocumentAsXML"
        elif '/api' in url_base:
            self.url = f"{url_base}/Core.svc/core/SendDocumentAsXML"
        else:
            self.url = f"{url_base}/api/Core.svc/core/SendDocumentAsXML"
        
        print(f"[DTEBox] URL base configurada: {empresa.dtebox_url}")
        print(f"[DTEBox] URL final construida: {self.url}")
        
        self.auth_key = empresa.dtebox_auth_key
        self.ambiente = empresa.dtebox_ambiente or 'T'
        self.pdf417_columns = empresa.dtebox_pdf417_columns or 5
        self.pdf417_level = empresa.dtebox_pdf417_level or 2
        self.pdf417_type = empresa.dtebox_pdf417_type or 1
        
        print(f"[DTEBox] Servicio inicializado - URL: {self.url}, Ambiente: {self.ambiente}")
    
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
                print(f"[DTEBox] [WARN] No se encontró elemento Documento, usando XML completo")
                return xml_firmado
        except Exception as e:
            print(f"[DTEBox] [WARN] Error al extraer Documento: {str(e)}, usando XML completo")
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
                
                print(f"[DTEBox] [OK] Extraído DTE desde EnvioDTE (tamaño: {len(dte_xml)} chars)")
                return dte_xml
            
            return xml_firmado
        except Exception as e:
            print(f"[DTEBox] [WARN] Error al extraer DTE desde EnvioDTE: {str(e)}, usando XML original")
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
                        
                        print(f"[DTEBox] [OK] Removido TED timbrado y agregado TED vacío")
                        
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
            print(f"[DTEBox] [WARN] Error al remover TED timbrado: {str(e)}, usando XML original")
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
                
                print(f"[DTEBox] [OK] El XML ya tiene elemento TED (vacío)")
                return xml_firmado
            
            # Usar lxml para mejor control del formato y evitar prefijos de namespace
            try:
                from lxml import etree as lxml_etree
                
                # Parsear el XML preservando namespaces
                root = lxml_etree.fromstring(xml_firmado.encode('ISO-8859-1'))
                
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
                        
                        print(f"[DTEBox] [OK] Agregado elemento TED con estructura básica al XML del DTE")
                        
                        # Convertir de vuelta a string preservando el formato original sin prefijos
                        xml_con_ted = lxml_etree.tostring(
                            root,
                            pretty_print=True,
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
            print(f"[DTEBox] [WARN] Error al agregar TED vacío: {str(e)}, usando XML original")
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
                
                print(f"[DTEBox] [OK] Extraído DTE desde EnvioDTE (tamaño: {len(dte_xml)} chars)")
                return dte_xml
            
            return xml_firmado
        except Exception as e:
            print(f"[DTEBox] [WARN] Error al extraer DTE desde EnvioDTE: {str(e)}, usando XML original")
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
                        
                        print(f"[DTEBox] [OK] Removido TED timbrado y agregado TED vacío")
                        
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
            print(f"[DTEBox] [WARN] Error al remover TED timbrado: {str(e)}, usando XML original")
            return xml_firmado
    
    def _remover_firma_xml(self, xml_firmado):
        """
        Remueve la firma digital (Signature) del XML firmado.
        Para API REST, DTEBox requiere XML sin firmar según soporte GDExpress.
        
        Args:
            xml_firmado: String con el XML del DTE firmado
            
        Returns:
            str: XML sin la firma digital
        """
        try:
            from lxml import etree as lxml_etree
            
            # Parsear el XML
            root = lxml_etree.fromstring(xml_firmado.encode('ISO-8859-1'))
            
            # Namespaces comunes para firmas XMLDSig
            ns_dsig = "http://www.w3.org/2000/09/xmldsig#"
            
            # Buscar y remover todos los elementos Signature
            signatures = root.findall(f'.//{{{ns_dsig}}}Signature')
            if not signatures:
                # Intentar sin namespace
                signatures = root.findall('.//Signature')
            
            for signature in signatures:
                parent = signature.getparent()
                if parent is not None:
                    parent.remove(signature)
                    print(f"[DTEBox] [OK] Removida firma digital del XML")
            
            # Convertir de vuelta a string
            xml_sin_firma = lxml_etree.tostring(
                root,
                pretty_print=True,
                xml_declaration=True,
                encoding='ISO-8859-1'
            ).decode('ISO-8859-1')
            
            return xml_sin_firma
            
        except Exception as e:
            print(f"[DTEBox] [WARN] Error al remover firma: {str(e)}, usando XML original")
            return xml_firmado
    
    def _remover_ted_completo(self, xml_firmado):
        """
        Remueve completamente el elemento TED del XML.
        Según soporte GDExpress, el TED debe ser removido completamente para API REST.
        
        Args:
            xml_firmado: String con el XML del DTE
            
        Returns:
            str: XML sin el elemento TED
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
                # Buscar el TED existente (vacío o timbrado)
                ted_existente = documento.find(f'.//{{{ns_sii}}}TED')
                if ted_existente is None:
                    ted_existente = documento.find('.//TED')
                
                if ted_existente is not None:
                    # Remover completamente el TED
                    parent = ted_existente.getparent()
                    if parent is not None:
                        parent.remove(ted_existente)
                        print(f"[DTEBox] [OK] Removido completamente el elemento TED del XML")
                        
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
            print(f"[DTEBox] [WARN] Error al remover TED: {str(e)}, usando XML original")
            return xml_firmado
    
    def timbrar_dte(self, xml_firmado):
        """
        Envía el XML a DTEBox para obtener el TED.
        IMPORTANTE: Para API REST, el XML NO debe ir firmado y NO debe tener elemento TED.
        
        Args:
            xml_firmado: String con el XML del DTE (puede venir firmado)
            
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
            
            # 1.6. Remover la firma digital del XML (API REST no acepta XML firmado)
            xml_firmado = self._remover_firma_xml(xml_firmado)
            
            # 1.7. Remover completamente el elemento TED (según soporte GDExpress)
            xml_firmado = self._remover_ted_completo(xml_firmado)
            
            # 1.8. LIMPIAR XML COMO EN KREADTE-CLOUD:
            # - Extraer solo el bloque <DTE>...</DTE>
            # - Remover namespaces del tag DTE
            # - Agregar declaración XML
            import re
            
            # Buscar inicio y fin del tag DTE
            start_dte = xml_firmado.find('<DTE')
            end_dte = xml_firmado.find('</DTE>')
            
            if start_dte != -1 and end_dte != -1:
                # Extraer solo el bloque DTE
                dte_xml = xml_firmado[start_dte:end_dte + 6]  # +6 para incluir </DTE>
                
                # SIMPLIFICAR el tag DTE quitando namespaces (CRÍTICO para DTEBox)
                dte_xml = re.sub(r'<DTE[^>]*>', '<DTE version="1.0">', dte_xml, count=1)
                
                # REMOVER FIRMA si quedó dentro del bloque DTE (CRÍTICO)
                # Remover todo el bloque <Signature>...</Signature> o <ds:Signature>...</ds:Signature>
                dte_xml = re.sub(r'<[^:>]*:?Signature[^>]*>.*?</[^:>]*:?Signature>', '', dte_xml, flags=re.DOTALL)
                
                # REMOVER TED si quedó (aunque ya debería estar removido)
                dte_xml = re.sub(r'<TED[^>]*>.*?</TED>', '', dte_xml, flags=re.DOTALL)
                
                # Agregar declaración XML
                xml_firmado = '<?xml version="1.0" encoding="ISO-8859-1"?>' + dte_xml
                
                print(f"[DTEBox] XML limpiado: namespace removido, firma removida, solo DTE version='1.0'")
                print(f"[DTEBox] Verificación - Tiene Signature: {'<Signature' in xml_firmado or '<ds:Signature' in xml_firmado}")
                print(f"[DTEBox] Verificación - Tiene TED: {'<TED' in xml_firmado}")
            
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
            
            # 5. Preparar request en formato XML (SendDocumentAsXMLRequest)
            print(f"[DTEBox] ========== REQUEST DETALLES ==========")
            print(f"[DTEBox] URL completa: {self.url}")
            print(f"[DTEBox] Método: POST")
            print(f"[DTEBox] Usando formato XML (SendDocumentAsXMLRequest)...")

            import xml.etree.ElementTree as ET

            root_req = ET.Element("SendDocumentAsXMLRequest")
            root_req.set("xmlns", "http://gdexpress.cl/api")
            
            # ORDEN CRÍTICO: Debe coincidir exactamente con libreria_dte_gdexpress
            ET.SubElement(root_req, "Environment").text = str(self.ambiente)
            ET.SubElement(root_req, "Content").text = xml_base64
            ET.SubElement(root_req, "ResolutionNumber").text = str(int(resolution_number))  # ← NÚMERO ANTES DE FECHA
            ET.SubElement(root_req, "ResolutionDate").text = resolution_date
            
            # PDF417 params CON VALORES (no vacíos)
            ET.SubElement(root_req, "PDF417Columns").text = "5"
            ET.SubElement(root_req, "PDF417Level").text = "2"
            ET.SubElement(root_req, "PDF417Type").text = "1"
            ET.SubElement(root_req, "TED").text = ""

            # Serializar con encoding UTF-8 (no unicode)
            xml_request = b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root_req, encoding='utf-8', method='xml')

            # Guardar request en archivo para debugging
            try:
                debug_dir = os.path.join(settings.BASE_DIR, 'logs', 'dtebox_debug')
                os.makedirs(debug_dir, exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                debug_file = os.path.join(debug_dir, f'dtebox_request_{timestamp}.xml')
                with open(debug_file, 'wb') as f:  # Escribir en modo binario
                    f.write(xml_request)
                print(f"[DTEBox] XML del request guardado en: {debug_file}")
            except Exception as e:
                print(f"[DTEBox] [WARN] No se pudo guardar archivo de debug: {str(e)}")

            headers_xml = {
                "AuthKey": self.auth_key,
                "Content-Type": "application/xml",
                "Accept": "application/xml"
            }

            print(f"[DTEBox] Headers: {headers_xml}")
            print(f"[DTEBox] AuthKey (primeros 10 chars): {self.auth_key[:10]}...")
            print(f"[DTEBox] XML Request (primeros 500 chars): {xml_request[:500].decode('utf-8')}...")
            print(f"[DTEBox] XML Request length: {len(xml_request)} bytes")
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
            
            # Procesar respuesta
            print(f"[DTEBox] ========== RESPONSE DETALLES ==========")
            print(f"[DTEBox] Status Code: {response.status_code}")
            
            # Guardar respuesta completa para debugging
            try:
                debug_dir = os.path.join(settings.BASE_DIR, 'logs', 'dtebox_debug')
                os.makedirs(debug_dir, exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                response_file = os.path.join(debug_dir, f'dtebox_response_{timestamp}.txt')
                with open(response_file, 'w', encoding='utf-8') as f:
                    f.write(f"Status Code: {response.status_code}\n")
                    f.write(f"URL: {self.url}\n")
                    f.write(f"Headers: {response.headers}\n\n")
                    f.write(f"Request Headers enviados:\n{headers_json}\n\n")
                    f.write(f"Response Content COMPLETO:\n{response.text}\n")
                print(f"[DTEBox] Respuesta guardada en: {response_file}")
            except Exception as e:
                print(f"[DTEBox] [WARN] Error guardando respuesta: {str(e)}")
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'ted': None,
                    'error': f'HTTP Error {response.status_code}: {response.text}'
                }

            # Parsear respuesta XML según documentación DTEBox
            try:
                import xml.etree.ElementTree as ET
                root_resp = ET.fromstring(response.text)

                # Manejar namespace opcional
                ns = '{http://gdexpress.cl/api}'
                result_elem = (root_resp.find(f'.//{ns}Result') or
                               root_resp.find('.//Result') or
                               root_resp.find('.//{*}Result'))
                desc_elem = (root_resp.find(f'.//{ns}Description') or
                             root_resp.find('.//Description') or
                             root_resp.find('.//{*}Description'))
                ted_elem = (root_resp.find(f'.//{ns}TED') or
                            root_resp.find('.//TED') or
                            root_resp.find('.//{*}TED'))

                result = result_elem.text if result_elem is not None else '1'
                description = desc_elem.text if desc_elem is not None else ''

                if str(result) == '0':
                    # Éxito - extraer TED en base64 y decodificar
                    ted_b64 = ted_elem.text if ted_elem is not None else ''
                    if ted_b64:
                        try:
                            ted_decoded = base64.b64decode(ted_b64).decode('ISO-8859-1')
                            print(f"[DTEBox] [OK] TED obtenido exitosamente")
                            return {
                                'success': True,
                                'ted': ted_decoded,
                                'error': None
                            }
                        except Exception as e:
                            return {
                                'success': False,
                                'ted': None,
                                'error': f'Error al decodificar TED: {str(e)}'
                            }
                    else:
                        return {
                            'success': False,
                            'ted': None,
                            'error': 'Respuesta exitosa pero sin TED'
                        }
                else:
                    # Error con descripción
                    error_desc = description or 'Error desconocido'
                    return {
                        'success': False,
                        'ted': None,
                        'error': f'Error DTEBox: {error_desc}'
                    }

            except Exception as e:
                # Si la respuesta no es XML válido, devolver texto bruto
                return {
                    'success': False,
                    'ted': None,
                    'error': f'Error al procesar respuesta DTEBox: {str(e)}. Respuesta: {response.text[:500]}'
                }
                
        except Exception as e:
            print(f"[DTEBox] [ERROR] Error inesperado: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'ted': None,
                'error': f'Error inesperado: {str(e)}'
            }
    
    def _extraer_dte_desde_enviodte(self, xml_str):
        """
        Extrae el DTE interno de un EnvioDTE completo.
        
        Args:
            xml_str: XML que puede contener un EnvioDTE o un DTE directo
            
        Returns:
            str: XML del DTE extraído, o el XML original si no es un EnvioDTE
        """
        try:
            from lxml import etree as lxml_etree
            
            root = lxml_etree.fromstring(xml_str.encode('ISO-8859-1'))
            
            # Buscar elementos EnvioDTE (puede tener namespace)
            envio_elems = (root.findall('.//{http://www.sii.cl/SiiDte}EnvioDTE') +
                          root.findall('.//EnvioDTE'))
            
            if envio_elems:
                # Si encontramos EnvioDTE, extraer el primer DTE interno
                print("[DTEBox] Encontrado EnvioDTE, extrayendo DTE interno...")
                
                dte_elems = (root.findall('.//{http://www.sii.cl/SiiDte}DTE') +
                            root.findall('.//DTE'))
                
                if dte_elems:
                    dte_elem = dte_elems[0]
                    # Convertir de vuelta a string XML
                    dte_xml = lxml_etree.tostring(
                        dte_elem,
                        pretty_print=True,
                        xml_declaration=True,
                        encoding='ISO-8859-1'
                    ).decode('ISO-8859-1')
                    
                    print(f"[DTEBox] [OK] DTE extraído del EnvioDTE")
                    return dte_xml
                else:
                    print("[DTEBox] No se encontró DTE dentro del EnvioDTE")
                    return xml_str
            else:
                # No es un EnvioDTE, devolver tal cual
                print("[DTEBox] No es un EnvioDTE, usando XML original")
                return xml_str
                
        except Exception as e:
            print(f"[DTEBox] [WARN] Error al extraer DTE: {str(e)}, usando XML original")
            return xml_str
    
    def descargar_pdf_gdexpress(self, dte):
        """
        Descarga el PDF de un DTE desde GDExpress/DTEBox
        
        Args:
            dte: Instancia de DocumentoTributarioElectronico
            
        Returns:
            dict: {
                'success': bool,
                'pdf_content': bytes (si success=True),
                'filename': str (si success=True),
                'error': str (si success=False)
            }
        """
        # Intentar con diferentes combinaciones de endpoints y grupos
        # Algunos documentos pueden estar en grupo 'E' (emitidos) o 'R' (recibidos)
        # dependiendo del estado de procesamiento en GDExpress
        
        endpoints = ['RecoverPDF_V2', 'RecoverPDF']
        grupos = ['E']  # Empezar solo con Emitidos
        
        # Si es Guía de Despacho (tipo 52), puede estar en grupo diferente
        if dte.tipo_dte == '52':
            # Para guías, intentar también con grupo R si falla con E
            grupos.append('R')
        
        for endpoint in endpoints:
            for grupo in grupos:
                resultado = self._intentar_descargar_pdf(dte, endpoint, grupo)
                if resultado['success']:
                    return resultado
                else:
                    print(f"[DTEBox PDF] Fallo con {endpoint} / Grupo {grupo}: {resultado['error']}")
        
        # Si ninguno funciona, retornar el último error
        return resultado
    
    def _intentar_descargar_pdf(self, dte, endpoint_name, grupo='E'):
        """
        Intenta descargar el PDF usando un endpoint específico
        
        Args:
            dte: Instancia de DocumentoTributarioElectronico
            endpoint_name: 'RecoverPDF_V2' o 'RecoverPDF'
            grupo: 'E' (emitidos) o 'R' (recibidos)
            
        Returns:
            dict con success, pdf_content/error
        """
        try:
            # Construir URL para descargar PDF
            # Endpoint: /api/Core.svc/core/RecoverPDF[_V2]/{ambiente}/{grupo}/{rut_emisor}/{tipo_dte}/{folio}
            # Ambiente: T (test) o P (producción)
            # Grupo: E (emitidos) o R (recibidos)
            
            url_base = self.url.replace('/SendDocumentAsXML', '')
            
            # Preparar parámetros
            # IMPORTANTE: GDExpress espera el RUT sin puntos pero CON guión
            # Ejemplo: 77117239-3 (NO 771172393)
            rut_emisor = self.empresa.rut.replace('.', '')
            tipo_dte = dte.tipo_dte
            folio = dte.folio
            ambiente = self.ambiente  # 'T' o 'P'
            
            # Construir URL completa
            url = f"{url_base}/{endpoint_name}/{ambiente}/{grupo}/{rut_emisor}/{tipo_dte}/{folio}"
            
            headers = {
                'AuthKey': self.auth_key,
                'Content-Type': 'application/json'
            }
            
            print(f"[DTEBox PDF] Solicitando PDF con {endpoint_name}...")
            print(f"[DTEBox PDF] URL: {url}")
            print(f"[DTEBox PDF] Parametros: Ambiente={ambiente}, Grupo={grupo}, RUT={rut_emisor}, Tipo={tipo_dte}, Folio={folio}")
            
            response = requests.get(
                url,
                headers=headers,
                timeout=30
            )
            
            print(f"[DTEBox PDF] Status Code: {response.status_code}")
            print(f"[DTEBox PDF] Content-Type: {response.headers.get('Content-Type', 'N/A')}")
            
            if response.status_code == 200:
                # La respuesta puede ser JSON, XML o directamente bytes del PDF
                content_type = response.headers.get('Content-Type', '')
                
                if 'application/xml' in content_type or 'text/xml' in content_type:
                    # Respuesta XML - puede contener el PDF en base64 o un error
                    try:
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(response.content)
                        
                        # Buscar el campo Data que puede contener el PDF en base64
                        data_element = root.find('.//{http://gdexpress.cl/api}Data')
                        
                        if data_element is not None and data_element.text:
                            # Hay datos, intentar decodificar como PDF
                            try:
                                import base64
                                pdf_content = base64.b64decode(data_element.text)
                                
                                # Verificar que sea un PDF válido
                                if pdf_content.startswith(b'%PDF'):
                                    filename = f"DTE_{dte.tipo_dte}_{dte.folio}.pdf"
                                    print(f"[DTEBox PDF] PDF descargado exitosamente desde XML: {len(pdf_content)} bytes")
                                    
                                    return {
                                        'success': True,
                                        'pdf_content': pdf_content,
                                        'filename': filename
                                    }
                            except Exception as e:
                                print(f"[DTEBox PDF] Error al decodificar Data: {e}")
                        
                        # Si no hay Data o no es un PDF válido, buscar Description con error
                        description = root.find('.//{http://gdexpress.cl/api}Description')
                        if description is not None and description.text:
                            error_msg = description.text
                        else:
                            error_msg = response.text[:500]
                        
                        print(f"[DTEBox PDF] Error en respuesta XML: {error_msg}")
                        return {
                            'success': False,
                            'error': f"GDExpress: {error_msg}"
                        }
                    except Exception as e:
                        print(f"[DTEBox PDF] Error al parsear XML: {e}")
                        return {
                            'success': False,
                            'error': f"Error al procesar respuesta XML: {response.text[:300]}"
                        }
                
                elif 'application/json' in content_type:
                    # Respuesta JSON con PDF en base64
                    try:
                        data = response.json()
                        
                        # Buscar el PDF en diferentes posibles campos
                        pdf_base64 = data.get('Data') or data.get('data') or data.get('pdf') or data.get('PDF')
                        
                        if pdf_base64:
                            # Decodificar base64
                            import base64
                            pdf_content = base64.b64decode(pdf_base64)
                            
                            # Verificar que sea un PDF válido
                            if pdf_content.startswith(b'%PDF'):
                                filename = f"DTE_{dte.tipo_dte}_{dte.folio}.pdf"
                                print(f"[DTEBox PDF] PDF descargado exitosamente (JSON): {len(pdf_content)} bytes")
                                
                                return {
                                    'success': True,
                                    'pdf_content': pdf_content,
                                    'filename': filename
                                }
                            else:
                                return {
                                    'success': False,
                                    'error': "El contenido decodificado no es un PDF valido"
                                }
                        else:
                            # Puede ser un error en formato JSON
                            error_msg = data.get('Description') or data.get('message') or str(data)
                            print(f"[DTEBox PDF] Error en respuesta JSON: {error_msg}")
                            return {
                                'success': False,
                                'error': f"Error de DTEBox: {error_msg}"
                            }
                    except Exception as e:
                        print(f"[DTEBox PDF] Error al parsear JSON: {e}")
                        return {
                            'success': False,
                            'error': f"Error al procesar respuesta: {str(e)}"
                        }
                
                elif 'pdf' in content_type.lower() or response.content.startswith(b'%PDF'):
                    # Respuesta directa con bytes del PDF
                    filename = f"DTE_{dte.tipo_dte}_{dte.folio}.pdf"
                    print(f"[DTEBox PDF] PDF descargado exitosamente (bytes): {len(response.content)} bytes")
                    
                    return {
                        'success': True,
                        'pdf_content': response.content,
                        'filename': filename
                    }
                else:
                    # Contenido desconocido
                    print(f"[DTEBox PDF] Tipo de contenido desconocido: {content_type}")
                    print(f"[DTEBox PDF] Primeros 200 bytes: {response.content[:200]}")
                    return {
                        'success': False,
                        'error': f"Respuesta inesperada del servidor (Content-Type: {content_type})"
                    }
            else:
                error_text = response.text[:500]
                print(f"[DTEBox PDF] Error HTTP {response.status_code}: {error_text}")
                return {
                    'success': False,
                    'error': f"Error HTTP {response.status_code}: {error_text}"
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': "Tiempo de espera agotado al conectar con GDExpress"
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': "No se pudo conectar con el servidor GDExpress"
            }
        except Exception as e:
            print(f"[DTEBox PDF] Error inesperado: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': f"Error al descargar PDF: {str(e)}"
            }
