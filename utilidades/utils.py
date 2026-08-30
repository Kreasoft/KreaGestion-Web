def clean_id(dirty_id):
    """Limpia un ID, eliminando cualquier carácter no numérico."""
    if isinstance(dirty_id, str):
        return ''.join(filter(str.isdigit, dirty_id))
    return dirty_id


def datos_smtp(empresa=None):
    """Host, usuario y clave SMTP de la empresa o de .env. listo=True si se puede enviar."""
    from django.conf import settings

    host = (getattr(empresa, 'smtp_host', None) or '').strip()
    user = (getattr(empresa, 'smtp_usuario', None) or '').strip()
    password = (getattr(empresa, 'smtp_password', None) or '').strip()
    port = getattr(empresa, 'smtp_puerto', None) or None
    use_tls = getattr(empresa, 'smtp_usar_tls', None)
    use_ssl = False

    if not (host and user and password):
        host = host or (getattr(settings, 'EMAIL_HOST', None) or '').strip()
        user = user or (getattr(settings, 'EMAIL_HOST_USER', None) or '').strip()
        password = password or (getattr(settings, 'EMAIL_HOST_PASSWORD', None) or '').strip()
        if not port:
            port = getattr(settings, 'EMAIL_PORT', 587) or 587
        if use_tls is None:
            use_tls = getattr(settings, 'EMAIL_USE_TLS', True)
        use_ssl = getattr(settings, 'EMAIL_USE_SSL', False)
    else:
        if not port:
            port = 587
        if use_tls is None:
            use_tls = True

    return {
        'listo': bool(host and user and password),
        'host': host,
        'port': int(port or 587),
        'user': user,
        'password': password,
        'use_tls': bool(use_tls),
        'use_ssl': bool(use_ssl),
        'from_email': user or getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'no-reply@gestioncloud.cl',
    }


def conexion_correo(empresa=None):
    """Conexión SMTP real, o None si no hay credenciales."""
    from django.conf import settings
    from django.core.mail import get_connection

    datos = datos_smtp(empresa)
    if not datos['listo']:
        return None
    return get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=datos['host'],
        port=datos['port'],
        username=datos['user'],
        password=datos['password'],
        use_tls=datos['use_tls'],
        use_ssl=datos['use_ssl'],
        timeout=getattr(settings, 'EMAIL_TIMEOUT', 20),
    )


def correo_usa_consola(empresa=None):
    """True si no hay SMTP usable (el mail no llega a ningún buzón)."""
    return not datos_smtp(empresa)['listo']


def aviso_correo_no_entregado(destinatario):
    """Mensaje para el usuario cuando falta SMTP."""
    return (
        f'El correo NO se envió a {destinatario}: falta el servidor SMTP. '
        'En Empresa → pestaña Datos complete usuario y contraseña de correo, '
        'o en .env EMAIL_HOST_USER y EMAIL_HOST_PASSWORD '
        '(Gmail: contraseña de aplicación) y reinicie el servidor.'
    )
