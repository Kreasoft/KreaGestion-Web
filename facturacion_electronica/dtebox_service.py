"""
Servicio para integración con DTEBox (Timbraje Offline)
Refactorizado para seguir el estándar de KreaDTE-Cloud y GDExpress.
"""
import requests
import base64
import json
import os
import re
import urllib.request
import urllib.error
from django.utils import timezone
from django.conf import settings
from datetime import datetime
from lxml import etree

class DTEBoxService:
    """Servicio para comunicación con DTEBox API"""
    
    def __init__(self, empresa):
        self.empresa = empresa
        
        if not empresa.dtebox_habilitado:
            raise ValueError("DTEBox no está habilitado para esta empresa")
        
        if not empresa.dtebox_url:
            raise ValueError("DTEBox URL no está configurada")
        
        if not empresa.dtebox_auth_key:
            raise ValueError("DTEBox Auth Key no está configurada")
        
        # Normalizar URL base
        url_base = empresa.dtebox_url.strip().rstrip('/')
        if not url_base.startswith('http'):
            url_base = f"http://{url_base}"
            
        # Asegurar que termina en el endpoint correcto para envío (como en KreaDTE-Cloud)
        # Formato: /api/Core.svc/core (minúscula)
        if 'api/Core.svc/core' not in url_base:
            if url_base.endswith('/Core.svc/core'):
                pass
            elif url_base.endswith('/Core.svc'):
                url_base = f"{url_base}/core"
            else:
                url_base = f"{url_base}/api/Core.svc/core"
        
        self.url_base = url_base
        self.url_envio = f"{url_base}/SendDocumentAsXML"
        self.url_boleta = f"{url_base}/SendDocumentAsXML"
        
        self.auth_key = empresa.dtebox_auth_key
        self.ambiente = 'T'
        
        print(f"[DTEBox] Inicializado: {self.url_envio}, Ambiente: {self.ambiente}")

    def _limpiar_y_preparar_xml(self, xml_firmado, tipo_dte):
        """Prepara el XML del DTE para DTEBox (mismo criterio que KreaDTE-Cloud).
        Por POST se envía XML SIN firmar; DTEBox firma/timbra. Se quita declaración XML del Content.
        Acepta XML firmado o sin firmar: extrae el DTE, elimina firmas/TED si existen.
        Retorna (xml_clean, None) si ok, o (None, mensaje_error) si falla.
        """
        print(f"[DTEBox Debug] Preparando XML tipo {tipo_dte} (estilo KreaDTE-Cloud: POST sin firma)")
        try:
            from lxml import etree

            # 1. Validar que hay XML (guías a veces tienen xml_firmado vacío)
            if xml_firmado is None:
                return None, "El XML del documento está vacío o no fue generado. Regenera el XML de la guía desde el detalle del DTE."
            if isinstance(xml_firmado, str):
                xml_firmado = xml_firmado.strip()
                if not xml_firmado:
                    return None, "El XML del documento está vacío. Regenera el XML de la guía desde el detalle del DTE."
                xml_bytes = xml_firmado.encode('ISO-8859-1', errors='replace')
            else:
                xml_bytes = xml_firmado

            parser = etree.XMLParser(recover=True, encoding='ISO-8859-1')
            root = etree.fromstring(xml_bytes, parser=parser)

            # 2. Si es un EnvioDTE (wrapper completo), extraer el DTE interno
            ns_sii = "http://www.sii.cl/SiiDte"
            if root.tag is not None and 'EnvioDTE' in str(root.tag):
                dte_interno = root.find(f'.//{{{ns_sii}}}DTE')
                if dte_interno is None:
                    dte_interno = root.find('.//DTE')
                if dte_interno is not None:
                    root = dte_interno

            def safe_remove(elem):
                parent = elem.getparent()
                if parent is not None:
                    parent.remove(elem)

            # 3. Remover Firmas (DTEBox firma el documento)
            ns_dsig = "http://www.w3.org/2000/09/xmldsig#"
            for sig in list(root.findall(f'.//{{{ns_dsig}}}Signature')):
                safe_remove(sig)
            for sig in list(root.findall('.//Signature')):
                safe_remove(sig)

            # 4. Remover TED (DTEBox lo genera)
            for ted_elem in list(root.findall(f'.//{{{ns_sii}}}TED')):
                safe_remove(ted_elem)
            for ted_elem in list(root.findall('.//TED')):
                safe_remove(ted_elem)

            # 5. Remover TmstFirma si existe
            for tmst in list(root.findall(f'.//{{{ns_sii}}}TmstFirma')):
                safe_remove(tmst)
            for tmst in list(root.findall('.//TmstFirma')):
                safe_remove(tmst)

            # 6. Convertir a string (mantener declaración XML)
            xml_bytes_out = etree.tostring(root, encoding='ISO-8859-1', xml_declaration=True, method='xml')
            xml_clean = xml_bytes_out.decode('ISO-8859-1', errors='replace')

            # 7. Limpiezas finales (minificar espacios entre tags)
            xml_clean = re.sub(r'>\s+<', '><', xml_clean)
            xml_clean = xml_clean.strip()

            # 8. Sanitizar campos de guías (TipoDespacho/IndTraslado) para compatibilidad con DTEBox
            if str(tipo_dte) == '52':
                try:
                    # Trabajar con árbol para modificar valores
                    parser2 = etree.XMLParser(recover=True, encoding='ISO-8859-1')
                    root2 = etree.fromstring(xml_clean.encode('ISO-8859-1'), parser=parser2)
                    ns_sii = "http://www.sii.cl/SiiDte"
                    iddoc = root2.find(f'.//{{{ns_sii}}}IdDoc') or root2.find('.//IdDoc')
                    if iddoc is not None:
                        # IndTraslado: limitar a valores conocidos, default '1'
                        ind = iddoc.find(f'{{{ns_sii}}}IndTraslado') or iddoc.find('IndTraslado')
                        if ind is None:
                            ind = etree.SubElement(iddoc, "IndTraslado")
                            ind.text = "1"
                        else:
                            val = (ind.text or '').strip()
                            if val not in {'1', '2', '3', '4'}:
                                ind.text = "1"
                        # TipoDespacho: opcional, si presente limitar a {'1','2'}, default '1'
                        td = iddoc.find(f'{{{ns_sii}}}TipoDespacho') or iddoc.find('TipoDespacho')
                        if td is not None:
                            val_td = (td.text or '').strip()
                            if val_td not in {'1', '2'}:
                                td.text = "1"
                    # Re-serializar después de cambios
                    xml_clean = etree.tostring(root2, encoding='ISO-8859-1', xml_declaration=True, method='xml').decode('ISO-8859-1', errors='replace')
                    xml_clean = re.sub(r'>\s+<', '><', xml_clean).strip()
                except Exception:
                    pass

            if 'xmlns="http://www.sii.cl/SiiDte"' not in xml_clean:
                xml_clean = re.sub(r'<DTE[^>]*>', '<DTE version="1.0" xmlns="http://www.sii.cl/SiiDte">', xml_clean)

            # No agregar declaración XML: DTEBox la ignora en el Content base64 (KreaDTE-Cloud)

            return xml_clean, None

        except Exception as e:
            msg = str(e)
            print(f"[DTEBox] Error preparando XML: {e}")
            import traceback
            traceback.print_exc()
            return None, msg or "Error desconocido al preparar el XML"

    def timbrar_dte(self, xml_firmado, tipo_dte=None):
        """
        Envía el XML a DTEBox por POST para obtener el timbre (TED).
        Según instrucciones GDExpress: por POST se envía XML SIN firmar (xml_dte).
        Acepta también XML firmado; internamente se limpia antes de enviar.
        """
        try:
            # Determinar tipo si no viene
            import xml.etree.ElementTree as ET
            if not tipo_dte:
                match = re.search(r'<TipoDTE>(\d+)</TipoDTE>', str(xml_firmado))
                tipo_dte = match.group(1) if match else '33'

            print(f"[DTEBox Debug] Preparando envío Tipo {tipo_dte} vía XML Protocol")

            # 1. Preparar XML base (DTE completo limpio)
            xml_preparado, error_preparar = self._limpiar_y_preparar_xml(xml_firmado, tipo_dte)
            if xml_preparado is None:
                return {'success': False, 'error': error_preparar or 'Error al preparar XML para envío'}
            
            # 2. Codificar a Base64 (Mandatorio ISO-8859-1)
            xml_b64 = base64.b64encode(xml_preparado.encode('ISO-8859-1', errors='replace')).decode('utf-8')
            
            # 2.1. Priorizar envío "solo Documento" para guías 52 en certificación
            content_b64 = xml_b64
            try:
                if str(tipo_dte) == '52':
                    from lxml import etree as LET
                    root_parsed = LET.fromstring(xml_preparado.encode('ISO-8859-1'))
                    ns_sii = "http://www.sii.cl/SiiDte"
                    doc_elem = root_parsed.find(f'.//{{{ns_sii}}}Documento') or root_parsed.find('.//Documento')
                    if doc_elem is not None:
                        doc_xml = LET.tostring(doc_elem, encoding='ISO-8859-1', xml_declaration=True)
                        content_b64 = base64.b64encode(doc_xml).decode('ascii')
            except Exception:
                pass
            
            # 3. Construir datos comunes
            # En certificación, algunos boxes aceptan ResolutionNumber=0 explícito
            res_num = 0 if (self.ambiente or 'T') == 'T' else (self.empresa.resolucion_numero or 0)
            res_fch = self.empresa.resolucion_fecha.strftime('%Y-%m-%d') if self.empresa.resolucion_fecha else "2014-08-22"
                        
            # 4. Enviar Request usando POST JSON (primario, como KreaDTE-Cloud)
            url_final = self.url_envio
            
            payload = {
                "Environment": self.ambiente,
                "Content": content_b64,
                "ResolutionDate": res_fch,
                "ResolutionNumber": int(res_num),
                "PDF417Columns": 0,
                "PDF417Level": 0,
                "PDF417Type": 0,
                "TED": ""
            }
            headers = {
                'AuthKey': self.auth_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            print(f"[DTEBox] Enviando a {url_final} (POST JSON)")
            print(f"[DTEBox DEBUG] Payload JSON: {json.dumps(payload)[:200]}...")
            req = urllib.request.Request(url_final, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
            
            try:
                with urllib.request.urlopen(req, timeout=45) as response:
                    resp_raw = response.read().decode('utf-8')
                    resp_data = json.loads(resp_raw)
                    print(f"[DTEBox] Respuesta Recibida: {json.dumps(resp_data)[:200]}...")
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8', errors='ignore')
                print(f"[DTEBox] ERROR HTTP {e.code} BODY: {error_body}")
                
                # Reintentar si es error 500 (como en KreaDTE-Cloud)
                if e.code == 500:
                    print(f"[DTEBox] Error HTTP 500, reintentando en 2 segundos...")
                    import time
                    time.sleep(2)
                    try:
                        with urllib.request.urlopen(req, timeout=45) as response:
                            resp_raw = response.read().decode('utf-8')
                            resp_data = json.loads(resp_raw)
                            print(f"[DTEBox] Reintento exitoso!")
                    except Exception as retry_err:
                        print(f"[DTEBox] Reintento también falló: {retry_err}")
                        # Fallback: Intentar envío en formato XML (algunos boxes lo requieren)
                        try:
                            # Construir XML request completo
                            xml_request = f'''<?xml version="1.0" encoding="utf-8"?>
<SendDocumentAsXMLRequest xmlns="http://gdexpress.cl/api">
  <Environment>{self.ambiente}</Environment>
  <Content>{xml_b64}</Content>
  <ResolutionDate>{res_fch}</ResolutionDate>
  <ResolutionNumber>{int(res_num)}</ResolutionNumber>
  <PDF417Columns>0</PDF417Columns>
  <PDF417Level>0</PDF417Level>
  <PDF417Type>0</PDF417Type>
  <TED></TED>
</SendDocumentAsXMLRequest>'''.strip()
                            headers_xml = {
                                'AuthKey': self.auth_key,
                                'Content-Type': 'application/xml',
                                'Accept': 'application/xml'
                            }
                            req_xml = urllib.request.Request(url_final, data=xml_request.encode('utf-8'), headers=headers_xml, method='POST')
                            with urllib.request.urlopen(req_xml, timeout=45) as response2:
                                resp_raw2 = response2.read().decode('utf-8', errors='ignore')
                                # Intentar parsear JSON dentro de XML o valores conocidos
                                try:
                                    resp_data2 = json.loads(resp_raw2)
                                except:
                                    resp_data2 = {}
                                print(f"[DTEBox] Fallback XML exitoso!")
                                result_code = str(resp_data2.get('Result', '0'))
                                return {
                                    'success': True if result_code == '0' else False,
                                    'estado': 'OK' if result_code == '0' else 'ERROR',
                                    'ted': resp_data2.get('TED', ''),
                                    'track_id': 'DTEBOX-' + timezone.now().strftime('%Y%m%d%H%M%S'),
                                    'xml_respuesta': resp_raw2
                                }
                        except Exception as xml_err:
                            print(f"[DTEBox] Fallback XML falló: {xml_err}")
                        # EXTRAER SOLO <Documento> y reintentar nuevamente
                        try:
                            from lxml import etree as LET
                            root_parsed = LET.fromstring(xml_preparado.encode('ISO-8859-1'))
                            ns_sii = "http://www.sii.cl/SiiDte"
                            doc_elem = root_parsed.find(f'.//{{{ns_sii}}}Documento') or root_parsed.find('.//Documento')
                            if doc_elem is None:
                                raise Exception("No se encontró nodo Documento para fallback")
                            doc_xml = LET.tostring(doc_elem, encoding='ISO-8859-1')
                            doc_b64 = base64.b64encode(doc_xml).decode('ascii')
                            xml_request_fb = f'''<?xml version="1.0" encoding="utf-8"?>
<SendDocumentAsXMLRequest xmlns="http://gdexpress.cl/api">
  <Environment>{self.ambiente}</Environment>
  <Content>{doc_b64}</Content>
  <ResolutionDate>{res_fch}</ResolutionDate>
  <ResolutionNumber>{int(res_num)}</ResolutionNumber>
  <PDF417Columns>0</PDF417Columns>
  <PDF417Level>0</PDF417Level>
  <PDF417Type>0</PDF417Type>
  <TED></TED>
</SendDocumentAsXMLRequest>'''.strip()
                            headers_xml2 = {
                                'AuthKey': self.auth_key,
                                'Content-Type': 'application/xml',
                                'Accept': 'application/xml'
                            }
                            req_xml2 = urllib.request.Request(url_final, data=xml_request_fb.encode('utf-8'), headers=headers_xml2, method='POST')
                            with urllib.request.urlopen(req_xml2, timeout=45) as response3:
                                resp_raw3 = response3.read().decode('utf-8', errors='ignore')
                                return {'success': True, 'estado': 'RECIBIDO', 'xml_respuesta': resp_raw3}
                        except Exception as xml_err2:
                            print(f"[DTEBox] Fallback Documento falló: {xml_err2}")
                        # Parsear motivo del SOAP Fault para mensaje claro
                        try:
                            reason_match = re.search(r'<Reason>.*?<Text[^>]*>(.*?)</Text>', error_body, flags=re.S)
                            subcode_match = re.search(r'<Subcode>.*?<Value[^>]*>(.*?)</Value>', error_body, flags=re.S)
                            reason_text = reason_match.group(1).strip() if reason_match else ''
                            subcode_text = subcode_match.group(1).strip() if subcode_match else ''
                            mensaje = "Error HTTP 500 en DTEBox"
                            if subcode_text:
                                mensaje += f" ({subcode_text})"
                            if reason_text:
                                mensaje += f": {reason_text}"
                            else:
                                mensaje += ": InternalServerError"
                            # Sugerencias comunes
                            sugerencias = (
                                "Verifique: AuthKey, URL del servicio, Environment (T/P), "
                                "Resolución SII (fecha/número), CAF cargado en DTEBox y estructura del XML (TipoDespacho/IndTraslado)."
                            )
                            return {'success': False, 'error': mensaje, 'detail': error_body[:1000], 'hints': sugerencias}
                        except Exception:
                            return {'success': False, 'error': f'Error HTTP 500: {error_body[:500]}'}
                else:
                    return {'success': False, 'error': f'HTTP {e.code}: {error_body}'}
            except Exception as e:
                return {'success': False, 'error': f'Error conex: {str(e)}'}

            # Procesar Respuesta (intentar JSON primero)
            try:
                result_code = str(resp_data.get('Result', '1'))
                if result_code == '0':
                    return {
                        'success': True,
                        'estado': 'OK',
                        'ted': resp_data.get('TED'),
                        'track_id': 'DTEBOX-' + timezone.now().strftime('%Y%m%d%H%M%S'),
                        'xml_respuesta': json.dumps(resp_data)
                    }
                else:
                    desc = resp_data.get('Description', 'Error desconocido')
                    return {'success': False, 'error': desc, 'detail': json.dumps(resp_data)[:1000]}
            except Exception:
                # Si no hay JSON, devolver cuerpo crudo para inspección
                return {'success': True, 'estado': 'RECIBIDO', 'xml_respuesta': resp_raw}

        except Exception as e:
            print(f"[DTEBox] Excepción crítica: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    def descargar_pdf(self, dte):
        """
        Descarga el PDF de un DTE desde GDExpress/DTEBox
        """
        try:
            # Endpoints posibles
            endpoints = ['RecoverPDF_V2', 'RecoverPDF']
            # GDExpress prefiere RUT con guion para PDF
            rut_emisor = self.empresa.rut.replace('.', '')
            
            for ep in endpoints:
                url = f"{self.url_base}/{ep}/{self.ambiente}/E/{rut_emisor}/{dte.tipo_dte}/{dte.folio}"
                print(f"[DTEBox PDF] Intentando endpoint: {ep}")
                
                try:
                    headers = {'AuthKey': self.auth_key, 'Accept': 'application/json'}
                    resp = requests.get(url, headers=headers, timeout=20)
                    
                    if resp.status_code == 200:
                        content_type = resp.headers.get('Content-Type', '')
                        
                        if 'application/json' in content_type:
                            data = resp.json()
                            pdf_b64 = data.get('Data') or data.get('pdf')
                            if pdf_b64:
                                return {'success': True, 'pdf_content': base64.b64decode(pdf_b64), 'filename': f"{dte.tipo_dte}_{dte.folio}.pdf"}
                        
                        elif resp.content.startswith(b'%PDF'):
                            return {'success': True, 'pdf_content': resp.content, 'filename': f"{dte.tipo_dte}_{dte.folio}.pdf"}
                except Exception as e:
                    print(f"[DTEBox PDF] Error con {ep}: {e}")
            
            return {'success': False, 'error': 'No se pudo recuperar el PDF'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
