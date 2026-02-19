"""
Utilidades para validación y envío seguro de DTEs
"""
from django.utils import timezone
from datetime import datetime


def validar_dte_antes_envio(dte):
    """
    Valida que un DTE esté listo para ser enviado al SII/DTEBox.
    
    Args:
        dte: Instancia de DocumentoTributarioElectronico
        
    Returns:
        tuple: (es_valido: bool, mensaje_error: str or None)
    """
    
    # 1. Verificar que no esté ya enviado o aceptado
    if dte.estado_sii in ['enviado', 'aceptado']:
        return False, f"El DTE ya fue enviado (estado: {dte.estado_sii})"
    
    # 2. Verificar que no esté anulado
    if dte.estado_sii == 'anulado':
        return False, "El DTE está anulado y no puede ser enviado"
    
    # 3. Verificar que tenga XML firmado
    if not dte.xml_firmado or len(dte.xml_firmado.strip()) == 0:
        return False, "El DTE no tiene XML firmado"
    
    # 4. Verificar que tenga CAF asignado
    if not dte.caf_utilizado:
        return False, "El DTE no tiene CAF asignado"
    
    # 5. Verificar que el CAF esté vigente
    if dte.caf_utilizado:
        hoy = timezone.now().date()
        
        # Verificar fecha de vencimiento
        try:
            fecha_venc = dte.caf_utilizado.fecha_vencimiento
            # Si es un método, llamarlo
            if callable(fecha_venc):
                fecha_venc = fecha_venc()
            
            if fecha_venc and fecha_venc < hoy:
                return False, f"El CAF está vencido (venció el {fecha_venc})"
        except (AttributeError, TypeError):
            # Si no tiene fecha de vencimiento, continuar
            pass
        
        # Verificar que el folio esté dentro del rango
        if not (dte.caf_utilizado.folio_desde <= dte.folio <= dte.caf_utilizado.folio_hasta):
            return False, f"El folio {dte.folio} está fuera del rango del CAF ({dte.caf_utilizado.folio_desde}-{dte.caf_utilizado.folio_hasta})"
    
    # 6. Verificar que tenga empresa asignada
    if not dte.empresa:
        return False, "El DTE no tiene empresa asignada"
    
    # 7. Verificar que la empresa tenga DTEBox habilitado
    if not dte.empresa.dtebox_habilitado:
        return False, f"La empresa {dte.empresa.nombre} no tiene DTEBox habilitado"
    
    # 8. Verificar configuración de DTEBox
    if not dte.empresa.dtebox_url:
        return False, "La empresa no tiene configurada la URL de DTEBox"
    
    if not dte.empresa.dtebox_auth_key:
        return False, "La empresa no tiene configurada la Auth Key de DTEBox"
    
    # 9. Verificar que tenga datos mínimos
    if not dte.rut_receptor:
        return False, "El DTE no tiene RUT del receptor"
    
    if not dte.monto_total or dte.monto_total <= 0:
        return False, "El DTE no tiene monto total válido"
    
    # 10. Verificar que el XML sea válido (básico)
    try:
        import xml.etree.ElementTree as ET
        ET.fromstring(dte.xml_firmado)
    except Exception as e:
        return False, f"El XML firmado no es válido: {str(e)}"
    
    # ✅ Todas las validaciones pasaron
    return True, None


def obtener_dtes_pendientes_envio(empresa=None):
    """
    Obtiene todos los DTEs que están pendientes de envío.
    
    Args:
        empresa: Instancia de Empresa (opcional, filtra por empresa)
        
    Returns:
        QuerySet de DocumentoTributarioElectronico
    """
    from facturacion_electronica.models import DocumentoTributarioElectronico
    
    # Estados que indican que el DTE debe ser enviado
    estados_pendientes = ['generado', 'firmado', 'error_envio']
    
    query = DocumentoTributarioElectronico.objects.filter(
        estado_sii__in=estados_pendientes
    ).select_related('empresa', 'caf_utilizado')
    
    if empresa:
        query = query.filter(empresa=empresa)
    
    return query.order_by('fecha_emision', 'folio')


def diagnosticar_dte(dte):
    """
    Genera un diagnóstico completo de un DTE.
    
    Args:
        dte: Instancia de DocumentoTributarioElectronico
        
    Returns:
        dict con información de diagnóstico
    """
    es_valido, error = validar_dte_antes_envio(dte)
    
    # Verificar CAF vigente de forma segura
    caf_vigente = None
    if dte.caf_utilizado:
        try:
            fecha_venc = dte.caf_utilizado.fecha_vencimiento
            if callable(fecha_venc):
                fecha_venc = fecha_venc()
            if fecha_venc:
                caf_vigente = fecha_venc >= timezone.now().date()
        except (AttributeError, TypeError):
            pass
    
    return {
        'id': dte.id,
        'tipo_dte': dte.tipo_dte,
        'folio': dte.folio,
        'fecha_emision': dte.fecha_emision,
        'estado_sii': dte.estado_sii,
        'monto_total': dte.monto_total,
        'receptor': dte.razon_social_receptor,
        'rut_receptor': dte.rut_receptor,
        'tiene_xml': bool(dte.xml_firmado),
        'tiene_caf': bool(dte.caf_utilizado),
        'caf_vigente': caf_vigente,
        'es_valido_para_envio': es_valido,
        'error_validacion': error,
        'ultimo_error_envio': dte.error_envio if hasattr(dte, 'error_envio') else None,
    }
