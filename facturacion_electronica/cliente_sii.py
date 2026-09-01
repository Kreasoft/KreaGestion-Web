import requests
import re
import json
import time
import random
import string
from contextlib import contextmanager
from datetime import datetime
from lxml import etree
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse
from urllib3.util.retry import Retry
from urllib3.util import connection as urllib3_connection
from .sii_crypto import load_pfx, sign_xml_sii


def _normalizar_rut(rut):
    rut_limpio = str(rut or '').strip().replace('.', '').replace(' ', '').upper()
    if '-' not in rut_limpio and len(rut_limpio) > 1:
        rut_limpio = f"{rut_limpio[:-1]}-{rut_limpio[-1]}"
    return rut_limpio


def _split_rut(rut):
    rut_limpio = _normalizar_rut(rut)
    if '-' not in rut_limpio:
        raise ValueError(f"RUT invalido para SII: {rut}")
    numero, dv = rut_limpio.split('-', 1)
    return numero, dv.upper()

class ClienteSII:
    """Cliente para interactuar directamente con el SII"""
    _cached_token = None
    _token_timestamp = None
    _dns_cache = {}
    
    def __init__(self, ambiente='CERTIFICACION', pfx_path=None, pfx_password=None):
        self.ambiente = ambiente.upper()
        
        self.ENDPOINTS = {
            'CERTIFICACION': {
                'seed': 'https://maullin.sii.cl/DTEWS/CrSeed.jws',
                'token': 'https://maullin.sii.cl/DTEWS/GetTokenFromSeed.jws',
                'upload': 'https://maullin.sii.cl/cgi_dte/UPL/DTEUpload',
                'query': 'https://maullin.sii.cl/DTEWS/QueryEstUp.jws'
            },
            'PRODUCCION': {
                'seed': 'https://palena.sii.cl/DTEWS/CrSeed.jws',
                'token': 'https://palena.sii.cl/DTEWS/GetTokenFromSeed.jws',
                'upload': 'https://palena.sii.cl/cgi_dte/UPL/DTEUpload',
                'query': 'https://palena.sii.cl/DTEWS/QueryEstUp.jws'
            }
        }
        self.BOLETA_ENDPOINTS = {
            'CERTIFICACION': {
                'seed': 'https://apicert.sii.cl/recursos/v1/boleta.electronica.semilla',
                'token': 'https://apicert.sii.cl/recursos/v1/boleta.electronica.token',
                'upload': 'https://pangal.sii.cl/recursos/v1/boleta.electronica.envio',
                'query': 'https://apicert.sii.cl/recursos/v1/boleta.electronica.envio'
            },
            'PRODUCCION': {
                'seed': 'https://api.sii.cl/recursos/v1/boleta.electronica.semilla',
                'token': 'https://api.sii.cl/recursos/v1/boleta.electronica.token',
                'upload': 'https://rahue.sii.cl/recursos/v1/boleta.electronica.envio',
                'query': 'https://api.sii.cl/recursos/v1/boleta.electronica.envio'
            }
        }
        self.urls = self.ENDPOINTS.get(self.ambiente, self.ENDPOINTS['CERTIFICACION'])
        self.boleta_urls = self.BOLETA_ENDPOINTS.get(self.ambiente, self.BOLETA_ENDPOINTS['CERTIFICACION'])
        self.pfx_path = pfx_path
        self.pfx_password = pfx_password
        self.token = None
        self.boleta_token = None
        
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    @staticmethod
    def _es_error_dns(exc):
        texto = str(exc or '').lower()
        return any(token in texto for token in [
            'nameresolutionerror',
            'failed to resolve',
            'getaddrinfo failed',
            'temporary failure in name resolution',
        ])

    @classmethod
    def _resolver_ip_publica(cls, hostname):
        hostname = str(hostname or '').strip().lower()
        if not hostname:
            return None

        if hostname in cls._dns_cache:
            return cls._dns_cache[hostname]

        proveedores = [
            ('https://dns.google/resolve', {'name': hostname, 'type': 'A'}, {}),
            (
                'https://cloudflare-dns.com/dns-query',
                {'name': hostname, 'type': 'A'},
                {'Accept': 'application/dns-json'}
            ),
        ]

        for url, params, headers in proveedores:
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=10)
                resp.raise_for_status()
                payload = resp.json()
                for answer in payload.get('Answer', []):
                    if answer.get('type') == 1 and answer.get('data'):
                        cls._dns_cache[hostname] = answer['data']
                        return answer['data']
            except Exception:
                continue

        return None

    @contextmanager
    def _forzar_resolucion_dns(self, hostname, ip):
        original_create_connection = urllib3_connection.create_connection

        def custom_create_connection(address, *args, **kwargs):
            host, port = address
            if str(host).lower() == str(hostname).lower():
                return original_create_connection((ip, port), *args, **kwargs)
            return original_create_connection(address, *args, **kwargs)

        urllib3_connection.create_connection = custom_create_connection
        try:
            yield
        finally:
            urllib3_connection.create_connection = original_create_connection

    def _request_with_dns_fallback(self, method, url, **kwargs):
        try:
            return self.session.request(method, url, **kwargs)
        except requests.exceptions.RequestException as exc:
            if not self._es_error_dns(exc):
                raise

            hostname = urlparse(url).hostname
            ip = self._resolver_ip_publica(hostname)
            if not ip:
                raise

            with self._forzar_resolucion_dns(hostname, ip):
                return self.session.request(method, url, **kwargs)
    
    def _soap_call(self, url, body):
        envelope = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns:def="http://DefaultNamespace">'
            f'<soapenv:Body>{body}</soapenv:Body>'
            '</soapenv:Envelope>'
        )
        
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': ''
        }
        
        resp = self._request_with_dns_fallback('POST', url, data=envelope, headers=headers, timeout=25)
        resp.raise_for_status()
        return resp.text
    
    def _extract_cdata(self, xml_str):
        m = re.search(r'<!\[CDATA\[(.*?)\]\]>', xml_str, re.DOTALL)
        return m.group(1) if m else xml_str
        
    def _extract_tag(self, xml_str, tag):
        if not xml_str:
            return None
        patron = rf'<(?:\w+:)?{re.escape(tag)}(?:\s[^>]*)?>(.*?)</(?:\w+:)?{re.escape(tag)}>'
        m = re.search(patron, str(xml_str), re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else None

    def get_seed(self):
        body = '<def:getSeed soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"/>'
        resp_xml = self._soap_call(self.urls['seed'], body)
        inner = self._extract_tag(resp_xml, 'getSeedReturn') or self._extract_cdata(resp_xml)
        
        decoded = inner.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        semilla = self._extract_tag(decoded, 'SEMILLA')
        
        if not semilla:
            raise Exception("No se pudo obtener la semilla del SII")
        return semilla
        
    def get_token(self, semilla=None):
        if ClienteSII._cached_token and ClienteSII._token_timestamp:
            if time.time() - ClienteSII._token_timestamp > 7200:
                ClienteSII._cached_token = None
                ClienteSII._token_timestamp = None

        if ClienteSII._cached_token:
            self.token = ClienteSII._cached_token
            return self.token
            
        if not semilla:
            semilla = self.get_seed()
            
        if not self.pfx_path or not self.pfx_password:
            raise Exception("Se requiere certificado (.pfx) y contraseña para obtener el token")
            
        key_pem, cert_pem, priv_key = load_pfx(self.pfx_path, self.pfx_password)
        
        xml_semilla = f'<getToken><item><Semilla>{semilla}</Semilla></item></getToken>'
        xml_with_id = xml_semilla.replace('<getToken>', '<getToken ID="seed">')
        
        signed_xml = sign_xml_sii(xml_with_id, 'seed', key_pem, cert_pem, priv_key)
        
        clean_signed = re.sub(r'<\?xml[^>]*\?>', '', signed_xml).replace(' ID="seed"', '')
        
        body = (
            '<def:getToken soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
            f'<pszXml xsi:type="xsd:string"><![CDATA[<?xml version="1.0" ?>\n{clean_signed}]]></pszXml>'
            '</def:getToken>'
        )
        
        resp_xml = self._soap_call(self.urls['token'], body)
        inner = self._extract_tag(resp_xml, 'getTokenReturn') or self._extract_cdata(resp_xml)
        decoded = inner.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        
        token = self._extract_tag(decoded, 'TOKEN')
        if not token:
            raise Exception("No se pudo obtener el token del SII")
            
        self.token = token
        ClienteSII._cached_token = token
        ClienteSII._token_timestamp = time.time()
        return token

    def get_seed_boleta(self):
        headers = {
            'Accept': 'application/xml',
            'User-Agent': 'Mozilla/4.0 (compatible; PROG 1.0; Windows NT)'
        }
        resp = self.session.get(self.boleta_urls['seed'], headers=headers, timeout=15)
        resp.raise_for_status()
        semilla = self._extract_tag(resp.text, 'SEMILLA')
        if not semilla:
            raise Exception(f"No se pudo obtener semilla boleta SII: {resp.text[:300]}")
        return semilla

    def get_token_boleta(self, semilla=None):
        if not semilla:
            semilla = self.get_seed_boleta()

        if not self.pfx_path or not self.pfx_password:
            raise Exception("Se requiere certificado (.pfx) y contraseña para obtener token de boleta")

        key_pem, cert_pem, priv_key = load_pfx(self.pfx_path, self.pfx_password)
        xml_semilla = f'<getToken><item><Semilla>{semilla}</Semilla></item></getToken>'
        signed_xml = sign_xml_sii(xml_semilla, '', key_pem, cert_pem, priv_key)
        signed_xml = re.sub(r"^<\?xml\s+version='1\.0'\s+encoding='ISO-8859-1'\?>", '<?xml version="1.0" encoding="UTF-8"?>', signed_xml)

        headers = {
            'Accept': 'application/xml',
            'Content-Type': 'application/xml',
            'User-Agent': 'Mozilla/4.0 (compatible; PROG 1.0; Windows NT)'
        }
        resp = self._request_with_dns_fallback(
            'POST',
            self.boleta_urls['token'],
            data=signed_xml.encode('utf-8'),
            headers=headers,
            timeout=20
        )
        resp.raise_for_status()
        token = self._extract_tag(resp.text, 'TOKEN')
        if not token:
            raise Exception(f"No se pudo obtener token boleta SII: {resp.text[:500]}")
        self.boleta_token = token
        return token

    def enviar_boleta_rest(self, xml_firmado, rut_emisor, rut_envia):
        if not self.boleta_token:
            self.get_token_boleta()

        # Igual que en DTE tradicional, evitar CRLF ambiguos dentro del XML enviado.
        xml_firmado = xml_firmado.replace('\r\n', '\n').replace('\r', '\n')

        rut_envia_num, rut_envia_dv = _split_rut(rut_envia)
        rut_emisor_num, rut_emisor_dv = _split_rut(rut_emisor)

        data = {
            'rutSender': rut_envia_num,
            'dvSender': rut_envia_dv,
            'rutCompany': rut_emisor_num,
            'dvCompany': rut_emisor_dv,
        }
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/4.0 (compatible; PROG 1.0; Windows NT)',
            'Connection': 'close',
            'Accept-Encoding': 'identity',
        }

        def _post_boleta_requests(token):
            request_headers = headers.copy()
            request_headers['Cookie'] = f'TOKEN={token}'
            return self._request_with_dns_fallback(
                'POST',
                self.boleta_urls['upload'],
                data=data,
                files={
                    'archivo': ('envioBoleta.xml', xml_firmado.encode('ISO-8859-1'), 'text/xml')
                },
                headers=request_headers,
                timeout=30
            )

        def _post_boleta_manual(token):
            boundary = '----SIIBoletaBoundary' + ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            crlf = '\r\n'

            def part(name, value):
                return (
                    f'--{boundary}{crlf}'
                    f'Content-Disposition: form-data; name="{name}"{crlf}{crlf}'
                    f'{value}{crlf}'
                )

            file_part = (
                f'--{boundary}{crlf}'
                f'Content-Disposition: form-data; name="archivo"; filename="envioBoleta.xml"{crlf}'
                f'Content-Type: text/xml{crlf}{crlf}'
                f'{xml_firmado}{crlf}'
            )

            body_text = (
                part('rutSender', rut_envia_num) +
                part('dvSender', rut_envia_dv) +
                part('rutCompany', rut_emisor_num) +
                part('dvCompany', rut_emisor_dv) +
                file_part +
                f'--{boundary}--{crlf}'
            )
            body_bytes = body_text.encode('ISO-8859-1')

            request_headers = {
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/4.0 (compatible; PROG 1.0; Windows NT)',
                'Cookie': f'TOKEN={token}',
                'Content-Type': f'multipart/form-data; boundary={boundary}',
                'Connection': 'close',
                'Accept-Encoding': 'identity',
            }
            return self._request_with_dns_fallback(
                'POST',
                self.boleta_urls['upload'],
                data=body_bytes,
                headers=request_headers,
                timeout=30
            )

        resp = _post_boleta_requests(self.boleta_token)

        if resp.status_code in {401, 403, 500}:
            # El endpoint REST de boletas devuelve 500 con bastante frecuencia
            # cuando el token expira o queda inconsistente en el gateway.
            # Forzamos un token nuevo y reintentamos una sola vez.
            self.boleta_token = None
            self.get_token_boleta()
            resp = _post_boleta_requests(self.boleta_token)

        if resp.status_code == 500:
            # Fallback: algunos nodos del SII son sensibles al multipart generado
            # por requests. Reintentamos con un body manual equivalente al de DTE.
            resp = _post_boleta_manual(self.boleta_token)

        if not resp.ok:
            detalle = (resp.text or '').strip()
            if len(detalle) > 1000:
                detalle = detalle[:1000]
            if resp.status_code == 500 and detalle.lower() == 'error 500':
                detalle = (
                    'Error 500 generico del endpoint REST de boletas del SII. '
                    'El servidor no entrego detalle tecnico; puede indicar indisponibilidad '
                    'del servicio o un rechazo interno del gateway para el envio/rango CAF.'
                )
            raise Exception(
                f"Error HTTP {resp.status_code} al enviar boleta al SII: "
                f"{detalle or resp.reason or 'sin detalle'}"
            )

        text = resp.text
        try:
            payload = resp.json()
        except ValueError:
            payload = {}

        track_id = str(payload.get('trackid') or payload.get('track_id') or '')
        estado = payload.get('estado') or payload.get('status')
        return {
            'success': bool(track_id),
            'track_id': track_id,
            'estado': estado,
            'xml_respuesta': text
        }

    @staticmethod
    def _detalle_folio_boleta(detalles, folio):
        if not detalles:
            return None
        if folio is not None:
            folio_str = str(folio)
            for item in detalles:
                if str(item.get('folio') or '') == folio_str:
                    return item
        if len(detalles) == 1:
            return detalles[0]
        return None

    @staticmethod
    def _glosa_envio_boleta(payload, detalle, aceptados, rechazados, reparos):
        partes = []
        if detalle:
            desc = (detalle.get('descripcion') or detalle.get('estado') or '').strip()
            if desc:
                partes.append(desc)
            for err in detalle.get('error') or []:
                texto = (err.get('descripcion') or '').strip()
                extra = err.get('detalle')
                if texto and extra:
                    partes.append(f'{texto}: {extra}')
                elif texto:
                    partes.append(texto)
        elif aceptados and not rechazados and not reparos:
            partes.append(f'Envío procesado: {aceptados} aceptado(s)')
        elif rechazados:
            partes.append(f'Envío procesado: {rechazados} rechazado(s)')
        elif reparos:
            partes.append(f'Envío procesado: {reparos} con reparos')
        return ' | '.join(partes) or payload.get('glosa') or payload.get('descripcion') or payload.get('descResp') or ''

    def consultar_estado_boleta(self, track_id, rut_emisor, folio=None):
        if not str(track_id or '').strip().isdigit():
            raise ValueError(f'Track ID de boleta inválido para consulta SII: {track_id}')

        if not self.boleta_token:
            self.get_token_boleta()

        rut_emisor_num, rut_emisor_dv = _split_rut(rut_emisor)
        url = f"{self.boleta_urls['query']}/{rut_emisor_num}-{rut_emisor_dv}-{track_id}"
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/4.0 (compatible; PROG 1.0; Windows NT)',
            'Cookie': f'TOKEN={self.boleta_token}',
        }
        resp = self._request_with_dns_fallback('GET', url, headers=headers, timeout=20)
        text = resp.text
        try:
            payload = resp.json()
        except ValueError:
            resp.raise_for_status()
            payload = {}

        estado = payload.get('estado') or payload.get('codResp')
        stats = payload.get('estadistica') or []
        aceptados = sum(int(item.get('aceptados') or 0) for item in stats)
        rechazados = sum(int(item.get('rechazados') or 0) for item in stats)
        reparos = sum(int(item.get('reparos') or 0) for item in stats)
        informados = sum(int(item.get('informados') or 0) for item in stats)
        detalle = self._detalle_folio_boleta(payload.get('detalle_rep_rech') or [], folio)
        glosa = self._glosa_envio_boleta(payload, detalle, aceptados, rechazados, reparos)
        return {
            'success': estado in ['EPR', 'EOK', 'DOK', 'REC', 'SOK', 'CRT', 'RPR', 'RPC', 'RLV'],
            'estado': estado,
            'glosa': glosa,
            'aceptados': aceptados,
            'rechazados': rechazados,
            'reparos': reparos,
            'informados': informados,
            'detalle_estado': str((detalle or {}).get('estado') or '').upper(),
            'fecha_recepcion': payload.get('fecha_recepcion') or '',
            'xml_respuesta': text,
        }

    def enviar_dte(self, xml_firmado, rut_emisor, rut_envia, tipo_envio='DTE'):
        if tipo_envio == 'BOLETA' or '<EnvioBOLETA' in xml_firmado[:500]:
            return self.enviar_boleta_rest(xml_firmado, rut_emisor, rut_envia)

        if not self.token:
            self.get_token()

        # IMPORTANTE (TED/FRMT):
        # El SII valida la firma del timbre (FRMT) contra el bloque <DD> como cadena exacta.
        # En Windows, es común que algunas rutas/serializaciones introduzcan \r\n, lo que rompe esa firma.
        # Para evitar TED-2-510, normalizamos el XML a saltos de línea LF antes de enviarlo.
        xml_firmado = xml_firmado.replace('\r\n', '\n').replace('\r', '\n')
            
        rut_envia_num, rut_envia_dv = _split_rut(rut_envia)
        rut_emisor_num, rut_emisor_dv = _split_rut(rut_emisor)
        
        import random
        import string
        boundary = '----SIIBoundary' + ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        crlf = '\r\n'
        
        def part(name, value):
            return f'--{boundary}{crlf}Content-Disposition: form-data; name="{name}"{crlf}{crlf}{value}{crlf}'
            
        file_part = (
            f'--{boundary}{crlf}'
            f'Content-Disposition: form-data; name="archivo"; filename="envio.xml"{crlf}'
            f'Content-Type: text/xml{crlf}{crlf}'
            f'{xml_firmado}{crlf}'
        )
        
        body_text = (
            part('rutSender', rut_envia_num) +
            part('dvSender', rut_envia_dv) +
            part('rutCompany', rut_emisor_num) +
            part('dvCompany', rut_emisor_dv) +
            file_part +
            f'--{boundary}--{crlf}'
        )
        
        body_bytes = body_text.encode('ISO-8859-1')
        
        headers = {
            'User-Agent': 'Mozilla/4.0 (compatible; PROG 1.0; Windows NT)',
            'Accept': 'image/gif, image/x-xbitmap, image/jpeg, image/pjpeg, application/vnd.ms-powerpoint, application/ms-excel, application/msword, */*',
            'Cookie': f'TOKEN={self.token}',
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Connection': 'close',
            'Accept-Encoding': 'identity'
        }
        
        # Timeout explícito para evitar cuelgues cuando el SII no responde.
        resp = self._request_with_dns_fallback('POST', self.urls['upload'], data=body_bytes, headers=headers, timeout=30)
        resp.raise_for_status()
        
        text = resp.text
        
        # Procesar la respuesta para compatibilidad con la app Django
        track_id = self._extract_tag(text, 'TRACKID')
        estado = self._extract_tag(text, 'STATUS') or self._extract_tag(text, 'ESTADO')
        
        # Si el estado es 5 (No está autenticado / Token inválido o vencido), limpiamos caché y reintentamos.
        if estado == '5':
            ClienteSII._cached_token = None
            ClienteSII._token_timestamp = None
            self.token = None
            
            # Obtener un nuevo token e intentar de nuevo
            self.get_token()
            headers['Cookie'] = f'TOKEN={self.token}'
            
            resp = self._request_with_dns_fallback('POST', self.urls['upload'], data=body_bytes, headers=headers, timeout=30)
            resp.raise_for_status()
            text = resp.text
            track_id = self._extract_tag(text, 'TRACKID')
            estado = self._extract_tag(text, 'STATUS') or self._extract_tag(text, 'ESTADO')

        return {
            'success': bool(track_id and track_id != '0'),
            'track_id': track_id,
            'estado': estado,
            'xml_respuesta': text
        }
        
    def consultar_estado(self, track_id, rut_emisor):
        if not self.token:
            self.get_token()
            
        rut_emisor_num, rut_emisor_dv = _split_rut(rut_emisor)
        
        body = (
            '<def:getEstUp soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
            f'<RutCompania xsi:type="xsd:string">{rut_emisor_num}</RutCompania>'
            f'<DvCompania xsi:type="xsd:string">{rut_emisor_dv}</DvCompania>'
            f'<TrackIdEnv xsi:type="xsd:string">{track_id}</TrackIdEnv>'
            f'<Token xsi:type="xsd:string">{self.token}</Token>'
            '</def:getEstUp>'
        )
        
        resp_xml = self._soap_call(self.urls['query'], body)
        inner = self._extract_tag(resp_xml, 'getEstUpReturn') or self._extract_cdata(resp_xml)
        decoded = inner.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        
        estado = self._extract_tag(decoded, 'ESTADO')
        glosa = self._extract_tag(decoded, 'GLOSA_ESTADO') or self._extract_tag(decoded, 'GLOSA')
        informados = self._extract_tag(decoded, 'INFORMADOS')
        aceptados = self._extract_tag(decoded, 'ACEPTADOS')
        rechazados = self._extract_tag(decoded, 'RECHAZADOS')
        reparos = self._extract_tag(decoded, 'REPAROS')
        
        return {
            'success': estado in ['EPR', 'OK'],
            'estado': estado,
            'glosa': glosa,
            'xml_respuesta': resp_xml,
            'informados': int(informados or 0),
            'aceptados': int(aceptados or 0),
            'rechazados': int(rechazados or 0),
            'reparos': int(reparos or 0),
        }

    def obtener_datos_resolucion_empresa(self, rut_empresa):
        """Consulta la resolución registrada para el contribuyente en el SII.

        En certificación, el SII valida la fecha/número de resolución contra el
        padrón oficial de contribuyentes autorizados. Si estos datos no
        coinciden, rechaza el envío con CRT-3-19.
        """
        rut_buscado = _normalizar_rut(rut_empresa)

        fuentes = []
        if self.ambiente == 'CERTIFICACION':
            fuentes = [
                'https://maullin.sii.cl/cvc_cgi/dte/ee_consulta_empresas_dwnld?NOMBRE_ARCHIVO=ee_empresas_nomipyme.csv',
                'https://maullin.sii.cl/cvc_cgi/dte/ee_consulta_empresas_dwnld?NOMBRE_ARCHIVO=ee_empresas_mipyme.csv',
            ]

        for url in fuentes:
            try:
                resp = self.session.get(url, timeout=20)
                resp.raise_for_status()
                contenido = resp.content.decode('latin-1', errors='ignore')
            except Exception:
                continue

            for linea in contenido.splitlines():
                partes = [parte.strip() for parte in linea.split(';')]
                if len(partes) < 4:
                    continue

                rut_linea = _normalizar_rut(partes[0])
                if rut_linea != rut_buscado:
                    continue

                numero = int(re.sub(r'[^0-9]', '', partes[2] or '') or '0')
                fecha = datetime.strptime(partes[3], '%d-%m-%Y').date()
                return {
                    'numero': numero,
                    'fecha': fecha,
                    'fuente': url,
                }

        return None

    def _fecha_dte_sii(self, fecha_emision):
        try:
            if isinstance(fecha_emision, str):
                dt = datetime.strptime(fecha_emision[:10], '%Y-%m-%d')
            else:
                dt = fecha_emision
            return dt.strftime('%d%m%Y')
        except Exception:
            return str(fecha_emision or '')

    def _cuerpo_consulta_folio(self, metodo, rut_emisor, rut_receptor, tipo_dte, folio, fecha_emision, monto_total):
        rut_emisor_num, rut_emisor_dv = _split_rut(rut_emisor)
        rut_receptor_num, rut_receptor_dv = _split_rut(rut_receptor)
        fecha_str = self._fecha_dte_sii(fecha_emision)
        monto = int(monto_total or 0)
        return (
            f'<def:{metodo} soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
            f'<RutConsultante xsi:type="xsd:string">{rut_emisor_num}</RutConsultante>'
            f'<DvConsultante xsi:type="xsd:string">{rut_emisor_dv}</DvConsultante>'
            f'<RutCompania xsi:type="xsd:string">{rut_emisor_num}</RutCompania>'
            f'<DvCompania xsi:type="xsd:string">{rut_emisor_dv}</DvCompania>'
            f'<RutReceptor xsi:type="xsd:string">{rut_receptor_num}</RutReceptor>'
            f'<DvReceptor xsi:type="xsd:string">{rut_receptor_dv}</DvReceptor>'
            f'<TipoDte xsi:type="xsd:string">{tipo_dte}</TipoDte>'
            f'<FolioDte xsi:type="xsd:string">{folio}</FolioDte>'
            f'<FechaEmisionDte xsi:type="xsd:string">{fecha_str}</FechaEmisionDte>'
            f'<MontoDte xsi:type="xsd:string">{monto}</MontoDte>'
            f'<Token xsi:type="xsd:string">{self.token}</Token>'
            f'</def:{metodo}>'
        )

    def consultar_estado_por_folio(self, rut_emisor, rut_receptor, tipo_dte, folio, fecha_emision, monto_total):
        if not self.token:
            self.get_token()

        body = self._cuerpo_consulta_folio(
            'getEstDte', rut_emisor, rut_receptor, tipo_dte, folio, fecha_emision, monto_total
        )
        url_query_dte = (
            'https://palena.sii.cl/DTEWS/QueryEstDte.jws'
            if self.ambiente == 'PRODUCCION'
            else 'https://maullin.sii.cl/DTEWS/QueryEstDte.jws'
        )
        resp_xml = self._soap_call(url_query_dte, body)
        inner = self._extract_tag(resp_xml, 'getEstDteReturn') or self._extract_cdata(resp_xml)
        decoded = (inner or resp_xml).replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        decoded = decoded.replace('&#xd;', '\n')

        estado = self._extract_tag(decoded, 'ESTADO')
        glosa = (
            self._extract_tag(decoded, 'GLOSA_ESTADO')
            or self._extract_tag(decoded, 'GLOSA_ERR')
            or self._extract_tag(decoded, 'GLOSA')
        )
        glosa_err = self._extract_tag(decoded, 'GLOSA_ERR')
        if glosa_err and glosa_err not in (glosa or ''):
            glosa = f'{glosa} {glosa_err}'.strip() if glosa else glosa_err
        return {
            'success': bool(estado or glosa),
            'estado': estado,
            'glosa': glosa,
            'xml_respuesta': resp_xml,
        }

    def consultar_estado_dte_avanzado(self, rut_emisor, rut_receptor, tipo_dte, folio, fecha_emision, monto_total):
        """QueryEstDteAv: estado comercial del DTE (aceptado / reparos / rechazado)."""
        if not self.token:
            self.get_token()

        body = self._cuerpo_consulta_folio(
            'getEstDteAv', rut_emisor, rut_receptor, tipo_dte, folio, fecha_emision, monto_total
        )
        url_av = (
            'https://palena.sii.cl/DTEWS/QueryEstDteAv.jws'
            if self.ambiente == 'PRODUCCION'
            else 'https://maullin.sii.cl/DTEWS/QueryEstDteAv.jws'
        )
        resp_xml = self._soap_call(url_av, body)
        inner = self._extract_tag(resp_xml, 'getEstDteAvReturn') or self._extract_cdata(resp_xml)
        decoded = (inner or resp_xml).replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        decoded = decoded.replace('&#xd;', '\n')

        estadodte = self._extract_tag(decoded, 'ESTADODTE')
        estado_tag = self._extract_tag(decoded, 'ESTADO')
        desc = self._extract_tag(decoded, 'DESC_ESTADODTE') or self._extract_tag(decoded, 'GLOSA_ESTADO')
        glosa = desc or self._extract_tag(decoded, 'GLOSA_ERR') or self._extract_tag(decoded, 'GLOSA')
        codigo = str(estadodte or '').strip()
        mapa = {
            '1': ('DOK', 'DTE Recibido'),
            '2': ('EOK', 'DTE Aceptado'),
            '3': ('RPR', 'DTE Aceptado con reparos'),
            '4': ('RCH', 'DTE Rechazado'),
        }
        if codigo in mapa:
            codigo_sii, glosa_codigo = mapa[codigo]
        else:
            codigo_sii = str(estado_tag or codigo or '').strip().upper()
            glosa_codigo = glosa
        return {
            'success': bool(codigo or glosa),
            'estado': codigo_sii,
            'estadodte': codigo,
            'glosa': glosa or glosa_codigo,
            'xml_respuesta': resp_xml,
        }

    # Compatibility with the previous GestionCloud client API.
    def obtener_semilla(self):
        return self.get_seed()

    def obtener_token(self, semilla=None, firmador=None):
        return self.get_token(semilla)

    def consultar_estado_dte(self, track_id, token=None, rut_emisor=None):
        if token:
            self.token = token
        return self.consultar_estado(track_id, rut_emisor)
