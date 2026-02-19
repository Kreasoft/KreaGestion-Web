# SISTEMA DE ENVÍO SEGURO DE DTEs
## Guía de Uso

### 📋 DESCRIPCIÓN

Sistema robusto para enviar DTEs al SII/DTEBox con:
- ✅ Validación previa completa
- ✅ Protección contra envíos duplicados
- ✅ Manejo inteligente de errores
- ✅ Reintentos automáticos
- ✅ Logging detallado

---

## 🚀 USO BÁSICO

### 1. DIAGNÓSTICO (Ver qué DTEs están pendientes)

```bash
python manage.py reenviar_dtes --diagnostico
```

Esto te mostrará:
- Cuántos DTEs están pendientes
- Cuáles son válidos para enviar
- Cuáles tienen problemas y por qué

### 2. REENVIAR TODOS LOS DTEs PENDIENTES

```bash
python manage.py reenviar_dtes
```

Esto enviará automáticamente todos los DTEs que:
- Estén en estado 'generado', 'firmado' o 'error_envio'
- Pasen la validación previa
- Tengan CAF vigente

### 3. REENVIAR UN DTE ESPECÍFICO

```bash
python manage.py reenviar_dtes --dte-id 123
```

Reemplaza `123` con el ID del DTE que quieres reenviar.

---

## 🎯 OPCIONES AVANZADAS

### Limitar cantidad de DTEs

```bash
python manage.py reenviar_dtes --limite 10
```

Procesa solo los primeros 10 DTEs pendientes.

### Filtrar por empresa

```bash
python manage.py reenviar_dtes --empresa 77.117.239-3
```

Solo procesa DTEs de la empresa con ese RUT.

### Forzar envío (usar con cuidado)

```bash
python manage.py reenviar_dtes --dte-id 123 --forzar
```

Intenta enviar aunque falle la validación. **Usar solo si sabes lo que haces.**

---

## 📊 EJEMPLOS DE USO

### Ejemplo 1: Ver estado de DTEs pendientes

```bash
# Ver diagnóstico completo
python manage.py reenviar_dtes --diagnostico

# Salida esperada:
# ================================================================================
# SISTEMA DE REENVÍO SEGURO DE DTEs
# ================================================================================
# 
# 🎯 Modo: Reenvío masivo de DTEs pendientes
# ⚠️ Solo diagnóstico (no se enviarán DTEs)
# 
# ================================================================================
# RESUMEN
# ================================================================================
# Total procesados: 5
# ✅ Exitosos: 3
# ❌ Fallidos: 0
# ⚠️ Saltados: 2
# 
# DETALLES:
# 
# 1. ✅ DTE 33 #3220 - Válido: ✓
# 2. ✅ DTE 52 #54 - Válido: ✓
# 3. ❌ DTE 39 #229 - Válido: ✗
#    Error: El CAF está vencido (venció el 2025-12-01)
# ...
```

### Ejemplo 2: Reenviar DTEs con límite

```bash
# Reenviar solo 5 DTEs
python manage.py reenviar_dtes --limite 5

# Salida esperada:
# ================================================================================
# RESUMEN
# ================================================================================
# Total procesados: 5
# ✅ Exitosos: 4
# ❌ Fallidos: 1
# 
# DETALLES:
# 
# 1. ✅ DTE 33 #3220 - ✅ DTE enviado exitosamente - Track ID: DTEBOX-33-3220-...
# 2. ✅ DTE 52 #54 - ✅ DTE enviado exitosamente - Track ID: DTEBOX-52-54-...
# 3. ❌ DTE 39 #229 - ❌ Error de DTEBox: CAF vencido
# ...
```

### Ejemplo 3: Reenviar un DTE específico con diagnóstico previo

```bash
# Primero ver diagnóstico
python manage.py reenviar_dtes --dte-id 74 --diagnostico

# Si todo está OK, enviar
python manage.py reenviar_dtes --dte-id 74
```

---

## 🔍 VALIDACIONES QUE SE REALIZAN

Antes de enviar, el sistema verifica:

1. ✅ **Estado del DTE**: No esté ya enviado o anulado
2. ✅ **XML firmado**: Exista y sea válido
3. ✅ **CAF asignado**: Tenga un CAF asociado
4. ✅ **CAF vigente**: El CAF no esté vencido
5. ✅ **Folio en rango**: El folio esté dentro del rango del CAF
6. ✅ **Configuración empresa**: DTEBox esté habilitado y configurado
7. ✅ **Datos mínimos**: RUT receptor, monto total, etc.
8. ✅ **XML válido**: El XML sea parseable

---

## 🛡️ PROTECCIONES DE SEGURIDAD

### 1. No envíos duplicados
- Usa estado 'enviando' temporal
- Lock de base de datos (SELECT FOR UPDATE)
- Verifica estado antes de enviar

### 2. Manejo de errores
- Todos los errores se guardan en la BD
- Estado vuelve a 'error_envio' si falla
- Permite reintentos posteriores

### 3. Trazabilidad
- Logging completo de cada paso
- Track ID único para cada envío
- Fecha y hora de envío guardadas

---

## 📝 ESTADOS DE DTE

| Estado | Descripción | ¿Se puede reenviar? |
|--------|-------------|---------------------|
| `generado` | DTE creado pero no firmado | ❌ (debe firmarse primero) |
| `firmado` | DTE firmado pero no enviado | ✅ |
| `enviando` | En proceso de envío | ⏳ (esperar) |
| `enviado` | Enviado exitosamente | ❌ |
| `aceptado` | Aceptado por el SII | ❌ |
| `rechazado` | Rechazado por el SII | ⚠️ (revisar) |
| `error_envio` | Error al enviar | ✅ |
| `anulado` | Documento anulado | ❌ |

---

## 🆘 SOLUCIÓN DE PROBLEMAS

### Problema: "El CAF está vencido"
**Solución**: Cargar un nuevo CAF para ese tipo de documento.

```bash
python manage.py cargar_cafs
```

### Problema: "El DTE no tiene XML firmado"
**Solución**: Regenerar el DTE completo.

```bash
python manage.py regenerar_dte_completo --dte-id 123
```

### Problema: "DTEBox no está habilitado"
**Solución**: Verificar configuración de la empresa en el admin.

1. Ir a Admin → Empresas → Tu empresa
2. Verificar que "DTEBox Habilitado" esté marcado
3. Verificar URL y Auth Key

### Problema: "Error de conexión a DTEBox"
**Solución**: Verificar que DTEBox esté corriendo.

1. Abrir DTEBox en el navegador
2. Verificar que responda
3. Verificar la URL configurada

---

## 📞 SOPORTE

Si tienes problemas:

1. Ejecuta diagnóstico: `python manage.py reenviar_dtes --diagnostico`
2. Revisa los logs en la consola
3. Verifica el estado del DTE en el admin
4. Revisa la configuración de DTEBox

---

## ✅ CHECKLIST ANTES DE USAR

- [ ] DTEBox está corriendo
- [ ] Empresa tiene DTEBox habilitado
- [ ] URL y Auth Key configuradas
- [ ] CAFs vigentes cargados
- [ ] Servidor Django corriendo

---

**¡Listo para usar!** 🚀
