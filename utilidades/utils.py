def clean_id(dirty_id):
    """Limpia un ID, eliminando cualquier carácter no numérico."""
    if isinstance(dirty_id, str):
        return ''.join(filter(str.isdigit, dirty_id))
    return dirty_id
