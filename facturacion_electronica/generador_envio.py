from lxml import etree
from datetime import datetime
import base64
import pytz
import hashlib
import re
from collections import Counter
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

SII_NS = "http://www.sii.cl/SiiDte"
DSIG_NS = "http://www.w3.org/2000/09/xmldsig#"


def _load_pfx(pfx_path, password):
    with open(pfx_path, 'rb') as f:
        pfx_data = f.read()
    if isinstance(password, str):
        password = password.encode('utf-8')
    private_key, certificate, _ = pkcs12.load_key_and_certificates(pfx_data, password)
    return private_key, certificate


def _strip_xml_declaration(xml_str):
    """Elimina la declaracion <?xml ...?> de un string XML."""
    return re.sub(r'^\s*<\?xml[^?]*\?>\s*', '', xml_str).strip()


def _strip_xmlns_from_element(xml_str, tag):
    """
    Elimina la declaracion xmlns del elemento raiz indicado cuando va embebido
    en un padre que ya hereda el namespace, evitando duplicados que el SII rechaza.
    """
    xml_str = re.sub(r'(<' + tag + r'\b[^>]*?)\s+xmlns="[^"]*"', r'\1', xml_str)
    return xml_str


def _strip_signature_blocks(xml_str):
    """Elimina firmas XMLDSig previas para volver a firmar en el contexto final."""
    return re.sub(
        r'<(?:\w+:)?Signature\b[^>]*>.*?</(?:\w+:)?Signature>',
        '',
        xml_str,
        flags=re.DOTALL
    )


def _escape_xml_text(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\r", "&#13;")
    )


def _escape_xml_attr(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace('"', "&quot;")
        .replace("\t", "&#9;")
        .replace("\n", "&#10;")
        .replace("\r", "&#13;")
    )


def _qname_name(elem, qname_text):
    qname = etree.QName(qname_text)
    if not qname.namespace:
        return qname.localname
    for prefix, uri in (elem.nsmap or {}).items():
        if uri == qname.namespace:
            return f"{prefix}:{qname.localname}" if prefix else qname.localname
    return qname.localname


def _canonicalizar_elemento_sii(elem):
    """
    Canonicalizacion minima compatible con el perfil usado por el proyecto de referencia.
    Evita undeclarations xmlns="" que algunos validadores SII no toleran al recalcular firma.
    """
    inherited = {}
    parent = elem.getparent()
    while parent is not None:
        for prefix, uri in (parent.nsmap or {}).items():
            name = "xmlns" if prefix is None else f"xmlns:{prefix}"
            if name not in inherited:
                inherited[name] = uri
        parent = parent.getparent()

    def walk(node, is_apex, ns_context):
        name = _qname_name(node, node.tag)
        local_ns = {}
        for prefix, uri in (node.nsmap or {}).items():
            ns_name = "xmlns" if prefix is None else f"xmlns:{prefix}"
            local_ns[ns_name] = uri

        current_ns = dict(ns_context)
        ns_to_render = {}
        if is_apex:
            for ns_name, uri in inherited.items():
                if current_ns.get(ns_name) != uri:
                    ns_to_render[ns_name] = uri
                current_ns[ns_name] = uri

        for ns_name, uri in local_ns.items():
            if current_ns.get(ns_name) != uri:
                ns_to_render[ns_name] = uri
            current_ns[ns_name] = uri

        attrs = []
        for attr_name, value in node.attrib.items():
            attrs.append((_qname_name(node, attr_name), value))
        attrs.sort(key=lambda item: item[0])

        out = "<" + name
        for ns_name, uri in sorted(ns_to_render.items(), key=lambda item: item[0]):
            out += f' {ns_name}="{_escape_xml_attr(uri)}"'
        for attr_name, value in attrs:
            out += f' {attr_name}="{_escape_xml_attr(value)}"'
        out += ">"

        if node.text:
            out += _escape_xml_text(node.text)
        for child in node:
            if isinstance(child.tag, str):
                out += walk(child, False, current_ns)
            if child.tail:
                out += _escape_xml_text(child.tail)

        out += "</" + name + ">"
        return out

    return walk(elem, True, {}).encode('utf-8')


def _canonicalizar_xml_str_sii(xml_str):
    root = etree.fromstring(xml_str.encode('utf-8'))
    return _canonicalizar_elemento_sii(root)


def _firma_bloque(private_key, certificate, signed_info_str):
    """
    Canonicaliza un SignedInfo y lo firma. Devuelve (sig_b64, cert_b64, mod_b64, exp_b64).
    """
    signed_info_c14n = _canonicalizar_xml_str_sii(signed_info_str)

    signature_bytes = private_key.sign(
        signed_info_c14n,
        asym_padding.PKCS1v15(),
        hashes.SHA1()
    )
    sig_b64 = base64.b64encode(signature_bytes).decode()

    cert_der = certificate.public_bytes(serialization.Encoding.DER)
    cert_b64 = base64.b64encode(cert_der).decode()

    pub_numbers = certificate.public_key().public_numbers()
    mod_b64 = base64.b64encode(
        pub_numbers.n.to_bytes((pub_numbers.n.bit_length() + 7) // 8, 'big')
    ).decode()
    exp_b64 = base64.b64encode(
        pub_numbers.e.to_bytes((pub_numbers.e.bit_length() + 7) // 8, 'big')
    ).decode()
    return sig_b64, cert_b64, mod_b64, exp_b64


def _construir_signature(reference_uri, digest_b64, private_key, certificate):
    """
    Construye un bloque <Signature> XML-DSig completo como string puro (sin prefijos ns0:).
    """
    signed_info_str = (
        '<SignedInfo xmlns="http://www.w3.org/2000/09/xmldsig#">'
        '<CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>'
        '<SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>'
        f'<Reference URI="{reference_uri}">'
        '<Transforms>'
        '<Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>'
        '</Transforms>'
        '<DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>'
        f'<DigestValue>{digest_b64}</DigestValue>'
        '</Reference>'
        '</SignedInfo>'
    )
    sig_b64, cert_b64, mod_b64, exp_b64 = _firma_bloque(private_key, certificate, signed_info_str)

    return (
        '<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">\n'
        + signed_info_str
        + '\n'
        + f'<SignatureValue>{sig_b64}</SignatureValue>\n'
        + '<KeyInfo>\n'
        + '<KeyValue>\n'
        + '<RSAKeyValue>\n'
        + f'<Modulus>{mod_b64}</Modulus>\n'
        + f'<Exponent>{exp_b64}</Exponent>\n'
        + '</RSAKeyValue>\n'
        + '</KeyValue>\n'
        + '<X509Data>\n'
        + f'<X509Certificate>{cert_b64}</X509Certificate>\n'
        + '</X509Data>\n'
        + '</KeyInfo>\n'
        + '</Signature>\n'
    )


def _construir_signature_c14n_referencia(reference_uri, digest_b64, private_key, certificate, signed_info_ns_attrs=''):
    signed_info_str = (
        f'<SignedInfo xmlns="http://www.w3.org/2000/09/xmldsig#"{signed_info_ns_attrs}>'
        '<CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>'
        '<SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>'
        f'<Reference URI="{reference_uri}">'
        '<Transforms>'
        '<Transform Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>'
        '</Transforms>'
        '<DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>'
        f'<DigestValue>{digest_b64}</DigestValue>'
        '</Reference>'
        '</SignedInfo>'
    )
    sig_b64, cert_b64, mod_b64, exp_b64 = _firma_bloque(private_key, certificate, signed_info_str)

    return (
        '<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">\n'
        + signed_info_str
        + '\n'
        + f'<SignatureValue>{sig_b64}</SignatureValue>\n'
        + '<KeyInfo>\n'
        + '<KeyValue>\n'
        + '<RSAKeyValue>\n'
        + f'<Modulus>{mod_b64}</Modulus>\n'
        + f'<Exponent>{exp_b64}</Exponent>\n'
        + '</RSAKeyValue>\n'
        + '</KeyValue>\n'
        + '<X509Data>\n'
        + f'<X509Certificate>{cert_b64}</X509Certificate>\n'
        + '</X509Data>\n'
        + '</KeyInfo>\n'
        + '</Signature>\n'
    )


def _calcular_digest_str(xml_str_con_ns):
    """
    Parsea un string XML con namespace e ISO-8859-1, lo canonicaliza y calcula SHA1.
    """
    root = etree.fromstring(
        xml_str_con_ns.encode('ISO-8859-1'),
        parser=etree.XMLParser(encoding='ISO-8859-1')
    )
    c14n = _canonicalizar_elemento_sii(root)
    digest = hashlib.sha1(c14n).digest()
    return base64.b64encode(digest).decode()


def _calcular_digest_elemento(elemento, aplicar_enveloped=False):
    """
    Calcula SHA1 sobre el C14N del elemento en su contexto XML final.
    Esto evita firmas invalidas al insertar fragmentos bajo EnvioBOLETA/EnvioDTE.
    """
    removidas = []
    if aplicar_enveloped:
        # El Reference declara enveloped-signature: al validar, el SII excluye
        # cualquier ds:Signature descendiente del nodo referenciado.
        for signature in list(elemento.xpath('.//*[local-name()="Signature" and namespace-uri()=$ns]', ns=DSIG_NS)):
            parent = signature.getparent()
            if parent is None:
                continue
            removidas.append((parent, parent.index(signature), signature))
            parent.remove(signature)
    try:
        c14n = _canonicalizar_elemento_sii(elemento)
    finally:
        for parent, index, signature in reversed(removidas):
            parent.insert(index, signature)
    return base64.b64encode(hashlib.sha1(c14n).digest()).decode()


def _escapar_no_ascii(xml_str):
    """
    Punto de salida para normalizacion final.
    Se mantiene el ISO-8859-1 literal porque el CAF puede ser validado de forma estricta por el SII.
    """
    return xml_str


def _crear_signature_element(reference_uri, digest_b64, transform_algorithm):
    signature = etree.Element(f"{{{DSIG_NS}}}Signature", nsmap={None: DSIG_NS})
    signed_info = etree.SubElement(signature, f"{{{DSIG_NS}}}SignedInfo")
    etree.SubElement(
        signed_info,
        f"{{{DSIG_NS}}}CanonicalizationMethod",
        Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
    )
    etree.SubElement(
        signed_info,
        f"{{{DSIG_NS}}}SignatureMethod",
        Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"
    )
    reference = etree.SubElement(signed_info, f"{{{DSIG_NS}}}Reference", URI=reference_uri)
    transforms = etree.SubElement(reference, f"{{{DSIG_NS}}}Transforms")
    etree.SubElement(
        transforms,
        f"{{{DSIG_NS}}}Transform",
        Algorithm=transform_algorithm
    )
    etree.SubElement(
        reference,
        f"{{{DSIG_NS}}}DigestMethod",
        Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"
    )
    etree.SubElement(reference, f"{{{DSIG_NS}}}DigestValue").text = digest_b64
    etree.SubElement(signature, f"{{{DSIG_NS}}}SignatureValue")
    return signature


def _agregar_key_info(signature, certificate):
    cert_der = certificate.public_bytes(serialization.Encoding.DER)
    cert_b64 = base64.b64encode(cert_der).decode()

    pub_numbers = certificate.public_key().public_numbers()
    mod_b64 = base64.b64encode(
        pub_numbers.n.to_bytes((pub_numbers.n.bit_length() + 7) // 8, 'big')
    ).decode()
    exp_b64 = base64.b64encode(
        pub_numbers.e.to_bytes((pub_numbers.e.bit_length() + 7) // 8, 'big')
    ).decode()

    key_info = etree.SubElement(signature, f"{{{DSIG_NS}}}KeyInfo")
    key_value = etree.SubElement(key_info, f"{{{DSIG_NS}}}KeyValue")
    rsa_key_value = etree.SubElement(key_value, f"{{{DSIG_NS}}}RSAKeyValue")
    etree.SubElement(rsa_key_value, f"{{{DSIG_NS}}}Modulus").text = mod_b64
    etree.SubElement(rsa_key_value, f"{{{DSIG_NS}}}Exponent").text = exp_b64
    x509_data = etree.SubElement(key_info, f"{{{DSIG_NS}}}X509Data")
    etree.SubElement(x509_data, f"{{{DSIG_NS}}}X509Certificate").text = cert_b64


def _separar_lineas_signature(signature):
    """
    Agrega saltos entre tags largos de XMLDSig sin modificar los valores base64.
    El SII valida mejor cuando SignatureValue/certificados no contienen whitespace interno.
    """
    signed_info = signature.find(f"{{{DSIG_NS}}}SignedInfo")
    signature_value = signature.find(f"{{{DSIG_NS}}}SignatureValue")
    key_info = signature.find(f"{{{DSIG_NS}}}KeyInfo")
    if signed_info is not None:
        signed_info.tail = '\n'
    if signature_value is not None:
        signature_value.tail = '\n'
    if key_info is not None:
        key_info.tail = '\n'

    for local_name in ('Modulus', 'Exponent', 'KeyValue', 'RSAKeyValue', 'X509Certificate', 'X509Data'):
        for elem in signature.xpath(f'.//*[local-name()="{local_name}"]'):
            elem.tail = '\n'


def _firmar_referencia_en_contexto(parent, target, reference_uri, private_key, certificate, transform_algorithm):
    digest_b64 = _calcular_digest_elemento(
        target,
        aplicar_enveloped=transform_algorithm == "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
    )
    signature = _crear_signature_element(reference_uri, digest_b64, transform_algorithm)
    parent.append(signature)

    signed_info = signature.find(f"{{{DSIG_NS}}}SignedInfo")
    signed_info_c14n = etree.tostring(signed_info, method='c14n')
    signature_bytes = private_key.sign(
        signed_info_c14n,
        asym_padding.PKCS1v15(),
        hashes.SHA1()
    )
    signature.find(f"{{{DSIG_NS}}}SignatureValue").text = base64.b64encode(signature_bytes).decode()
    _agregar_key_info(signature, certificate)
    _separar_lineas_signature(signature)


def _firmar_envio_en_contexto(envio_xml, private_key, certificate):
    parser = etree.XMLParser(encoding='ISO-8859-1', remove_blank_text=False)
    root = etree.fromstring(envio_xml.encode('ISO-8859-1'), parser=parser)

    set_dte = root.xpath('.//*[local-name()="SetDTE"]')
    if not set_dte:
        raise ValueError("No se encontro SetDTE en el envio")
    set_dte = set_dte[0]
    set_id = set_dte.get('ID')
    if not set_id:
        raise ValueError("SetDTE sin ID: no se puede firmar")
    digest_b64 = _calcular_digest_elemento(set_dte, aplicar_enveloped=False)
    signature_block = _construir_signature_c14n_referencia(
        f'#{set_id}',
        digest_b64,
        private_key,
        certificate,
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
    )

    xml_firmado = etree.tostring(
        root,
        xml_declaration=True,
        encoding='ISO-8859-1',
        pretty_print=False
    ).decode('ISO-8859-1')
    xml_firmado = re.sub(
        r"^<\?xml\s+version='1\.0'\s+encoding='ISO-8859-1'\?>",
        '<?xml version="1.0" encoding="ISO-8859-1"?>',
        xml_firmado
    )
    root_close = re.search(r'</(?:EnvioBOLETA|EnvioDTE)>\s*$', xml_firmado)
    if not root_close:
        raise ValueError("No se encontro cierre del envio para insertar Signature")
    xml_firmado = xml_firmado[:root_close.start()] + signature_block + xml_firmado[root_close.start():]
    return _escapar_no_ascii(xml_firmado)


def _extraer_tipo_dte(xml_str):
    """Extrae el TipoDTE de un string XML de DTE."""
    m = re.search(r'<TipoDTE>(\d+)</TipoDTE>', xml_str)
    return m.group(1) if m else None


def _extraer_tmst_firma(xml_str):
    m = re.search(r'<TmstFirma>([^<]+)</TmstFirma>', xml_str)
    return m.group(1) if m else None


def _timestamp_envio_chile():
    chile_tz = pytz.timezone('America/Santiago')
    return datetime.now(chile_tz).strftime('%Y-%m-%dT%H:%M:%S')


def generar_envio_dte(xml_firmados, rut_emisor, rut_envia, pfx_path, pfx_password,
                      fecha_resolucion, num_resolucion):
    """
    Empaqueta DTEs en el sobre correcto segun el tipo:
      - Boletas (39, 41) -> EnvioBOLETA (schema requerido por el SII)
      - Resto            -> EnvioDTE

    El sobre se construye como string XML puro para evitar que lxml
    duplique declaraciones xmlns que causan SCH-00001 en el SII.
    """
    # Detectar si son boletas o facturas/guias
    tipos_en_envio = []
    for xml_str in xml_firmados:
        t = _extraer_tipo_dte(xml_str)
        if t:
            tipos_en_envio.append(int(t))

    es_boleta = all(t in (39, 41) for t in tipos_en_envio) and bool(tipos_en_envio)

    if es_boleta:
        return _generar_envio_boleta(xml_firmados, rut_emisor, rut_envia, pfx_path,
                                     pfx_password, fecha_resolucion, num_resolucion,
                                     tipos_en_envio)
    else:
        return _generar_envio_dte(xml_firmados, rut_emisor, rut_envia, pfx_path,
                                  pfx_password, fecha_resolucion, num_resolucion)


def _limpiar_dtes(xml_firmados):
    """
    Limpia solo la declaracion XML del DTE embebido.
    Mantener el xmlns del nodo <DTE> replica el formato del proyecto KreaDTE
    que hoy esta enviando boletas correctamente.
    """
    resultado = []
    for xml_str in xml_firmados:
        resultado.append(_strip_xml_declaration(xml_str))
    return resultado


def _generar_envio_boleta(xml_firmados, rut_emisor, rut_envia, pfx_path, pfx_password,
                          fecha_resolucion, num_resolucion, tipos_en_envio):
    """
    Genera un EnvioBOLETA valido para el SII (boletas tipo 39/41).
    Diferencias vs EnvioDTE:
      - Elemento raiz: <EnvioBOLETA>
      - Caratula incluye <SubTotDTE> con conteo por tipo
    """
    rut_emisor_str = rut_emisor.replace('.', '')
    rut_envia_str = rut_envia.replace('.', '')
    timestamp = _extraer_tmst_firma(xml_firmados[0]) or _timestamp_envio_chile()

    private_key, certificate = _load_pfx(pfx_path, pfx_password)

    # SubTotDTE: conteo de documentos por TipoDTE
    conteo = Counter(tipos_en_envio)
    subtot_str = ''
    for tipo, cantidad in sorted(conteo.items()):
        subtot_str += (
            '<SubTotDTE>'
            f'<TpoDTE>{tipo}</TpoDTE>'
            f'<NroDTE>{cantidad}</NroDTE>'
            '</SubTotDTE>'
        )

    caratula_str = (
        '<Caratula version="1.0">'
        f'<RutEmisor>{rut_emisor_str}</RutEmisor>'
        f'<RutEnvia>{rut_envia_str}</RutEnvia>'
        '<RutReceptor>60803000-K</RutReceptor>'
        f'<FchResol>{fecha_resolucion}</FchResol>'
        f'<NroResol>{num_resolucion}</NroResol>'
        f'<TmstFirmaEnv>{timestamp}</TmstFirmaEnv>'
        + subtot_str +
        '</Caratula>'
    )

    dtes_str = ''.join(_limpiar_dtes(xml_firmados))

    set_dte_str = (
        '<SetDTE ID="SetDoc">\n'
        + caratula_str + '\n'
        + dtes_str + '\n'
        + '</SetDTE>\n'
    )

    envio_xml_sin_firma = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
        '<EnvioBOLETA xmlns="http://www.sii.cl/SiiDte" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://www.sii.cl/SiiDte EnvioBOLETA_v11.xsd" '
        'version="1.0">\n'
        + set_dte_str
        + '</EnvioBOLETA>'
    )
    return _firmar_envio_en_contexto(envio_xml_sin_firma, private_key, certificate)


def _generar_envio_dte(xml_firmados, rut_emisor, rut_envia, pfx_path, pfx_password,
                       fecha_resolucion, num_resolucion):
    """
    Genera un EnvioDTE valido para el SII (facturas, guias, notas de credito/debito).
    """
    rut_emisor_str = rut_emisor.replace('.', '')
    rut_envia_str = rut_envia.replace('.', '')
    timestamp = _extraer_tmst_firma(xml_firmados[0]) or _timestamp_envio_chile()

    private_key, certificate = _load_pfx(pfx_path, pfx_password)

    tipos_en_envio = []
    for xml_str in xml_firmados:
        t = _extraer_tipo_dte(xml_str)
        if t:
            tipos_en_envio.append(int(t))

    from collections import Counter
    conteo = Counter(tipos_en_envio)
    subtot_str = ''
    for tipo, cantidad in sorted(conteo.items()):
        subtot_str += (
            '<SubTotDTE>'
            f'<TpoDTE>{tipo}</TpoDTE>'
            f'<NroDTE>{cantidad}</NroDTE>'
            '</SubTotDTE>'
        )

    caratula_str = (
        '<Caratula version="1.0">'
        f'<RutEmisor>{rut_emisor_str}</RutEmisor>'
        f'<RutEnvia>{rut_envia_str}</RutEnvia>'
        '<RutReceptor>60803000-K</RutReceptor>'
        f'<FchResol>{fecha_resolucion}</FchResol>'
        f'<NroResol>{num_resolucion}</NroResol>'
        f'<TmstFirmaEnv>{timestamp}</TmstFirmaEnv>'
        + subtot_str +
        '</Caratula>'
    )

    dtes_str = ''.join(_limpiar_dtes(xml_firmados))

    set_dte_str = (
        '<SetDTE ID="SetDoc">\n'
        + caratula_str + '\n'
        + dtes_str + '\n'
        + '</SetDTE>\n'
    )

    envio_xml_sin_firma = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
        '<EnvioDTE xmlns="http://www.sii.cl/SiiDte" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://www.sii.cl/SiiDte EnvioDTE_v10.xsd" '
        'version="1.0">\n'
        + set_dte_str
        + '</EnvioDTE>'
    )
    return _firmar_envio_en_contexto(envio_xml_sin_firma, private_key, certificate)
