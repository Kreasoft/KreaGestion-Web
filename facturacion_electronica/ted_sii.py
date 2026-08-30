import base64
import re
from datetime import datetime

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key


def _escape_xml(text):
    if text is None:
        return ""
    text = str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _caf_xml(caf):
    if getattr(caf, "contenido_caf", None):
        return caf.contenido_caf
    if getattr(caf, "archivo_xml", None):
        with open(caf.archivo_xml.path, "r", encoding="ISO-8859-1") as fh:
            return fh.read()
    raise ValueError("CAF sin contenido XML")


def construir_ted(rut_emisor, tipo_dte, folio, fecha_emision, rut_receptor,
                  razon_social_receptor, monto_total, item_1, caf):
    """Construye TED SII firmando DD con la llave privada RSASK del CAF."""
    caf_xml = _caf_xml(caf).strip()

    match_caf = re.search(r'(<CAF(?:\s+version="1\.0")?>.*?</CAF>)', caf_xml, re.DOTALL)
    if not match_caf:
        raise ValueError("No se encontro el bloque <CAF> en el archivo de folios")

    caf_block = match_caf.group(1).replace("\r\n", "\n").replace("\r", "\n")
    caf_block = re.sub(r'>\s+<', '><', caf_block)

    match_rsask = re.search(r'<RSASK>(.*?)</RSASK>', caf_xml, re.DOTALL)
    if not match_rsask:
        raise ValueError("No se encontro la llave privada <RSASK> en el CAF")

    rsask_content = match_rsask.group(1).strip()
    if not rsask_content.startswith("-----BEGIN"):
        rsask_pem = f"-----BEGIN RSA PRIVATE KEY-----\n{rsask_content}\n-----END RSA PRIVATE KEY-----"
    else:
        rsask_pem = rsask_content

    tsted = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    dd_xml = (
        '<DD>'
        f'<RE>{_escape_xml(str(rut_emisor).replace(".", ""))}</RE>'
        f'<TD>{tipo_dte}</TD>'
        f'<F>{folio}</F>'
        f'<FE>{fecha_emision}</FE>'
        f'<RR>{_escape_xml(str(rut_receptor).replace(".", ""))}</RR>'
        f'<RSR>{_escape_xml(str(razon_social_receptor)[:40].strip())}</RSR>'
        f'<MNT>{int(monto_total)}</MNT>'
        f'<IT1>{_escape_xml(str(item_1)[:40].strip())}</IT1>'
        f'{caf_block}'
        f'<TSTED>{tsted}</TSTED>'
        '</DD>'
    )

    dd_iso = dd_xml.encode("ISO-8859-1")
    private_key = load_pem_private_key(
        rsask_pem.encode("utf-8"),
        password=None,
        backend=default_backend(),
    )
    signature = private_key.sign(dd_iso, padding.PKCS1v15(), hashes.SHA1())
    sig_b64 = base64.b64encode(signature).decode("ascii")
    sig_multiline = "\n".join(sig_b64[i:i + 64] for i in range(0, len(sig_b64), 64))

    return (
        '<TED version="1.0">\n'
        f'{dd_xml}\n'
        f'<FRMT algoritmo="SHA1withRSA">{sig_multiline}</FRMT>\n'
        '</TED>'
    )
