"""
Cliente SOAP para webservices del SII
Envío y consulta de estado de DTE
"""
from zeep import Client
from zeep.transports import Transport
from requests import Session
import requests
from lxml import etree
import base64
from datetime import datetime


class ClienteSII:
    """Cliente para interactuar con los webservices del SII"""
    
    # URLs de los webservices del SII
    URLS = {
        'certificacion': {
            'seed': 'https://maullin.sii.cl/DTEWS/CrSeed.jws?WSDL',
            'token': 'https://maullin.sii.cl/DTEWS/GetTokenFromSeed.jws?WSDL',
            'envio': 'https://maullin.sii.cl/cgi_dte/UPL/DTEUpload',
            'consulta': 'https://maullin.sii.cl/DTEWS/services/QueryEstDte?wsdl',
        },
        'produccion': {
            'seed': 'https://palena.sii.cl/DTEWS/CrSeed.jws?WSDL',
            'token': 'https://palena.sii.cl/DTEWS/GetTokenFromSeed.jws?WSDL',
            'envio': 'https://palena.sii.cl/cgi_dte/UPL/DTEUpload',
            'consulta': 'https://palena.sii.cl/DTEWS/services/QueryEstDte?wsdl',
        }
    }
    
    def __init__(self, ambiente='certificacion'):
        """
        Inicializa el cliente SII
        
        Args:
            ambiente: 'certificacion' o 'produccion'
        """
        self.ambiente = ambiente
        self.urls = self.URLS[ambiente]
        
        # Configurar sesión HTTP
        self.session = Session()
        self.session.verify = True  # Verificar certificados SSL
        
        # Configurar transporte
        self.transport = Transport(session=self.session, timeout=30)
        
        print(f"Cliente SII inicializado - Ambiente: {ambiente}")
    
    def obtener_semilla(self):
        """
        Obtiene la semilla (seed) del SII para autenticación usando requests directo
        
        Returns:
            str: Semilla obtenida
        """
        import requests
        import html
        
        try:
            print(f"Obteniendo semilla del SII...")
            
            # URL sin ?WSDL para el servicio
            url = self.urls['seed'].replace('?WSDL', '')
            
            # SOAP envelope
            soap_request = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                  xmlns:def="http://DefaultNamespace">
   <soapenv:Header/>
   <soapenv:Body>
      <def:getSeed/>
   </soapenv:Body>
</soapenv:Envelope>"""
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': '',
            }
            
            # Enviar petición
            response = requests.post(
                url,
                data=soap_request.encode('utf-8'),
                headers=headers,
                timeout=30,
                verify=True
            )
            
            if response.status_code != 200:
                raise ValueError(f"Error HTTP {response.status_code}: {response.text[:200]}")
            
            # Parsear respuesta SOAP
            root = etree.fromstring(response.content)
            
            # Buscar getSeedReturn (el XML está escapado dentro)
            seed_return = root.find('.//{http://DefaultNamespace}getSeedReturn')
            if seed_return is None:
                seed_return = root.find('.//getSeedReturn')
            
            if seed_return is None or seed_return.text is None:
                raise ValueError("No se encontró getSeedReturn en la respuesta")
            
            # Decodificar el XML escapado
            xml_escapado = seed_return.text
            xml_decodificado = html.unescape(xml_escapado)
            
            # Parsear el XML interno
            root_interno = etree.fromstring(xml_decodificado.encode('utf-8'))
            
            # Buscar SEMILLA
            semilla_elem = root_interno.find('.//{http://www.sii.cl/XMLSchema}SEMILLA')
            if semilla_elem is None:
                semilla_elem = root_interno.find('.//SEMILLA')
            
            if semilla_elem is None or semilla_elem.text is None:
                raise ValueError("No se encontró SEMILLA en la respuesta interna")
            
            semilla = semilla_elem.text
            
            print(f"Semilla obtenida: {semilla}")
            return semilla
            
        except Exception as e:
            print(f"ERROR al obtener semilla: {str(e)}")
            raise
    
    def obtener_token(self, semilla, firmador):
        """
        Obtiene el token de autenticación del SII
        
        Args:
            semilla: Semilla obtenida del SII
            firmador: Instancia de FirmadorDTE
            
        Returns:
            str: Token de autenticación
        """
        try:
            print(f"Obteniendo token de autenticación...")
            
            # Crear XML SIMPLE de solicitud de token (sin namespaces complejos)
            # Según ejemplo real del SII: <getToken><item><Semilla>XXX</Semilla></item></getToken>
            gettoken = etree.Element("getToken")
            item = etree.SubElement(gettoken, "item")
            semilla_elem = etree.SubElement(item, "Semilla")
            semilla_elem.text = semilla
            
            # Convertir a string
            gettoken_string = etree.tostring(
                gettoken,
                pretty_print=False,  # Sin formato para que quede compacto
                xml_declaration=False,  # Sin declaración XML
                encoding='unicode'
            )
            
            # Firmar la solicitud (usando método específico para tokens)
            gettoken_firmado = firmador.firmar_token_request(gettoken_string)
            
            # DEBUG: Guardar el XML firmado para análisis
            with open('gettoken_firmado_simple.xml', 'w', encoding='utf-8') as f:
                f.write(gettoken_firmado)
            print(f"   XML firmado guardado en: gettoken_firmado_simple.xml")
            
            # El SII espera el XML firmado como string escapado
            import html
            gettoken_escapado = html.escape(gettoken_firmado)
            
            # URL sin ?WSDL
            url = self.urls['token'].replace('?WSDL', '')
            
            # SOAP envelope con el XML firmado escapado como string
            soap_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                  xmlns:def="http://DefaultNamespace">
   <soapenv:Header/>
   <soapenv:Body>
      <def:getToken>{gettoken_escapado}</def:getToken>
   </soapenv:Body>
</soapenv:Envelope>"""
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': '',
            }
            
            # Enviar petición
            response = requests.post(
                url,
                data=soap_request.encode('utf-8'),
                headers=headers,
                timeout=30,
                verify=True
            )
            
            if response.status_code != 200:
                print(f"\n   ERROR HTTP {response.status_code} al obtener token")
                print(f"   Respuesta completa del SII:")
                print(response.text[:1500])
                raise ValueError(f"Error HTTP {response.status_code}")
            
            # Parsear respuesta SOAP
            root = etree.fromstring(response.content)
            
            # Buscar getTokenReturn (el XML está escapado dentro)
            token_return = root.find('.//{http://DefaultNamespace}getTokenReturn')
            if token_return is None:
                token_return = root.find('.//getTokenReturn')
            
            if token_return is None or token_return.text is None:
                raise ValueError("No se encontró getTokenReturn en la respuesta")
            
            # Decodificar el XML escapado
            import html
            xml_escapado = token_return.text
            xml_decodificado = html.unescape(xml_escapado)
            
            # Parsear el XML interno
            root_interno = etree.fromstring(xml_decodificado.encode('utf-8'))
            
            # Buscar TOKEN
            token_elem = root_interno.find('.//{http://www.sii.cl/XMLSchema}TOKEN')
            if token_elem is None:
                token_elem = root_interno.find('.//TOKEN')
            
            if token_elem is None or token_elem.text is None:
                raise ValueError("No se encontró TOKEN en la respuesta interna")
            
            token = token_elem.text
            
            print(f"Token obtenido exitosamente")
            return token
            
        except Exception as e:
            print(f"ERROR al obtener token: {str(e)}")
            raise
    
    def enviar_dte(self, xml_envio, token, rut_emisor, rut_envia):
        """
        Envía un DTE al SII
        
        Args:
            xml_envio: XML del SetDTE (puede contener múltiples DTE)
            token: Token de autenticación
            rut_emisor: RUT del emisor
            rut_envia: RUT de quien envía
            
        Returns:
            dict: Respuesta del SII con track_id
        """
        try:
            # Codificar el XML en base64
            xml_bytes = xml_envio.encode('ISO-8859-1')
            xml_base64 = base64.b64encode(xml_bytes).decode('ascii')
            
            # Crear cliente SOAP para envío
            client = Client(self.urls['envio'], transport=self.transport)
            
            # Enviar el DTE
            response = client.service.enviarDTE(
                rutSender=rut_envia,
                dvSender=self._obtener_dv(rut_envia),
                rutCompany=rut_emisor,
                dvCompany=self._obtener_dv(rut_emisor),
                archivo=xml_base64,
                token=token
            )
            
            # Parsear respuesta
            root = etree.fromstring(response.encode('utf-8'))
            
            # Extraer track_id
            track_id_elem = root.find('.//TRACKID')
            estado_elem = root.find('.//ESTADO')
            
            resultado = {
                'track_id': track_id_elem.text if track_id_elem is not None else None,
                'estado': estado_elem.text if estado_elem is not None else None,
                'respuesta_completa': response
            }
            
            if resultado['track_id']:
                print(f"DTE enviado exitosamente - Track ID: {resultado['track_id']}")
            else:
                print(f"ADVERTENCIA: Respuesta del SII sin Track ID")
            
            return resultado
            
        except Exception as e:
            print(f"ERROR al enviar DTE: {str(e)}")
            raise
    
    def consultar_estado_dte(self, track_id, token, rut_emisor):
        """
        Consulta el estado de un DTE enviado
        
        Args:
            track_id: ID de seguimiento del envío
            token: Token de autenticación
            rut_emisor: RUT del emisor
            
        Returns:
            dict: Estado del DTE
        """
        try:
            # Crear cliente SOAP
            client = Client(self.urls['consulta'], transport=self.transport)
            
            # Consultar estado
            response = client.service.getEstDte(
                token=token,
                trackId=track_id
            )
            
            # Parsear respuesta
            root = etree.fromstring(response.encode('utf-8'))
            
            # Extraer información
            estado_elem = root.find('.//ESTADO')
            glosa_elem = root.find('.//GLOSA_ESTADO')
            num_atencion_elem = root.find('.//NUM_ATENCION')
            
            resultado = {
                'estado': estado_elem.text if estado_elem is not None else None,
                'glosa': glosa_elem.text if glosa_elem is not None else None,
                'num_atencion': num_atencion_elem.text if num_atencion_elem is not None else None,
                'respuesta_completa': response
            }
            
            print(f"Estado consultado - Estado: {resultado['estado']}")
            
            return resultado
            
        except Exception as e:
            print(f"ERROR al consultar estado: {str(e)}")
            raise
    
    def consultar_estado_documento(self, rut_emisor, tipo_dte, folio, fecha_emision, 
                                   monto_total, rut_receptor, token):
        """
        Consulta el estado de un documento específico en el SII
        
        Args:
            rut_emisor: RUT del emisor
            tipo_dte: Tipo de DTE
            folio: Folio del documento
            fecha_emision: Fecha de emisión (YYYY-MM-DD)
            monto_total: Monto total del documento
            rut_receptor: RUT del receptor
            token: Token de autenticación
            
        Returns:
            dict: Estado del documento
        """
        try:
            # Crear cliente SOAP
            client = Client(self.urls['consulta'], transport=self.transport)
            
            # Consultar estado del documento
            response = client.service.getEstDte(
                token=token,
                rutEmisor=rut_emisor,
                dvEmisor=self._obtener_dv(rut_emisor),
                tipoDte=tipo_dte,
                folioDte=folio,
                fechaEmisionDte=fecha_emision,
                montoTotal=int(monto_total),
                rutReceptor=rut_receptor,
                dvReceptor=self._obtener_dv(rut_receptor)
            )
            
            # Parsear respuesta
            root = etree.fromstring(response.encode('utf-8'))
            
            estado_elem = root.find('.//ESTADO')
            glosa_elem = root.find('.//GLOSA')
            
            resultado = {
                'estado': estado_elem.text if estado_elem is not None else None,
                'glosa': glosa_elem.text if glosa_elem is not None else None,
                'respuesta_completa': response
            }
            
            print(f"Estado documento consultado - Estado: {resultado['estado']}")
            
            return resultado
            
        except Exception as e:
            print(f"ERROR al consultar estado documento: {str(e)}")
            raise
    
    def _obtener_dv(self, rut):
        """
        Obtiene el dígito verificador de un RUT
        
        Args:
            rut: RUT con o sin formato (ej: "12345678-9" o "12345678")
            
        Returns:
            str: Dígito verificador
        """
        # Limpiar el RUT
        rut_limpio = rut.replace('.', '').replace('-', '')
        
        # Si ya tiene el DV, extraerlo
        if len(rut_limpio) > 8:
            return rut_limpio[-1]
        
        # Calcular el DV
        rut_numerico = rut_limpio[:-1] if not rut_limpio.isdigit() else rut_limpio
        
        suma = 0
        multiplo = 2
        
        for digito in reversed(rut_numerico):
            suma += int(digito) * multiplo
            multiplo = multiplo + 1 if multiplo < 7 else 2
        
        resto = suma % 11
        dv = 11 - resto
        
        if dv == 11:
            return '0'
        elif dv == 10:
            return 'K'
        else:
            return str(dv)
    
    def crear_set_dte(self, dtes_firmados, caratula):
        """
        Crea un SetDTE (conjunto de DTEs) para envío masivo
        
        Args:
            dtes_firmados: Lista de XML de DTEs firmados
            caratula: Diccionario con datos de la carátula
            
        Returns:
            str: XML del SetDTE
        """
        try:
            # Crear el EnvioDTE
            envio_dte = etree.Element(
                "EnvioDTE",
                version="1.0",
                nsmap={None: "http://www.sii.cl/SiiDte"}
            )
            
            # Crear SetDTE
            set_dte = etree.SubElement(envio_dte, "SetDTE", ID="SetDoc")
            
            # Carátula
            caratula_elem = etree.SubElement(set_dte, "Caratula", version="1.0")
            
            etree.SubElement(caratula_elem, "RutEmisor").text = caratula['rut_emisor']
            etree.SubElement(caratula_elem, "RutEnvia").text = caratula['rut_envia']
            etree.SubElement(caratula_elem, "RutReceptor").text = caratula.get('rut_receptor', '60803000-K')  # SII
            etree.SubElement(caratula_elem, "FchResol").text = caratula['fecha_resolucion']
            etree.SubElement(caratula_elem, "NroResol").text = str(caratula['numero_resolucion'])
            etree.SubElement(caratula_elem, "TmstFirmaEnv").text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            
            # Agregar DTEs al Set
            for dte_xml in dtes_firmados:
                dte_root = etree.fromstring(dte_xml.encode('ISO-8859-1'))
                set_dte.append(dte_root)
            
            # Convertir a string
            set_dte_string = etree.tostring(
                envio_dte,
                pretty_print=True,
                xml_declaration=True,
                encoding='ISO-8859-1'
            ).decode('ISO-8859-1')
            
            print(f"SetDTE creado con {len(dtes_firmados)} documento(s)")
            
            return set_dte_string
            
        except Exception as e:
            print(f"ERROR al crear SetDTE: {str(e)}")
            raise
