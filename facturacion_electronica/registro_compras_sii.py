"""Consulta directa al Registro de Compras y Ventas alojado por el SII."""
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from .cliente_sii import ClienteSII, _split_rut


class RegistroComprasSII:
    ENDPOINT = 'https://www4.sii.cl/consdcvinternetui/services/data/facadeService/getDetalleCompraExport'
    NAMESPACE = 'cl.sii.sdi.lob.diii.consdcv.data.api.interfaces.FacadeService/getDetalleCompraExport'

    def __init__(self, empresa):
        if not empresa.certificado_digital or not empresa.password_certificado:
            raise ValueError('La empresa debe tener certificado digital y contraseña configurados.')
        # El RCV corresponde al ambiente tributario real del SII.
        ClienteSII._cached_token = None
        ClienteSII._token_timestamp = None
        self.cliente = ClienteSII('PRODUCCION', empresa.certificado_digital.path, empresa.password_certificado)
        self.token = self.cliente.get_token()
        self.rut, self.dv = _split_rut(empresa.rut)

    def consultar_periodo(self, periodo):
        if not (len(periodo) == 6 and periodo.isdigit() and 1 <= int(periodo[4:]) <= 12):
            raise ValueError('El período debe tener formato AAAAMM.')
        documentos = []
        for estado_rcv in ('REGISTRO', 'PENDIENTE', 'RECLAMADO', 'NO_INCLUIR'):
            documentos.extend(self._consultar_seccion(periodo, estado_rcv))
        return documentos

    def _consultar_seccion(self, periodo, estado_rcv):
        payload = {
            'metaData': {'namespace': self.NAMESPACE, 'conversationId': self.token, 'transactionId': '0', 'page': None},
            'data': {
                'rutEmisor': self.rut, 'dvEmisor': self.dv, 'ptributario': periodo,
                'operacion': 'COMPRA', 'estadoContab': estado_rcv, 'codTipoDoc': '0',
            },
        }
        respuesta = self.cliente.session.post(
            self.ENDPOINT, json=payload, timeout=45,
            headers={
                'Cookie': f'TOKEN={self.token}', 'Content-Type': 'application/json; charset=utf-8',
                'Accept': 'application/json, text/plain, */*', 'Referer': 'https://www4.sii.cl/consdcvinternetui/',
            },
        )
        respuesta.raise_for_status()
        cuerpo = respuesta.json()
        estado = cuerpo.get('respEstado') or {}
        if estado.get('codRespuesta') in (99, '99'):
            return []
        if estado.get('codRespuesta') not in (0, '0'):
            raise RuntimeError(f'RCV SII rechazó la consulta: {estado.get("codError") or estado.get("msgeRespuesta") or estado}')
        lineas = cuerpo.get('data') or []
        if not lineas:
            return []
        filas = list(csv.DictReader(lineas, delimiter=';'))
        return [self._normalizar_fila(fila, estado_rcv) for fila in filas if fila.get('Tipo Doc') and fila.get('Folio')]

    @staticmethod
    def _decimal(valor):
        limpio = str(valor or '0').strip().replace('.', '').replace(',', '.')
        try:
            return Decimal(limpio or '0')
        except InvalidOperation:
            return Decimal('0')

    @staticmethod
    def _fecha(valor, con_hora=False):
        valor = str(valor or '').strip()
        if not valor:
            return None
        formato = '%d/%m/%Y %H:%M:%S' if con_hora else '%d/%m/%Y'
        fecha = datetime.strptime(valor, formato)
        return timezone.make_aware(fecha) if con_hora else fecha.date()

    def _normalizar_fila(self, fila, estado_rcv):
        return {
            'tipo_dte': str(fila.get('Tipo Doc', '')).strip(),
            'folio': int(str(fila.get('Folio', '0')).strip()),
            'rut_emisor': str(fila.get('RUT Proveedor', '')).strip().upper(),
            'razon_social_emisor': str(fila.get('Razon Social', '')).strip(),
            'fecha_emision': self._fecha(fila.get('Fecha Docto')),
            'fecha_recepcion_sii': self._fecha(fila.get('Fecha Recepcion'), con_hora=True),
            'estado_rcv': estado_rcv,
            'tipo_compra_rcv': str(fila.get('Tipo Compra', '')).strip(),
            'monto_neto': self._decimal(fila.get('Monto Neto')),
            'monto_iva': self._decimal(fila.get('Monto IVA Recuperable')),
            'monto_total': self._decimal(fila.get('Monto Total')),
        }
