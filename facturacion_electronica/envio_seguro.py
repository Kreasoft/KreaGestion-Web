"""
Sistema de envío seguro de DTEs con validación y manejo de errores
"""
from django.db import transaction
from django.utils import timezone
from .validacion_envio import validar_dte_antes_envio
import logging

logger = logging.getLogger(__name__)


def enviar_dte_seguro(dte, forzar=False):
    """
    Envía un DTE al SII con validación previa y manejo robusto de errores.
    
    Args:
        dte: Instancia de DocumentoTributarioElectronico
        forzar: Si True, intenta enviar aunque haya fallado la validación (usar con cuidado)
        
    Returns:
        dict: {
            'success': bool,
            'mensaje': str,
            'track_id': str (si success=True),
            'error': str (si success=False),
            'detalles': dict
        }
    """
    
    resultado = {
        'success': False,
        'mensaje': '',
        'track_id': None,
        'error': None,
        'detalles': {}
    }
    
    try:
        logger.info(f"[ENVÍO SEGURO] Iniciando envío de DTE {dte.tipo_dte} #{dte.folio}")
        
        # PASO 1: Validación previa
        if not forzar:
            es_valido, error_validacion = validar_dte_antes_envio(dte)
            
            if not es_valido:
                resultado['error'] = f"Validación fallida: {error_validacion}"
                resultado['mensaje'] = f"❌ No se puede enviar: {error_validacion}"
                logger.warning(f"[ENVÍO SEGURO] Validación fallida para DTE {dte.id}: {error_validacion}")
                return resultado
            
            logger.info(f"[ENVÍO SEGURO] ✓ Validación previa exitosa")
        else:
            logger.warning(f"[ENVÍO SEGURO] ⚠️ Envío forzado - saltando validación")
        
        # PASO 2: Marcar como 'enviando' (previene envíos duplicados)
        estado_anterior = dte.estado_sii
        
        with transaction.atomic():
            # Recargar el DTE con lock para evitar race conditions
            dte_locked = dte.__class__.objects.select_for_update().get(pk=dte.pk)
            
            # Verificar que no haya sido enviado por otro proceso
            if dte_locked.estado_sii in ['enviando', 'enviado', 'aceptado']:
                resultado['error'] = f"El DTE ya está en estado '{dte_locked.estado_sii}'"
                resultado['mensaje'] = f"⚠️ El DTE ya fue procesado (estado: {dte_locked.estado_sii})"
                logger.warning(f"[ENVÍO SEGURO] DTE {dte.id} ya procesado: {dte_locked.estado_sii}")
                return resultado
            
            dte_locked.estado_sii = 'enviando'
            dte_locked.save(update_fields=['estado_sii'])
            dte.refresh_from_db()
        
        logger.info(f"[ENVÍO SEGURO] ✓ Estado cambiado a 'enviando'")
        # PASO 3: Enviar directo al SII
        try:
            from .dte_service import DTEService

            service = DTEService(dte.empresa)
            logger.info("[ENVIO SEGURO] Enviando directo al SII...")
            resultado_sii = service.enviar_dte_al_sii(dte)

            if resultado_sii.get('success'):
                dte.refresh_from_db()
                resultado['success'] = True
                resultado['track_id'] = dte.track_id
                resultado['mensaje'] = f"DTE enviado exitosamente al SII - Track ID: {dte.track_id}"
                resultado['detalles'] = {
                    'track_id': dte.track_id,
                    'fecha_envio': dte.fecha_envio_sii.isoformat() if dte.fecha_envio_sii else None,
                }
            else:
                error_sii = resultado_sii.get('error') or resultado_sii.get('xml_respuesta') or 'Error desconocido del SII'
                with transaction.atomic():
                    dte.estado_sii = 'error_envio'
                    if hasattr(dte, 'error_envio'):
                        dte.error_envio = error_sii
                    dte.save()
                resultado['error'] = error_sii
                resultado['mensaje'] = f"Error del SII: {error_sii}"
                resultado['detalles'] = {'error_sii': error_sii}

        except Exception as e_envio:
            # PASO 6: Error de conexión o sistema
            logger.error(f"[ENVÍO SEGURO] ❌ Excepción al enviar: {str(e_envio)}", exc_info=True)
            
            with transaction.atomic():
                dte.estado_sii = 'error_envio'
                if hasattr(dte, 'error_envio'):
                    dte.error_envio = f"Excepción: {str(e_envio)}"
                dte.save()
            
            resultado['error'] = str(e_envio)
            resultado['mensaje'] = f"❌ Error de sistema: {str(e_envio)}"
            resultado['detalles'] = {'excepcion': str(e_envio)}
    
    except Exception as e_general:
        # Error crítico en el proceso
        logger.critical(f"[ENVÍO SEGURO] 💥 Error crítico: {str(e_general)}", exc_info=True)
        
        # Intentar restaurar estado anterior
        try:
            with transaction.atomic():
                dte.estado_sii = estado_anterior if 'estado_anterior' in locals() else 'error_envio'
                dte.save()
        except:
            pass
        
        resultado['error'] = f"Error crítico: {str(e_general)}"
        resultado['mensaje'] = f"💥 Error crítico en el proceso de envío"
        resultado['detalles'] = {'error_critico': str(e_general)}
    
    return resultado


def reenviar_dtes_pendientes(empresa=None, limite=None, solo_diagnostico=False):
    """
    Reenvía todos los DTEs pendientes de envío.
    
    Args:
        empresa: Instancia de Empresa (opcional, filtra por empresa)
        limite: Número máximo de DTEs a procesar (None = todos)
        solo_diagnostico: Si True, solo muestra qué se haría sin enviar realmente
        
    Returns:
        dict: {
            'total_procesados': int,
            'exitosos': int,
            'fallidos': int,
            'saltados': int,
            'resultados': list[dict]
        }
    """
    from .validacion_envio import obtener_dtes_pendientes_envio, diagnosticar_dte
    
    logger.info(f"[REENVÍO] Iniciando proceso de reenvío de DTEs pendientes")
    
    # Obtener DTEs pendientes
    dtes_pendientes = obtener_dtes_pendientes_envio(empresa)
    
    if limite:
        dtes_pendientes = dtes_pendientes[:limite]
    
    total = dtes_pendientes.count()
    logger.info(f"[REENVÍO] Encontrados {total} DTEs pendientes")
    
    resumen = {
        'total_procesados': 0,
        'exitosos': 0,
        'fallidos': 0,
        'saltados': 0,
        'resultados': []
    }
    
    for dte in dtes_pendientes:
        resumen['total_procesados'] += 1
        
        if solo_diagnostico:
            # Solo diagnosticar
            diagnostico = diagnosticar_dte(dte)
            resumen['resultados'].append({
                'dte_id': dte.id,
                'folio': dte.folio,
                'tipo': dte.tipo_dte,
                'diagnostico': diagnostico,
                'accion': 'DIAGNÓSTICO'
            })
            
            if diagnostico['es_valido_para_envio']:
                resumen['exitosos'] += 1
            else:
                resumen['saltados'] += 1
        else:
            # Enviar realmente
            logger.info(f"[REENVÍO] Procesando DTE {dte.tipo_dte} #{dte.folio} (ID: {dte.id})")
            
            resultado = enviar_dte_seguro(dte)
            
            resumen['resultados'].append({
                'dte_id': dte.id,
                'folio': dte.folio,
                'tipo': dte.tipo_dte,
                'resultado': resultado,
                'accion': 'ENVIADO' if resultado['success'] else 'FALLIDO'
            })
            
            if resultado['success']:
                resumen['exitosos'] += 1
                logger.info(f"[REENVÍO] ✅ DTE {dte.id} enviado exitosamente")
            else:
                resumen['fallidos'] += 1
                logger.warning(f"[REENVÍO] ❌ DTE {dte.id} falló: {resultado['error']}")
    
    logger.info(f"[REENVÍO] Proceso completado - Exitosos: {resumen['exitosos']}, Fallidos: {resumen['fallidos']}, Saltados: {resumen['saltados']}")
    
    return resumen
