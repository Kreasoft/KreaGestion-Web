# ✅ CONTROL DE VIGENCIA DE CAF - IMPLEMENTADO

## 🎯 **PROBLEMA RESUELTO:**

Los archivos CAF del SII tienen una **vigencia de 6 meses** desde la fecha de autorización. Si se emiten documentos con un CAF vencido, esos documentos **quedan nulos y no son válidos ante el SII**.

## ✅ **SOLUCIÓN IMPLEMENTADA:**

---

### **1. MÉTODOS EN EL MODELO `ArchivoCAF`**

#### **`esta_vigente()`**
```python
def esta_vigente(self):
    """Verifica si el CAF está dentro de los 6 meses de vigencia"""
    fecha_vencimiento = self.fecha_autorizacion + timedelta(days=180)
    return hoy <= fecha_vencimiento
```

#### **`dias_para_vencer()`**
```python
def dias_para_vencer(self):
    """Retorna cuántos días faltan para el vencimiento"""
    fecha_vencimiento = self.fecha_autorizacion + timedelta(days=180)
    return (fecha_vencimiento - hoy).days
```

#### **`fecha_vencimiento()`**
```python
def fecha_vencimiento(self):
    """Retorna la fecha exacta de vencimiento"""
    return self.fecha_autorizacion + timedelta(days=180)
```

#### **`verificar_vencimiento()`**
```python
def verificar_vencimiento(self):
    """
    Marca automáticamente el CAF como 'vencido' si pasó la fecha
    Retorna True si está vigente, False si venció
    """
```

---

### **2. VALIDACIÓN AUTOMÁTICA AL ASIGNAR FOLIOS**

En `facturacion_electronica/services.py` → `FolioService.obtener_siguiente_folio()`:

```python
for caf in cafs_activos:
    # VERIFICAR VIGENCIA DEL CAF
    if not caf.esta_vigente():
        print(f"⚠️ CAF vencido: {caf.tipo_documento}")
        caf.estado = 'vencido'
        caf.save()
        continue  # Pasar al siguiente CAF
    
    # Solo si está vigente, asignar folio
    if caf.folios_disponibles() > 0:
        folio = caf.obtener_siguiente_folio()
        return folio, caf
```

**✅ Beneficio:** El sistema **NUNCA asignará folios de CAFs vencidos**

---

### **3. ALERTAS VISUALES EN LA INTERFAZ**

#### **Lista de CAF** (`/facturacion-electronica/caf/`)

**Columna "Vigencia":**
- 🟢 Verde (>60 días): "✓ 120 días"
- 🔵 Azul (30-60 días): "⏰ 45 días"  
- 🟡 Amarillo (≤30 días): "⚠ 15 días - Vence: 15/04/2025"
- 🔴 Rojo (vencido): "✗ VENCIDO - Venció: 01/04/2025"

**Alertas en la parte superior:**
```
⚠️ ¡Atención! El CAF de Boleta Electrónica (folios 1-100) vence en 15 días (15/04/2025).
   Se recomienda solicitar un nuevo CAF al SII.

❌ ¡CAF Vencido! El CAF de Factura Electrónica (folios 1-50) venció el 01/04/2025.
   No se pueden emitir documentos con este CAF.
```

---

### **4. COMANDO DE VERIFICACIÓN AUTOMÁTICA**

**Comando:** `python manage.py verificar_vigencia_caf`

**Funcionalidades:**
- ✅ Revisa todos los CAFs activos
- ✅ Calcula días para vencimiento
- ✅ Marca automáticamente como "vencido" los que pasaron los 6 meses
- ✅ Genera alertas por nivel de criticidad
- ✅ Puede filtrarse por empresa específica

**Ejemplo de uso:**
```bash
# Verificar todos los CAFs
python manage.py verificar_vigencia_caf

# Verificar solo una empresa
python manage.py verificar_vigencia_caf --empresa 1
```

**Output:**
```
======================================================================
VERIFICACIÓN DE VIGENCIA DE CAF
======================================================================

Total de CAFs activos: 5

CRITICO (<=30 dias): Boleta Electrónica (Folios 1-100)
   Empresa: Kreasoft spa
   Dias restantes: 15
   Vence: 2025-04-15
   ACCION REQUERIDA: Solicitar nuevo CAF al SII

ADVERTENCIA (<=60 dias): Factura Electrónica (Folios 1-50)
   Empresa: Kreasoft spa
   Dias restantes: 45
   Vence: 2025-05-15

======================================================================
RESUMEN:
======================================================================
OK Vigentes (>60 dias): 3
ATENCION Por vencer (30-60 dias): 1
CRITICO Por vencer (<=30 dias): 1
VENCIDO Marcados como vencidos: 0

URGENTE! Hay 1 CAF(s) que vencen en menos de 30 dias
Se recomienda solicitar nuevos CAF al SII INMEDIATAMENTE
======================================================================
```

---

### **5. AUTOMATIZACIÓN CON CRON**

**Recomendación:** Ejecutar el comando diariamente

**Linux/Mac (crontab):**
```bash
# Ejecutar diariamente a las 8:00 AM
0 8 * * * cd /ruta/proyecto && python manage.py verificar_vigencia_caf
```

**Windows (Task Scheduler):**
```
Programa: python.exe
Argumentos: manage.py verificar_vigencia_caf
Directorio: C:\PROJECTOS-WEB\GestionCloud
Periodicidad: Diaria a las 8:00 AM
```

---

## 🔒 **PROTECCIONES IMPLEMENTADAS:**

### **1. Imposible Usar CAF Vencido**
```python
# Al intentar obtener folio de CAF vencido:
if not caf.esta_vigente():
    caf.estado = 'vencido'
    caf.save()
    continue  # NO se usa este CAF
```

### **2. Alertas Tempranas**
- **60 días antes:** Advertencia azul
- **30 días antes:** Alerta amarilla crítica
- **0 días (vencido):** Error rojo + bloqueo

### **3. Estado Automático**
```python
# Estados del CAF:
'activo'   → CAF vigente y con folios disponibles
'agotado'  → Todos los folios usados
'vencido'  → Pasó la fecha de vencimiento (6 meses)
'anulado'  → Anulado manualmente
```

---

## 📊 **CÁLCULO DE VIGENCIA:**

```
Fecha Autorización: 06/10/2024
+ 180 días (6 meses)
= Fecha Vencimiento: 04/04/2025

Hoy: 01/04/2025
Días restantes: 3 días → CRÍTICO ⚠️

Hoy: 05/04/2025
Días restantes: 0 → VENCIDO ❌
```

---

## 🎯 **FLUJO COMPLETO:**

### **Escenario 1: CAF Vigente**
```
1. Usuario procesa venta
2. Sistema busca CAF activo
3. Sistema verifica: esta_vigente() → TRUE ✅
4. Sistema asigna folio
5. DTE generado correctamente
```

### **Escenario 2: CAF Vencido**
```
1. Usuario procesa venta
2. Sistema busca CAF activo
3. Sistema verifica: esta_vigente() → FALSE ❌
4. Sistema marca CAF como 'vencido'
5. Sistema busca siguiente CAF
6. Si no hay otro CAF: ERROR "No hay folios disponibles"
```

### **Escenario 3: CAF Por Vencer**
```
1. Admin abre lista de CAFs
2. Ve alerta: "⚠️ CAF vence en 15 días"
3. Admin solicita nuevo CAF al SII
4. Admin carga nuevo CAF
5. Sistema usa automáticamente el más antiguo primero
```

---

## 📝 **ARCHIVOS MODIFICADOS:**

```
✅ facturacion_electronica/models.py
   - esta_vigente()
   - dias_para_vencer()
   - fecha_vencimiento()
   - verificar_vencimiento()

✅ facturacion_electronica/services.py
   - Validación de vigencia en obtener_siguiente_folio()

✅ facturacion_electronica/templates/facturacion_electronica/caf_list.html
   - Columna "Vigencia" con códigos de color
   - Alertas en la parte superior

✅ facturacion_electronica/management/commands/verificar_vigencia_caf.py
   - Comando de verificación automática
```

---

## 🚀 **CÓMO USAR:**

### **1. Monitoreo Visual**
```
Ve a: http://127.0.0.1:8000/facturacion-electronica/caf/

Verás:
- Días restantes para cada CAF
- Fecha de vencimiento
- Alertas de CAFs críticos
- Estado visual por colores
```

### **2. Verificación Manual**
```bash
python manage.py verificar_vigencia_caf
```

### **3. Verificación Automática**
```
Configura tarea programada (cron/Task Scheduler)
para ejecutar diariamente
```

---

## ⚠️ **RECOMENDACIONES:**

1. **Solicitar CAF con anticipación:** 60 días antes del vencimiento
2. **Mantener CAF de respaldo:** Siempre tener al menos 2 CAFs activos
3. **Monitorear semanalmente:** Revisar la lista de CAFs cada semana
4. **Automatizar verificación:** Configurar el comando en cron/Task Scheduler
5. **No usar certificados vencidos:** El sistema los bloqueará automáticamente

---

## ✅ **ESTADO FINAL:**

| Componente | Estado |
|------------|--------|
| Validación de vigencia | ✅ Funcional |
| Cálculo de días restantes | ✅ Funcional |
| Bloqueo de CAFs vencidos | ✅ Funcional |
| Alertas visuales | ✅ Funcional |
| Comando de verificación | ✅ Funcional |
| Protección automática | ✅ Funcional |

---

**✅ EL SISTEMA AHORA CONTROLA AUTOMÁTICAMENTE LA VIGENCIA DE LOS CAF**

**No se podrán emitir documentos con CAFs vencidos, garantizando la validez de los DTEs ante el SII.**

**Última actualización:** 06/10/2025 - 23:05




















