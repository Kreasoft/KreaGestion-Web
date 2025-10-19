"""
Cliente SOAP para webservices del SII
Envío y consulta de estado de DTE
"""
from zeep import Client
from zeep.transports import Transport
from requests import Session
from lxml import etree
import base64
from datetime import datetime


class ClienteSII:
    """Cliente para interactuar con los webservices del SII"""
    
    # URLs de los webservices del SII
    URLS = {
        'certificacion': {
            'envio': 'https://maullin.sii.cl/DTEWS/services/QueryEstDte?wsdl',
            'consulta': 'https://maullin.sii.cl/DTEWS/services/QueryEstDte?wsdl',
            'token': 'https://maullin.sii.cl/DTEWS/CrSeed.jws?WSDL',
        },
        'produccion': {
            'envio': 'https://palena.sii.cl/DTEWS/services/QueryEstDte?wsdl',
            'consulta': 'https://palena.sii.cl/DTEWS/services/QueryEstDte?wsdl',
            'token': 'https://palena.sii.cl/DTEWS/CrSeed.jws?WSDL',
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
        
        print(f"🌐 Cliente SII inicializado - Ambiente: {ambiente}")
    
    def obtener_semilla(self):
        """
        Obtiene la semilla (seed) del SII para autenticación
        
        Returns:
            str: Semilla obtenida
        """
        try:
            # Crear cliente SOAP para obtener semilla
            client = Client(self.urls['token'], transport=self.transport)
            
            # Llamar al método getSeed
            response = client.service.getSeed()
            
            # Parsear la respuesta XML
            root = etree.fromstring(response.encode('utf-8'))
            
            # Buscar el elemento SEMILLA
            semilla_elem = root.find('.//{http://www.sii.cl/XMLSchema}SEMILLA')
            if semilla_elem is None:
                semilla_elem = root.find('.//SEMILLA')
            
            if semilla_elem is None:
                raise ValueError("No se pudo obtener la semilla del SII")
            
            semilla = semilla_elem.text
            
            print(f"✅ Semilla obtenida: {semilla}")
            return semilla
            
        except Exception as e:
            print(f"❌ Error al obtener semilla: {str(e)}")
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
            # Crear XML de solicitud de token
            gettoken = etree.Element("getToken")
            item = etree.SubElement(gettoken, "item")
            semilla_elem = etree.SubElement(item, "Semilla")
            semilla_elem.text = semilla
            
            # Convertir a string
            gettoken_string = etree.tostring(
                gettoken,
                pretty_print=True,
                xml_declaration=True,
                encoding='ISO-8859-1'
            ).decode('ISO-8859-1')
            
            # Firmar la solicitud
            gettoken_firmado = firmador.firmar_xml(gettoken_string)
            
            # Crear cliente SOAP
            client = Client(self.urls['token'], transport=self.transport)
            
            # Enviar solicitud de token
            response = client.service.getToken(gettoken_firmado)
            
            # Parsear respuesta
            root = etree.fromstring(response.encode('utf-8'))
            
            # Buscar el token
            token_elem = root.find('.//{http://www.sii.cl/XMLSchema}TOKEN')
            if token_elem is None:
                token_elem = root.find('.//TOKEN')
            
            if token_elem is None:
                raise ValueError("No se pudo obtener el token del SII")
            
            token = token_elem.text
            
            print(f"✅ Token obtenido exitosamente")
            return token
            
        except Exception as e:
            print(f"❌ Error al obtener token: {str(e)}")
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
                print(f"✅ DTE enviado exitosamente - Track ID: {resultado['track_id']}")
            else:
                print(f"⚠️ Respuesta del SII sin Track ID")
            
            return resultado
            
        except Exception as e:
            print(f"❌ Error al enviar DTE: {str(e)}")
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
            
            print(f"✅ Estado consultado - Estado: {resultado['estado']}")
            
            return resultado
            
        except Exception as e:
            print(f"❌ Error al consultar estado: {str(e)}")
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
            
            print(f"✅ Estado documento consultado - Estado: {resultado['estado']}")
            
            return resultado
            
        except Exception as e:
            print(f"❌ Error al consultar estado documento: {str(e)}")
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
            
            print(f"✅ SetDTE creado con {len(dtes_firmados)} documento(s)")
            
            return set_dte_string
            
        except Exception as e:
            print(f"❌ Error al crear SetDTE: {str(e)}")
            raise
