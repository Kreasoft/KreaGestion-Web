# 🔒 VALIDACIONES DE CAF - Sistema de Control de Duplicados

## ✅ Implementado: Control Automático al Cargar CAF

El sistema ahora **valida automáticamente** cada CAF antes de permitir su carga, cortando el problema de raíz.

---

## 🛡️ Validaciones Implementadas

### 1. **CAF Duplicado entre Sucursales**
**Problema**: El mismo archivo CAF no puede usarse en múltiples sucursales.

**Validación**: 
- Genera un hash SHA-256 del contenido del CAF
- Compara con todos los CAFs existentes de la empresa
- **BLOQUEA** si encuentra un CAF idéntico en otra sucursal

**Mensaje de Error**:
```
ESTE ARCHIVO CAF YA FUE CARGADO ANTERIORMENTE.

Ya existe en:
  - Sucursal: Casa Matriz
  - Tipo: Factura Electrónica
  - Rango: 47-61
  - Estado: Activo

NO SE PUEDE CARGAR EL MISMO CAF EN MULTIPLES SUCURSALES.
Cada sucursal debe tener sus propios CAFs con rangos exclusivos.
```

---

### 2. **Rangos Solapados en la Misma Sucursal**
**Problema**: Dos CAFs no pueden tener rangos de folios que se solapen en la misma sucursal.

**Validación**:
- Verifica que no haya solapamiento de rangos con CAFs activos o agotados
- Solapamiento se detecta si:
  - El inicio del nuevo CAF está dentro del rango existente, O
  - El fin del nuevo CAF está dentro del rango existente, O
  - El nuevo CAF contiene completamente al existente

**Mensaje de Error**:
```
CONFLICTO DE RANGOS DE FOLIOS.

El rango 52-71 se solapa con un CAF existente:
  - CAF ID: 6
  - Rango: 47-61
  - Estado: Activo
  - Sucursal: Casa Matriz

LOS RANGOS DE FOLIOS NO PUEDEN SOLAPARSE EN LA MISMA SUCURSAL.
Solucion: Usar un rango diferente o anular el CAF anterior.
```

---

### 3. **Advertencia: Rangos Duplicados en Sucursales Distintas**
**Comportamiento**: El sistema permite técnicamente cargar rangos duplicados en sucursales diferentes SI son archivos CAF distintos (por ejemplo, CAFs obtenidos del SII para diferentes sucursales con el mismo rango).

**Advertencia en Consola**:
```
[ADVERTENCIA] El rango 47-61 ya existe en otra sucursal (Casa Matriz)
             Esto es técnicamente permitido si son CAFs diferentes del SII, 
             pero puede causar confusión.
```

---

## 🔧 Implementación Técnica

### Archivo: `facturacion_electronica/models.py`

```python
def validar_caf_unico(self):
    """
    Valida que el CAF no esté duplicado.
    
    Validaciones:
    1. El mismo contenido XML no puede cargarse dos veces
    2. Los rangos de folios no pueden solaparse en la misma sucursal
    
    Returns:
        tuple: (es_valido: bool, mensaje_error: str)
    """
    # ... código de validación ...

def save(self, *args, **kwargs):
    """Override save para ejecutar validaciones antes de guardar"""
    if not self.pk or 'contenido_caf' in kwargs.get('update_fields', []):
        es_valido, mensaje_error = self.validar_caf_unico()
        if not es_valido:
            from django.core.exceptions import ValidationError
            raise ValidationError(mensaje_error)
    
    super().save(*args, **kwargs)
```

### Archivos Modificados:
1. **`facturacion_electronica/models.py`**:
   - Método `validar_caf_unico()`: Lógica de validación
   - Override `save()`: Ejecuta validaciones automáticamente

2. **`facturacion_electronica/views_caf.py`**:
   - `cargar_caf()`: Captura `ValidationError` y muestra mensaje al usuario

3. **`facturacion_electronica/views.py`**:
   - `caf_create()`: Captura `ValidationError` y muestra mensaje al usuario

---

## ✅ Pruebas Realizadas

### ✔️ Prueba 1: CAF Duplicado
- **Acción**: Intentar cargar el mismo CAF en una sucursal diferente
- **Resultado**: ✅ BLOQUEADO correctamente
- **Mensaje**: Se muestra el mensaje de error con detalles del CAF existente

### ✔️ Prueba 2: Rangos Solapados
- **Acción**: Intentar cargar CAF con rango 52-71 cuando existe CAF 47-61
- **Resultado**: ✅ BLOQUEADO correctamente
- **Mensaje**: Se muestra el conflicto de rangos con solución sugerida

### ✔️ Prueba 3: CAF Válido
- **Acción**: Cargar CAF con rango 62-81 (después del rango 47-61)
- **Resultado**: ✅ PERMITIDO correctamente
- **Comportamiento**: CAF se guarda exitosamente

---

## 📋 Flujo de Usuario

1. **Usuario carga un archivo CAF**
   - Selecciona sucursal
   - Selecciona tipo de documento
   - Sube el archivo XML

2. **Sistema valida automáticamente**
   - Verifica que no sea duplicado
   - Verifica que el rango no se solape
   - Genera hash del contenido

3. **Resultado**
   - ✅ **Si es válido**: CAF se guarda y se muestra mensaje de éxito
   - ❌ **Si no es válido**: Se muestra mensaje de error claro y NO se guarda

---

## 🎯 Beneficios

1. **Prevención Automática**: No requiere acción manual del usuario
2. **Mensajes Claros**: El usuario sabe exactamente qué está mal
3. **Protección del SII**: Evita problemas con folios duplicados
4. **Integridad de Datos**: Garantiza que cada sucursal tenga sus propios CAFs

---

## 🔍 Casos de Uso

### ❌ Caso Rechazado 1
```
Usuario intenta cargar el mismo CAF.xml en:
- Sucursal A (ya existe)
- Sucursal B (intento de carga)

RESULTADO: BLOQUEADO
RAZÓN: Mismo contenido CAF detectado
```

### ❌ Caso Rechazado 2
```
Sucursal A tiene:
- CAF con rango 1-100

Usuario intenta cargar en Sucursal A:
- CAF con rango 50-150

RESULTADO: BLOQUEADO
RAZÓN: Solapamiento de rangos (50-100)
```

### ✅ Caso Permitido
```
Sucursal A tiene:
- CAF con rango 1-100

Usuario carga en Sucursal A:
- CAF con rango 101-200

RESULTADO: PERMITIDO
RAZÓN: Rangos no se solapan
```

---

## 🚨 Nota Importante

Las validaciones se ejecutan **ANTES** de guardar el CAF en la base de datos, por lo que:
- No se crean registros inválidos
- No hay necesidad de limpieza posterior
- El sistema mantiene su integridad automáticamente

---

**Fecha de implementación**: 2025-12-27  
**Versión**: 1.0  
**Estado**: ✅ Implementado y probado


