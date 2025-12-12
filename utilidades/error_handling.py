"""
Utilidades para manejo de errores consistente en toda la aplicación
"""
from django.contrib import messages
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

# Configurar logging para que muestre los mensajes
logging.basicConfig(level=logging.INFO)


def mostrar_errores_formulario(request, form, nombre_formulario="Formulario"):
    """
    Muestra errores de un formulario de forma clara y estructurada
    
    Args:
        request: HttpRequest object
        form: Form instance con errores
        nombre_formulario: Nombre descriptivo del formulario
    """
    if not form.is_valid():
        logger.warning(f"Formulario '{nombre_formulario}' tiene errores: {form.errors}")
        
        # Contar errores para mostrar un resumen
        total_errores = sum(len(errors) for field, errors in form.errors.items() if field != '__all__')
        total_errores += len(form.non_field_errors())
        
        # Mensaje principal con resumen
        if total_errores > 0:
            messages.error(request, f'❌ ERRORES EN {nombre_formulario.upper()}: Se encontraron {total_errores} error(es)')
        
        # Errores generales del formulario
        if form.non_field_errors():
            for error in form.non_field_errors():
                messages.error(request, f'   • {error}')
        
        # Errores por campo (mostrar solo los primeros 10 para no saturar)
        errores_mostrados = 0
        max_errores_a_mostrar = 10
        
        for field_name, error_list in form.errors.items():
            if field_name == '__all__':
                continue
            
            if errores_mostrados >= max_errores_a_mostrar:
                errores_restantes = total_errores - errores_mostrados
                messages.warning(request, f'   ... y {errores_restantes} error(es) más. Revise todos los campos marcados en rojo.')
                break
            
            # Obtener el label del campo si existe
            field = form.fields.get(field_name) if hasattr(form, 'fields') else None
            field_label = getattr(field, 'label', None) if field else None
            
            # Si no hay label, formatear el nombre del campo
            if not field_label:
                field_label = field_name.replace('_', ' ').title()
            
            # Mostrar cada error del campo
            for error in error_list:
                if errores_mostrados < max_errores_a_mostrar:
                    messages.error(request, f'   • Campo "{field_label}": {error}')
                    errores_mostrados += 1
        
        # Verificar que los mensajes se agregaron
        from django.contrib.messages import get_messages
        mensajes_agregados = list(get_messages(request))
        logger.info(f"Mensajes agregados para '{nombre_formulario}': {len(mensajes_agregados)} mensajes")


def mostrar_errores_multiples_formularios(request, formularios_dict):
    """
    Muestra errores de múltiples formularios de forma organizada
    
    Args:
        request: HttpRequest object
        formularios_dict: Diccionario con nombre_formulario: form_instance
    """
    for nombre, form in formularios_dict.items():
        if not form.is_valid():
            mostrar_errores_formulario(request, form, nombre)


def manejar_error_guardado(request, error, contexto_adicional=None):
    """
    Maneja errores al guardar datos mostrando mensajes claros según el tipo de error
    
    Args:
        request: HttpRequest object
        error: Exception capturada
        contexto_adicional: Diccionario con información adicional del contexto
    """
    error_str = str(error).lower()
    mensaje_base = f'❌ ERROR AL GUARDAR: {str(error)}'
    
    # Detectar tipo de error común
    if 'duplicate' in error_str or 'unique' in error_str or 'ya existe' in error_str:
        messages.error(request, mensaje_base)
        messages.warning(request, '⚠️ DUPLICADO: Ya existe un registro con estos datos únicos.')
        if contexto_adicional and 'campo_duplicado' in contexto_adicional:
            messages.info(request, f'💡 El campo "{contexto_adicional["campo_duplicado"]}" ya está en uso.')
    
    elif 'not null' in error_str or 'null' in error_str or 'requerido' in error_str:
        messages.error(request, mensaje_base)
        messages.warning(request, '⚠️ CAMPOS OBLIGATORIOS: Faltan campos requeridos.')
        messages.info(request, '💡 Por favor, complete todos los campos marcados como obligatorios (*).')
    
    elif 'foreign key' in error_str or 'referencia' in error_str:
        messages.error(request, mensaje_base)
        messages.warning(request, '⚠️ REFERENCIA INVÁLIDA: Los datos relacionados no son válidos.')
        messages.info(request, '💡 Verifique que todos los datos relacionados existan y sean correctos.')
    
    elif 'validation' in error_str or 'validación' in error_str:
        messages.error(request, mensaje_base)
        messages.warning(request, '⚠️ VALIDACIÓN: Los datos no cumplen con las reglas de validación.')
    
    elif 'permission' in error_str or 'permiso' in error_str or 'denied' in error_str:
        messages.error(request, mensaje_base)
        messages.warning(request, '⚠️ PERMISOS: No tiene permisos para realizar esta acción.')
    
    elif 'integrity' in error_str or 'integridad' in error_str:
        messages.error(request, mensaje_base)
        messages.warning(request, '⚠️ INTEGRIDAD DE DATOS: Error en la integridad de los datos.')
        messages.info(request, '💡 Verifique que no haya conflictos con datos existentes.')
    
    else:
        # Error genérico
        messages.error(request, mensaje_base)
        messages.warning(request, '⚠️ Por favor, verifique los datos e intente nuevamente.')
        if contexto_adicional and 'accion' in contexto_adicional:
            messages.info(request, f'💡 Acción: {contexto_adicional["accion"]}')
    
    # Log del error completo para debugging
    logger.exception(f"Error al guardar: {error}", exc_info=error)


def validar_y_mostrar_errores(request, *formularios_con_nombres):
    """
    Valida múltiples formularios y muestra errores de forma clara
    
    Args:
        request: HttpRequest object
        *formularios_con_nombres: Tuplas de (nombre_formulario, form_instance)
    
    Returns:
        bool: True si todos los formularios son válidos, False en caso contrario
    """
    todos_validos = True
    formularios_dict = {}
    
    logger.info("=== VALIDANDO FORMULARIOS ===")
    for nombre, form in formularios_con_nombres:
        formularios_dict[nombre] = form
        es_valido = form.is_valid()
        logger.info(f"Formulario '{nombre}': {'VÁLIDO' if es_valido else 'INVÁLIDO'}")
        if not es_valido:
            todos_validos = False
            logger.error(f"Errores en '{nombre}': {form.errors}")
    
    if not todos_validos:
        logger.warning("Hay formularios inválidos, mostrando errores...")
        mostrar_errores_multiples_formularios(request, formularios_dict)
        # Asegurar que al menos hay un mensaje de error
        if not messages.get_messages(request):
            messages.error(request, '❌ Por favor, corrija los errores en el formulario.')
    else:
        logger.info("Todos los formularios son válidos")
    
    return todos_validos


