"""Cliente oficial del Registro de Aceptación o Reclamo de DTE del SII."""
from html import escape
from lxml import etree

from .cliente_sii import ClienteSII, _split_rut


class RegistroReclamoSII:
    NS = 'http://ws.registroreclamodte.diii.sdi.sii.cl'
    ENDPOINTS = {
        'CERTIFICACION': 'https://ws2.sii.cl/WSREGISTRORECLAMODTECERT/registroreclamodteservice',
        'PRODUCCION': 'https://ws1.sii.cl/WSREGISTRORECLAMODTE/registroreclamodteservice',
    }
    ACCIONES = {'ACD', 'ERM', 'RCD', 'RFP', 'RFT'}

    def __init__(self, empresa):
        if not empresa.certificado_digital or not empresa.password_certificado:
            raise ValueError('La empresa debe tener certificado digital y contraseña configurados.')
        # Las facturas de esta bandeja provienen del RCV tributario real. Los
        # eventos de aceptación/reclamo deben registrarse en el mismo ambiente,
        # independientemente del ambiente configurado para emitir DTE propios.
        ambiente = 'PRODUCCION'
        self.endpoint = self.ENDPOINTS[ambiente]
        self.cliente = ClienteSII(ambiente, empresa.certificado_digital.path, empresa.password_certificado)
        # ClienteSII mantiene una caché global heredada. Para una decisión
        # tributaria multiempresa obtenemos siempre un token del certificado activo.
        ClienteSII._cached_token = None
        ClienteSII._token_timestamp = None
        self.token = self.cliente.get_token()

    def _llamar(self, metodo, rut_emisor, tipo_dte, folio, accion=None):
        numero, dv = _split_rut(rut_emisor)
        if tipo_dte not in {'33', '34', '43'}:
            raise ValueError('El Registro SII solo admite DTE tipos 33, 34 y 43.')
        if accion is not None and accion not in self.ACCIONES:
            raise ValueError('Acción de aceptación o reclamo no válida.')
        campos = (
            f'<rutEmisor>{escape(numero)}</rutEmisor><dvEmisor>{escape(dv)}</dvEmisor>'
            f'<tipoDoc>{escape(str(tipo_dte))}</tipoDoc><folio>{escape(str(folio))}</folio>'
            + (f'<accionDoc>{escape(accion)}</accionDoc>' if accion else '')
        )
        sobre = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
            f'xmlns:reg="{self.NS}"><soapenv:Body><reg:{metodo}>{campos}'
            f'</reg:{metodo}></soapenv:Body></soapenv:Envelope>'
        )
        respuesta = self.cliente.session.post(
            self.endpoint, data=sobre.encode('utf-8'), timeout=30,
            headers={'Content-Type': 'text/xml; charset=UTF-8', 'SOAPAction': '', 'Cookie': f'TOKEN={self.token}'},
        )
        respuesta.raise_for_status()
        raiz = etree.fromstring(respuesta.content, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        fault = raiz.xpath('//*[local-name()="Fault"]')
        if fault:
            texto = ' '.join(fault[0].itertext()).strip()
            raise RuntimeError(f'El SII rechazó la solicitud SOAP: {texto}')
        return raiz, respuesta.text

    @staticmethod
    def _texto(raiz, nombre):
        valores = raiz.xpath(f'//*[local-name()="{nombre}"]/text()')
        return str(valores[0]).strip() if valores else ''

    def registrar_evento(self, documento, accion):
        raiz, crudo = self._llamar('ingresarAceptacionReclamoDoc', documento.rut_emisor, documento.tipo_dte, documento.folio, accion)
        codigo = self._texto(raiz, 'codResp')
        return {'codigo': int(codigo) if codigo.lstrip('-').isdigit() else None, 'descripcion': self._texto(raiz, 'descResp'), 'respuesta': crudo}

    def consultar_fecha_recepcion(self, documento):
        raiz, crudo = self._llamar('consultarFechaRecepcionSii', documento.rut_emisor, documento.tipo_dte, documento.folio)
        return {'fecha': self._texto(raiz, 'return'), 'respuesta': crudo}

    def listar_eventos(self, documento):
        raiz, crudo = self._llamar('listarEventosHistDoc', documento.rut_emisor, documento.tipo_dte, documento.folio)
        eventos = []
        for nodo in raiz.xpath('//*[local-name()="listaEventosDoc"]'):
            def texto_hijo(campo):
                valores = nodo.xpath(f'.//*[local-name()="{campo}"]/text()')
                return str(valores[0]).strip() if valores else ''
            eventos.append({campo: texto_hijo(campo) for campo in ('codEvento', 'descEvento', 'rutResponsable', 'dvResponsable', 'fechaEvento')})
        return {'codigo': self._texto(raiz, 'codResp'), 'descripcion': self._texto(raiz, 'descResp'), 'eventos': eventos, 'respuesta': crudo}
