# Guía de Manejo de Errores en GestionCloud

## Objetivo

Garantizar que **todos los errores** se muestren de forma **clara, específica y útil** para el usuario.

## Funciones Disponibles

### 1. `mostrar_errores_formulario(request, form, nombre_formulario)`

Muestra errores de un formulario de forma estructurada.

**Ejemplo de uso:**
```python
from utilidades.error_handling import mostrar_errores_formulario

if request.method == 'POST':
    form = MiFormulario(request.POST)
    if not form.is_valid():
        mostrar_errores_formulario(request, form, "Mi Formulario")
```

### 2. `mostrar_errores_multiples_formularios(request, formularios_dict)`

Muestra errores de múltiples formularios organizados.

**Ejemplo de uso:**
```python
from utilidades.error_handling import mostrar_errores_multiples_formularios

formularios = {
    'Formulario Principal': form1,
    'Configuración': form2,
    'Detalles': form3
}
mostrar_errores_multiples_formularios(request, formularios)
```

### 3. `validar_y_mostrar_errores(request, *formularios_con_nombres)`

Valida múltiples formularios y muestra errores automáticamente.

**Ejemplo de uso:**
```python
from utilidades.error_handling import validar_y_mostrar_errores

if request.method == 'POST':
    form1 = Form1(request.POST)
    form2 = Form2(request.POST)
    
    todos_validos = validar_y_mostrar_errores(
        request,
        ('Formulario Principal', form1),
        ('Configuración', form2)
    )
    
    if todos_validos:
        # Guardar datos
        pass
```

### 4. `manejar_error_guardado(request, error, contexto_adicional)`

Maneja errores al guardar datos mostrando mensajes según el tipo de error.

**Ejemplo de uso:**
```python
from utilidades.error_handling import manejar_error_guardado

try:
    objeto.save()
except Exception as e:
    manejar_error_guardado(request, e, {
        'accion': 'crear cliente',
        'campo_duplicado': 'RUT'  # Si es un error de duplicado
    })
```

## Tipos de Errores Detectados

La función `manejar_error_guardado` detecta automáticamente:

1. **Duplicados**: Errores de `unique` o `duplicate`
2. **Campos Obligatorios**: Errores de `not null` o `null`
3. **Referencias Inválidas**: Errores de `foreign key`
4. **Validación**: Errores de validación de datos
5. **Permisos**: Errores de permisos
6. **Integridad**: Errores de integridad de datos

## Ejemplo Completo

```python
from django.contrib import messages
from django.shortcuts import render, redirect
from utilidades.error_handling import (
    validar_y_mostrar_errores,
    manejar_error_guardado
)

def mi_vista_create(request):
    if request.method == 'POST':
        form1 = Form1(request.POST, request.FILES)
        form2 = Form2(request.POST)
        
        # Validar y mostrar errores automáticamente
        todos_validos = validar_y_mostrar_errores(
            request,
            ('Formulario Principal', form1),
            ('Configuración', form2)
        )
        
        if todos_validos:
            try:
                # Guardar datos
                objeto = form1.save(commit=False)
                objeto.usuario = request.user
                objeto.save()
                
                config = form2.save(commit=False)
                config.objeto = objeto
                config.save()
                
                messages.success(request, '✅ Registro creado exitosamente.')
                return redirect('mi_app:lista')
                
            except Exception as e:
                manejar_error_guardado(request, e, {
                    'accion': 'crear registro'
                })
    else:
        form1 = Form1()
        form2 = Form2()
    
    return render(request, 'mi_template.html', {
        'form1': form1,
        'form2': form2
    })
```

## Reglas de Mensajes

### Mensajes de Éxito
- ✅ Usar emoji de check verde
- Mensaje claro y específico
- Ejemplo: `✅ Empresa "Nombre" creada exitosamente.`

### Mensajes de Error
- ❌ Usar emoji de X roja para errores principales
- ⚠️ Usar emoji de advertencia para detalles
- 💡 Usar emoji de bombilla para sugerencias
- Estructura: Título del error → Detalles → Sugerencias

### Formato de Errores por Campo
```
❌ ERRORES EN [NOMBRE DEL FORMULARIO]:
   • Campo "Nombre del Campo": Descripción del error
   • Campo "Otro Campo": Otro error
```

## Buenas Prácticas

1. **Siempre validar formularios** antes de intentar guardar
2. **Mostrar errores específicos** por campo, no genéricos
3. **Usar try/except** al guardar datos
4. **Proporcionar contexto** en los mensajes de error
5. **Logging** de errores para debugging (ya incluido en las funciones)

## Integración en Vistas Existentes

Para actualizar una vista existente:

1. Importar las funciones:
```python
from utilidades.error_handling import validar_y_mostrar_errores, manejar_error_guardado
```

2. Reemplazar validaciones manuales:
```python
# ANTES:
if form.is_valid():
    # ...

# DESPUÉS:
if validar_y_mostrar_errores(request, ('Formulario', form)):
    # ...
```

3. Reemplazar manejo de excepciones:
```python
# ANTES:
except Exception as e:
    messages.error(request, f'Error: {str(e)}')

# DESPUÉS:
except Exception as e:
    manejar_error_guardado(request, e, {'accion': 'descripción'})
```





