"""Clasifica respuestas del SII sin confundir un reintento con un rechazo tributario."""
import re
import unicodedata

_RE_CODIGO = re.compile(r'(?<![A-Z0-9])(RCH|RSC|RPR|RPC|RLV|EOK|DOK|SOK|EPR)(?![A-Z0-9])')
_RE_TRACK = re.compile(r'TRACK\s*I?D\s*[:#-]?\s*(\d{6,})', re.IGNORECASE)
_RE_SEGUNDOS = re.compile(r'ESPERAR\s+(\d+)\s+SEGUNDO', re.IGNORECASE)


def normalizar_texto_sii(valor):
    texto = unicodedata.normalize('NFKD', str(valor or ''))
    texto = ''.join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', texto).upper().strip()


def texto_sii_de(*partes):
    return normalizar_texto_sii(' '.join(str(p or '') for p in partes))


def es_espera_reintento_sii(*partes):
    """True si el SII pidió esperar porque el archivo ya se envió (doble clic / reintento)."""
    texto = texto_sii_de(*partes)
    if not texto:
        return False
    if 'YA FUE ENVIADO' in texto:
        return True
    if 'DEBE ESPERAR' in texto and 'SEGUNDO' in texto:
        return True
    if 'ESPERAR' in texto and 'SEGUNDO' in texto and 'REINTENT' in texto:
        return True
    return False


def extraer_segundos_espera(*partes):
    texto = texto_sii_de(*partes)
    match = _RE_SEGUNDOS.search(texto)
    if match:
        return max(1, int(match.group(1)))
    if es_espera_reintento_sii(texto):
        return 900
    return 0


def extraer_track_id(*partes):
    texto = texto_sii_de(*partes)
    match = _RE_TRACK.search(texto)
    return match.group(1) if match else ''


def contiene_codigo_estado(texto, codigos):
    hallados = set(_RE_CODIGO.findall(normalizar_texto_sii(texto)))
    return any(codigo in hallados for codigo in codigos)


def contiene_palabra(texto, palabras):
    normalizado = normalizar_texto_sii(texto)
    return any(re.search(rf'(?<![A-Z0-9]){re.escape(palabra)}(?![A-Z0-9])', normalizado) for palabra in palabras)


def mensaje_espera_reintento(segundos=900, track_id=''):
    minutos = max(1, int((segundos or 900) / 60))
    track = f' Track ID {track_id}.' if track_id else ''
    return (
        f'El SII ya recibió este envío.{track} No es un rechazo del documento: '
        f'se reenvió demasiado rápido (suele pasar al pulsar Enviar más de una vez). '
        f'Espere {minutos} minutos y pulse Consultar SII. '
        f'No emita otro folio: el documento ya está en el SII.'
    )


def es_dte_repetido_sii(*partes):
    """True si el SII indica que el DTE ya fue recibido/registrado previamente (DTE-3-100 / DTE Repetido)."""
    texto = texto_sii_de(*partes)
    if not texto:
        return False
    if 'DTE-3-100' in texto:
        return True
    if 'DTE REPETIDO' in texto:
        return True
    if 'FOLIO REPETIDO' in texto:
        return True
    return False


def evidencia_rechazo_tributario(*partes):
    """True solo con evidencia real de rechazo: RCH, RSC o la palabra RECHAZADO (excluye esperas y repetidos)."""
    if es_espera_reintento_sii(*partes) or es_dte_repetido_sii(*partes):
        return False
    texto = texto_sii_de(*partes)
    if not texto:
        return False
    return contiene_codigo_estado(texto, ('RCH', 'RSC')) or contiene_palabra(
        texto, ('RECHAZADO', 'RECHAZADA')
    )


def es_dte_no_recibido_sii(*partes):
    """True si el SII tiene Track/envío pero el DTE no quedó registrado (FAU / -11)."""
    texto = texto_sii_de(*partes)
    if not texto:
        return False
    if 'FAU' in texto and 'NO RECIBIDO' in texto:
        return True
    if 'DTE NO RECIBIDO' in texto:
        return True
    if re.search(r'(?<![0-9])-11(?![0-9])', texto) and 'NO RECIBIDO' in texto:
        return True
    return 'GLOSA' not in texto and texto in {'FAU', '-11'}


def es_glosa_envio_procesado(*partes):
    """EPR / 'Envio Procesado' confirma recepción, no un rechazo tributario."""
    texto = texto_sii_de(*partes)
    return 'ENVIO PROCESADO' in texto


_RE_CONTEO_ENVIO = re.compile(
    r'(?:<|&lt;)(ACEPTADOS|RECHAZADOS|REPAROS)(?:>|&gt;)\s*(\d+)\s*(?:</|&lt;/)\1(?:>|&gt;)',
    re.I,
)


def conteos_envio_sii(*partes):
    """Lee ACEPTADOS/RECHAZADOS/REPAROS del XML QueryEstUp (crudo o escapado)."""
    texto = ' '.join(str(p or '') for p in partes)
    conteos = {'aceptados': 0, 'rechazados': 0, 'reparos': 0}
    for match in _RE_CONTEO_ENVIO.finditer(texto):
        conteos[match.group(1).lower()] = int(match.group(2))
    return conteos


# Documentos sin aceptación comercial del receptor (boletas y guías): DOK / SOK / EOK es estado final aceptado.
TIPOS_SIN_ACEPTACION_COMERCIAL = frozenset({'39', '41', '52'})


def es_dte_sin_aceptacion_comercial(tipo_dte):
    return str(tipo_dte or '').strip() in TIPOS_SIN_ACEPTACION_COMERCIAL


def es_recepcion_sii_documento(*partes):
    """El SII tiene el DTE (DOK / DTE Recibido / Schema Validado)."""
    texto = texto_sii_de(*partes)
    if not texto:
        return False
    if contiene_codigo_estado(texto, ('DOK', 'SOK')):
        return True
    return 'DTE RECIBIDO' in texto or 'SCHEMA VALIDADO' in texto


def es_consulta_datos_no_coinciden(*partes):
    """getEstDte DNK: el DTE existe, pero folio/monto/fecha no calzan con lo enviado."""
    texto = texto_sii_de(*partes)
    if 'DATOS NO COINCIDEN' in texto:
        return True
    return 'DNK' in texto and 'DTE RECIBIDO' in texto


def es_falso_rechazo_sii(*partes, estado_sii='', track_id=''):
    """
    estado_sii quedó en rechazado/error pero la glosa no es un RCH ni DOK/EOK:
    espera 900s, o glosa vacía/EPR sin rechazos tributarios ni codigos reales.
    """
    estado = str(estado_sii or '').strip().lower()
    if estado not in {'rechazado', 'error_envio', 'error'}:
        return False
    texto = texto_sii_de(*partes)
    if contiene_codigo_estado(texto, ('RCH', 'RSC', 'EOK', 'SOK', 'DOK', 'RPR', 'RPC', 'RLV')) or es_dte_repetido_sii(texto):
        return False
    if conteos_envio_sii(*partes).get('rechazados', 0) > 0:
        return False
    if evidencia_rechazo_tributario(*partes):
        return False
    if es_espera_reintento_sii(*partes):
        return True
    tiene_track = bool(str(track_id or '').strip() or extraer_track_id(*partes))
    if es_glosa_envio_procesado(*partes) and tiene_track:
        return True
    return (not texto) and tiene_track
