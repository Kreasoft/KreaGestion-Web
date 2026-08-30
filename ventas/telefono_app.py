import hashlib
import hmac
import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

AUTH_OFFLINE_HOURS = 48


def normalizar_telefono_cl(raw):
    """Devuelve celular chileno como 569XXXXXXXX o None."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if digits.startswith("56") and len(digits) >= 11:
        digits = digits[:11]
    elif digits.startswith("9") and len(digits) >= 9:
        digits = "56" + digits[:9]
    elif len(digits) == 8:
        digits = "569" + digits
    if len(digits) == 11 and digits.startswith("569"):
        return digits
    return None


def formatear_telefono_cl(norm):
    """56963697225 -> +56 9 63697225"""
    if not norm or len(str(norm)) != 11:
        return (norm or "") if norm else ""
    n = str(norm)
    return f"+{n[:2]} {n[2]} {n[3:]}"


def emitir_token_app(empresa_id, vendedor_id, telefono):
    msg = f"{empresa_id}|{vendedor_id}|{telefono}|app-movil"
    secret = str(getattr(settings, "SECRET_KEY", "") or "gestioncloud").encode("utf-8")
    return hmac.new(secret, msg.encode("utf-8"), hashlib.sha256).hexdigest()


def verificar_token_app(token, empresa_id, vendedor_id, telefono):
    if not token:
        return False
    esperado = emitir_token_app(empresa_id, vendedor_id, telefono)
    return hmac.compare_digest(esperado, str(token))


def cache_auth_vigente(activado_en, horas=AUTH_OFFLINE_HOURS):
    if not activado_en:
        return False
    limite = timezone.now() - timedelta(hours=horas)
    return activado_en >= limite
