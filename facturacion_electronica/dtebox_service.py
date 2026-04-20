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
        
        # 1. Normalización de URL Base
        # Soportamos: 'ip', 'http://ip', 'http://ip/api/Core.svc', 'http://ip/api/core.svc/'
        url_input = empresa.dtebox_url.strip().rstrip('/')
        if not url_input.startswith('http'):
            url_input = f"http://{url_input}"
            
        # Extraer el host base eliminando cualquier rastro de la ruta del servicio
        host_base = re.split(r'/api/core\.svc', url_input, flags=re.IGNORECASE)[0].rstrip('/')
        
        # URL oficial del servicio Core.svc (punto de entrada único)
        self.url_service = f"{host_base}/api/Core.svc"
        
        # Prefijo para métodos core (SendDocument, RecoverPDF, RecoverXML, etc.)
        self.url_core = f"{self.url_service}/core"
        self.url_envio = f"{self.url_core}/SendDocumentAsXML"
        
        # 2. Credenciales y Ambiente
        self.auth_key = empresa.dtebox_auth_key or empresa.api_key or ''
        # GDExpress usa 'T' para Homologación (Test) y 'P' para Producción, siempre en Mayúsculas.
        self.ambiente = (empresa.dtebox_ambiente or 'T').upper()
        
        print(f"[DTEBox] Blindaje Inicial: Service={self.url_service}, Ambiente={self.ambiente}")

    def _get_ruts_variations(self):
        """Genera las variaciones de RUT que GDExpress suele requerir."""
        rut_raw = self.empresa.rut.replace('.', '').upper()
        return [
            rut_raw,                    # Ejemplo: 76129486-5
            rut_raw.replace('-', '')    # Ejemplo: 761294865
        ]

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

            # 3. Firmas: remover para todos los tipos (DTEBox firma el documento)
            ns_dsig = "http://www.w3.org/2000/09/xmldsig#"
            for sig in list(root.findall(f'.//{{{ns_dsig}}}Signature')):
                safe_remove(sig)
            for sig in list(root.findall('.//Signature')):
                safe_remove(sig)

            # 4. TED: remover para todos los tipos (DTEBox genera el TED)
            for ted_elem in list(root.findall(f'.//{{{ns_sii}}}TED')):
                safe_remove(ted_elem)
            for ted_elem in list(root.findall('.//TED')):
                safe_remove(ted_elem)

            # 5. Remover TmstFirma si existe
            for tmst in list(root.findall(f'.//{{{ns_sii}}}TmstFirma')):
                safe_remove(tmst)
            for tmst in list(root.findall('.//TmstFirma')):
                safe_remove(tmst)

            # 6. Convertir a string SIN declaración XML (Content debe ser solo el DTE)
            xml_bytes_out = etree.tostring(root, encoding='ISO-8859-1', xml_declaration=True, method='xml')
            xml_clean = xml_bytes_out.decode('ISO-8859-1', errors='replace')

            # 7. Limpiezas finales (evitar minificación agresiva que pueda romper el parser)
            # xml_clean = re.sub(r'>\s+<', '><', xml_clean)
            xml_clean = xml_clean.strip()

            # 8. Sanitizar campos de guías (TipoDespacho/IndTraslado) para compatibilidad con DTEBox
            try:
                # Trabajar con árbol para modificar valores
                parser2 = etree.XMLParser(recover=True, encoding='ISO-8859-1')
                root2 = etree.fromstring(xml_clean.encode('ISO-8859-1'), parser=parser2)
                ns_sii = "http://www.sii.cl/SiiDte"
                
                # Sanitizar IdDoc para guías
                if str(tipo_dte) == '52':
                    iddoc = root2.find(f'.//{{{ns_sii}}}IdDoc') or root2.find('.//IdDoc')
                    if iddoc is not None:
                        # IndTraslado: evitar duplicidades (limpiar antes de procesar)
                        all_inds = iddoc.findall(f'.//{{{ns_sii}}}IndTraslado') + iddoc.findall('.//IndTraslado')
                        if all_inds:
                            # Quedarse con el primero y borrar el resto
                            ind = all_inds[0]
                            for extra in all_inds[1:]:
                                iddoc.remove(extra)
                            
                            val = (ind.text or '').strip()
                            if val not in {'1', '2', '3', '4', '5', '6', '7', '8', '9'}:
                                ind.text = "1"
                        else:
                            ind = etree.SubElement(iddoc, "IndTraslado")
                            ind.text = "1"
                        
                        # TipoDespacho: opcional, evitar duplicidades
                        all_tds = iddoc.findall(f'.//{{{ns_sii}}}TipoDespacho') + iddoc.findall('.//TipoDespacho')
                        if all_tds:
                            td = all_tds[0]
                            for extra in all_tds[1:]:
                                iddoc.remove(extra)
                            
                            val_td = (td.text or '').strip()
                            if val_td not in {'1', '2', '3'}:
                                td.text = "1"

                # Sanitizar Receptor: Asegurar GiroRecep (OBLIGATORIO para DTEBox)
                if str(tipo_dte) in ['33', '52', '56', '61']:
                    receptor = root2.find(f'.//{{{ns_sii}}}Receptor') or root2.find('.//Receptor')
                    if receptor is not None:
                        # GiroRecep: evitar duplicidades (OBLIGATORIO para DTEBox)
                        all_giros = receptor.findall(f'.//{{{ns_sii}}}GiroRecep') + receptor.findall('.//GiroRecep')
                        if all_giros:
                            # Quedarse con el primero y borrar el resto
                            giro_elem = all_giros[0]
                            for extra in all_giros[1:]:
                                receptor.remove(extra)
                            
                            if not (giro_elem.text or '').strip():
                                giro_elem.text = "PARTICULAR"
                        else:
                            # Agregar si no existe
                            # Intentar con namespace primero
                            rzn_soc = receptor.find(f'{{{ns_sii}}}RznSocRecep')
                            if rzn_soc is not None:
                                new_giro = etree.Element(f"{{{ns_sii}}}GiroRecep")
                                new_giro.text = "PARTICULAR"
                                rzn_soc.addnext(new_giro)
                            else:
                                # Si no hay namespace
                                rzn_soc = receptor.find('RznSocRecep')
                                if rzn_soc is not None:
                                    new_giro = etree.Element("GiroRecep")
                                    new_giro.text = "PARTICULAR"
                                    rzn_soc.addnext(new_giro)
                                else:
                                    # Fallback: al inicio del receptor
                                    new_giro = etree.Element(f"{{{ns_sii}}}GiroRecep")
                                    new_giro.text = "PARTICULAR"
                                    receptor.insert(0, new_giro)

                # Re-serializar después de cambios
                xml_clean = etree.tostring(root2, encoding='ISO-8859-1', xml_declaration=True, method='xml').decode('ISO-8859-1', errors='replace')
            except Exception as e:
                print(f"[DTEBox] Error en sanitización o re-inyección de TED: {e}")
                pass

            # 1. Asegurar Namespace SII y eliminar duplicados de raíz
            if 'xmlns="http://www.sii.cl/SiiDte"' not in xml_clean:
                xml_clean = re.sub(r'<DTE[^>]*>', '<DTE version="1.0" xmlns="http://www.sii.cl/SiiDte">', xml_clean)
            else:
                xml_clean = re.sub(r'<DTE[^>]*>', '<DTE version="1.0" xmlns="http://www.sii.cl/SiiDte">', xml_clean)

            # Parsear de nuevo para limpieza final de duplicados
            try:
                # Usar parser que ignore namespaces para limpieza fácil
                root3 = etree.fromstring(xml_clean.encode('ISO-8859-1', errors='replace'))
                ns_sii = "http://www.sii.cl/SiiDte"
                
                # Función para limpiar duplicados de cualquier tag
                def limpiar_duplicados(padre, tag_name):
                    if padre is None: return
                    encontrados = padre.findall(f'.//{{{ns_sii}}}{tag_name}') + padre.findall(f'.//{tag_name}')
                    if len(encontrados) > 1:
                        for extra in encontrados[1:]:
                            extra.getparent().remove(extra)

                # Limpiar IndTraslado en IdDoc
                iddoc = root3.find(f'.//{{{ns_sii}}}IdDoc') or root3.find('.//IdDoc')
                limpiar_duplicados(iddoc, 'IndTraslado')
                limpiar_duplicados(iddoc, 'TipoDespacho')
                
                # Limpiar GiroRecep en Receptor
                receptor = root3.find(f'.//{{{ns_sii}}}Receptor') or root3.find('.//Receptor')
                limpiar_duplicados(receptor, 'GiroRecep')
                
                # Re-serializar sin declaración XML para el Base64
                xml_para_b64_inner = etree.tostring(root3, encoding='ISO-8859-1', xml_declaration=False).decode('ISO-8859-1', errors='replace').strip()
                # Unir con declaración purista (sin saltos de línea, comillas dobles)
                xml_para_b64 = '<?xml version="1.0" encoding="ISO-8859-1"?>' + xml_para_b64_inner
                
                xml_b64 = base64.b64encode(xml_para_b64.encode('ISO-8859-1', errors='replace')).decode('utf-8')
            except Exception as e_clean:
                print(f"[DTEBox] Error en limpieza duplicados final: {e_clean}")

            return xml_para_b64, None

        except Exception as e:
            msg = str(e)
            print(f"[DTEBox] Error preparando XML: {e}")
            import traceback
            traceback.print_exc()
            return None, msg or "Error desconocido al preparar el XML"

    def timbrar_dte(self, xml_firmado, tipo_dte=None):
        """
        Envía el XML a DTEBox por POST REST con JSON.
        """
        try:
            if not tipo_dte:
                match = re.search(r'<TipoDTE>(\d+)</TipoDTE>', str(xml_firmado))
                tipo_dte = match.group(1) if match else '33'

            print(f"[DTEBox] Preparando envío REST Tipo {tipo_dte}")

            # 1. Preparar XML limpio
            xml_para_b64, error_preparar = self._limpiar_y_preparar_xml(xml_firmado, tipo_dte)
            if xml_para_b64 is None:
                return {'success': False, 'error': error_preparar}
            
            # 2. Codificar a Base64 - USAR XML EXACTO (CON DECLARACIÓN PURISTA SI EXISTE)
            xml_b64 = base64.b64encode(xml_para_b64.encode('ISO-8859-1', errors='replace')).decode('utf-8')
            
            # 3. Datos de resolución - SEGUIR INSTRUCCIÓN GDEXPRESS: 0 para Homologación
            res_num = 0 if self.ambiente == 'T' else int(self.empresa.resolucion_numero or 0)
            res_fch = self.empresa.resolucion_fecha.strftime('%Y-%m-%d') if self.empresa.resolucion_fecha else "2014-08-22"

            # 4. Construir Payload JSON (Estándar REST DTEBox)
            # NOTA: WCF es sensible a los tipos. Usamos INT para números.
            payload = {
                "Environment": self.ambiente,
                "Content": xml_b64,
                "ResolutionNumber": int(res_num),
                "ResolutionDate": res_fch,
                "PDF417Columns": 5,
                "PDF417Level": 2,
                "PDF417Type": 1,
                "TED": ""
            }

            headers = {
                'AuthKey': self.auth_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            print(f"[DTEBox] URL: {self.url_envio}")
            
            # Realizar petición POST con requests
            response = requests.post(
                self.url_envio, 
                json=payload, 
                headers=headers, 
                timeout=60
            )
            
            print(f"[DTEBox] Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    resp_data = response.json()
                    result_code = str(resp_data.get('Result', '1'))
                    
                    if result_code == '0':
                        return {
                            'success': True,
                            'estado': 'OK',
                            'ted': resp_data.get('TED'),
                            'track_id': 'DTEBOX-' + timezone.now().strftime('%Y%m%d%H%M%S'),
                            'xml_respuesta': response.text
                        }
                    else:
                        error_msg = resp_data.get('Description', 'Error en procesamiento DTEBox')
                        print(f"[DTEBox Error] Result: {result_code} | Msg: {error_msg}")
                        return {
                            'success': False, 
                            'error': f"{error_msg} (Código: {result_code})",
                            'detail': response.text
                        }
                except ValueError:
                    # Si no es JSON, podría ser una respuesta exitosa en otro formato
                    if 'TrackId' in response.text:
                         return {
                            'success': True,
                            'estado': 'OK',
                            'xml_respuesta': response.text
                        }
                    return {'success': False, 'error': f"Respuesta no válida: {response.text[:200]}"}
            else:
                # INTEGRACIÓN: Capturar el detalle del 500 para diagnóstico
                error_body = response.text[:1000]
                print(f"[DTEBox CRÍTICO] HTTP {response.status_code} | Body: {error_body}")
                return {
                    'success': False, 
                    'error': f"Error HTTP {response.status_code} en DTEBox", 
                    'detail': error_body
                }

        except Exception as e:
            print(f"[DTEBox] Excepción: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    def descargar_pdf(self, dte):
        """Descarga el PDF de un DTE desde GDExpress/DTEBox."""
        try:
            # Intentar primero RecoverPDF_V2 (más moderno) y luego RecoverPDF (legacy)
            endpoints = ['RecoverPDF_V2', 'RecoverPDF']
            ruts_probar = self._get_ruts_variations()
            
            for ep in endpoints:
                for rut_emisor in ruts_probar:
                    # Formato Documentación: [url_service]/core/[endpoint]/[Ambiente]/E/[RUT]/[TipoDTE]/[Folio]
                    url = f"{self.url_core}/{ep}/{self.ambiente}/E/{rut_emisor}/{dte.tipo_dte}/{dte.folio}"
                    
                    try:
                        headers = {
                            'AuthKey': self.auth_key, 
                            'Accept': 'application/json',
                            'Content-Type': 'application/json'
                        }
                        print(f"[DTEBox PDF] Solicitando: {ep} | RUT: {rut_emisor} | Folio: {dte.folio}")
                        resp = requests.get(url, headers=headers, timeout=25)
                        
                        if resp.status_code == 200:
                            content_type = resp.headers.get('Content-Type', '')
                            
                            # Caso 1: JSON con Data en Base64
                            if 'application/json' in content_type:
                                data = resp.json()
                                # 'Data' es el estándar de GDExpress para el contenido binario
                                pdf_b64 = data.get('Data') or data.get('pdf')
                                if pdf_b64:
                                    print(f"[DTEBox PDF] ¡Éxito! Recuperado vía JSON ({ep})")
                                    return {
                                        'success': True, 
                                        'pdf_content': base64.b64decode(pdf_b64), 
                                        'filename': f"DTE_{dte.tipo_dte}_{dte.folio}.pdf"
                                    }
                            
                            # Caso 2: Binario directo (%PDF)
                            elif resp.content.startswith(b'%PDF'):
                                print(f"[DTEBox PDF] ¡Éxito! Recuperado vía Stream Directo")
                                return {
                                    'success': True, 
                                    'pdf_content': resp.content, 
                                    'filename': f"DTE_{dte.tipo_dte}_{dte.folio}.pdf"
                                }
                        
                        print(f"[DTEBox PDF] Sin éxito con {ep}/{rut_emisor} (Status: {resp.status_code})")
                    except Exception as e_req:
                        print(f"[DTEBox PDF] Fallo de conexión en intento ({ep}): {str(e_req)}")
            
            return {'success': False, 'error': f'GDExpress no entregó el PDF para el Folio {dte.folio}. Verifique si el documento está procesado en su portal.'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def descargar_xml(self, dte):
        """Descarga el XML de un DTE desde GDExpress/DTEBox."""
        try:
            ruts_probar = self._get_ruts_variations()
            
            for rut_emisor in ruts_probar:
                # Formato Documentación: [url_service]/core/RecoverXML/[Ambiente]/E/[RUT]/[TipoDTE]/[Folio]
                url = f"{self.url_core}/RecoverXML/{self.ambiente}/E/{rut_emisor}/{dte.tipo_dte}/{dte.folio}"
                
                try:
                    headers = {
                        'AuthKey': self.auth_key, 
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    }
                    print(f"[DTEBox XML] Solicitando: RecoverXML | RUT: {rut_emisor} | Folio: {dte.folio}")
                    resp = requests.get(url, headers=headers, timeout=25)
                    
                    if resp.status_code == 200:
                        content_type = resp.headers.get('Content-Type', '')
                        
                        # Caso 1: JSON con Data en Base64
                        if 'application/json' in content_type:
                            data = resp.json()
                            xml_b64 = data.get('Data') or data.get('xml')
                            if xml_b64:
                                print(f"[DTEBox XML] ¡Éxito! Recuperado vía JSON")
                                return {
                                    'success': True, 
                                    'xml_content': base64.b64decode(xml_b64).decode('ISO-8859-1', errors='replace'), 
                                    'filename': f"DTE_{dte.tipo_dte}_{dte.folio}.xml"
                                }
                        
                        # Caso 2: XML directo
                        elif b'<DTE' in resp.content or b'<?xml' in resp.content:
                            print(f"[DTEBox XML] ¡Éxito! Recuperado vía Stream Directo")
                            return {
                                'success': True, 
                                'xml_content': resp.content.decode('ISO-8859-1', errors='replace'), 
                                'filename': f"DTE_{dte.tipo_dte}_{dte.folio}.xml"
                            }
                        
                        print(f"[DTEBox XML] Status 200 pero contenido no reconocido para RUT {rut_emisor}")
                    else:
                        print(f"[DTEBox XML] Sin éxito para RUT {rut_emisor} (Status: {resp.status_code})")
                except Exception as e_req:
                    print(f"[DTEBox XML] Fallo de conexión para RUT {rut_emisor}: {str(e_req)}")
            
            return {'success': False, 'error': f'No se pudo recuperar el XML oficial del folio {dte.folio} desde GDExpress.'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
