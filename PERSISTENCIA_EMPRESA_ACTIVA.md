# ✅ PERSISTENCIA DE EMPRESA ACTIVA - MEJORADO

## 📋 Resumen

Se ha implementado un sistema robusto de **persistencia de la empresa activa** que mantiene la selección del usuario incluso después de cerrar el navegador, usando una combinación de **sesiones Django** y **cookies HTTP**.

---

## 🎯 **PROBLEMA RESUELTO**

### **Antes**:
```
❌ La empresa activa se perdía al cerrar el navegador
❌ SESSION_EXPIRE_AT_BROWSER_CLOSE = True
❌ SESSION_COOKIE_AGE = 3600 (1 hora)
❌ Solo se guardaba en sesión (volátil)
❌ No había fallback si la sesión expiraba
```

### **Ahora**:
```
✅ La empresa persiste 30 días
✅ SESSION_EXPIRE_AT_BROWSER_CLOSE = False
✅ SESSION_COOKIE_AGE = 30 días
✅ Doble almacenamiento: Sesión + Cookie
✅ Fallback automático entre fuentes
✅ Actualización en cada request
```

---

## 🔧 **CAMBIOS IMPLEMENTADOS**

### **1. Configuración de Sesiones (`settings.py`)**

```python
# ANTES (Problemático)
SESSION_COOKIE_AGE = 3600  # 1 hora
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # ❌ Se borra al cerrar navegador

# AHORA (Mejorado)
SESSION_COOKIE_AGE = 30 * 24 * 60 * 60  # 30 días
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # ✅ Persiste
SESSION_SAVE_EVERY_REQUEST = True  # Mantiene sesión activa
SESSION_COOKIE_HTTPONLY = True  # Seguridad
SESSION_COOKIE_SAMESITE = 'Lax'  # Protección CSRF
```

### **2. Middleware Mejorado (`usuarios/middleware.py`)**

#### **Sistema de Fuentes Múltiples**:

```python
# Orden de prioridad para obtener empresa:
1. request.session['empresa_activa_id']  # Sesión (prioritario)
2. request.COOKIES.get('empresa_activa_id')  # Cookie (fallback)
3. Empresa.objects.first()  # Primera disponible (última opción)
```

#### **Guardado Dual**:

```python
# Al procesar request:
request.session['empresa_activa_id'] = empresa.id
request.session.modified = True  # Forzar guardado

# Al enviar response:
response.set_cookie(
    'empresa_activa_id',
    empresa.id,
    max_age=30*24*60*60,  # 30 días
    httponly=True,  # Seguridad
    samesite='Lax'  # CSRF protection
)
```

### **3. Vista de Selección de Empresa Mejorada**

```python
# Guardar en sesión
request.session['empresa_activa_id'] = empresa.id
request.session.modified = True  # Forzar guardado

# Guardar en cookie
response = redirect('dashboard')
response.set_cookie(
    'empresa_activa_id',
    empresa.id,
    max_age=30*24*60*60,
    httponly=True,
    samesite='Lax'
)

return response
```

---

## 🎯 **FLUJO DE PERSISTENCIA**

### **Escenario 1: Usuario trabaja normalmente**

```
1. Usuario inicia sesión
2. Middleware carga empresa desde sesión
3. En cada request, se actualiza la cookie
4. Empresa persiste en memoria del servidor (sesión)
   Y en el navegador (cookie)
```

### **Escenario 2: Usuario cierra navegador**

```
1. Usuario cierra el navegador
2. La sesión permanece en el servidor (30 días)
3. La cookie permanece en el navegador (30 días)
4. Usuario abre el navegador nuevamente
5. Middleware lee la cookie
6. Restaura la sesión automáticamente
7. ✅ Usuario sigue con la misma empresa
```

### **Escenario 3: Sesión expira pero cookie existe**

```
1. La sesión del servidor expira
2. Middleware intenta leer sesión → NULL
3. Middleware lee cookie → empresa_id = X
4. Carga empresa desde cookie
5. Restaura sesión automáticamente
6. ✅ Continuidad sin interrupción
```

### **Escenario 4: Usuario cambia de empresa**

```
1. Usuario selecciona nueva empresa
2. Vista actualiza sesión
3. Vista actualiza cookie
4. Ambas fuentes sincronizadas
5. ✅ Cambio persistente
```

---

## 🔒 **SEGURIDAD IMPLEMENTADA**

### **Cookies Seguras**:

```python
httponly=True      # No accesible por JavaScript (XSS protection)
samesite='Lax'     # Protección contra CSRF
max_age=2592000    # Expira en 30 días (no permanente)
```

### **Sesiones Seguras**:

```python
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = True  # Actualiza en cada uso
```

### **Validación**:

```python
# Validar que la empresa existe
try:
    request.empresa = Empresa.objects.get(id=empresa_id)
except Empresa.DoesNotExist:
    # Fallback a primera empresa disponible
    request.empresa = Empresa.objects.first()
```

---

## 📊 **PRUEBAS Y CASOS DE USO**

### **Caso 1: Cierre y apertura de navegador**

```
✅ Usuario cierra Chrome
✅ Espera 5 minutos
✅ Abre Chrome nuevamente
✅ Hace login
✅ Empresa activa: La misma de antes
```

### **Caso 2: Cambio de navegador**

```
⚠️ Usuario trabaja en Chrome → Empresa A
⚠️ Abre Firefox
⚠️ Hace login
⚠️ Empresa activa: Primera disponible (cookies no compartidas)
⚠️ Selecciona Empresa A manualmente
✅ Ahora Firefox también tiene Empresa A persistente
```

### **Caso 3: Múltiples dispositivos**

```
⚠️ Usuario en PC → Empresa A
⚠️ Usuario en Laptop → Primera disponible
⚠️ Selecciona Empresa A en Laptop
✅ Cada dispositivo mantiene su propia selección
```

### **Caso 4: Expiración de 30 días**

```
⚠️ Usuario no accede por 31 días
⚠️ Cookie expira
⚠️ Sesión expira
⚠️ Hace login
⚠️ Sistema asigna primera empresa disponible
ℹ️ Debe seleccionar empresa nuevamente (normal después de 30 días)
```

---

## 🎨 **EXPERIENCIA DEL USUARIO**

### **Superusuario**:

```
1. Selecciona empresa A
2. Trabaja todo el día
3. Cierra navegador al terminar
4. Al día siguiente:
   → Abre navegador
   → Hace login
   → ✅ Sigue en empresa A (automático)
```

### **Usuario Normal**:

```
1. Tiene empresa asignada en su perfil
2. Siempre ve su empresa (fija)
3. No puede cambiar de empresa
4. Persistencia garantizada por perfil de usuario
```

---

## 📁 **ARCHIVOS MODIFICADOS**

```
✅ gestioncloud/settings.py
   - SESSION_COOKIE_AGE = 30 días
   - SESSION_EXPIRE_AT_BROWSER_CLOSE = False
   - SESSION_SAVE_EVERY_REQUEST = True
   - SESSION_COOKIE_HTTPONLY = True
   - SESSION_COOKIE_SAMESITE = 'Lax'

✅ usuarios/middleware.py
   - Lectura desde sesión
   - Lectura desde cookie (fallback)
   - Guardado dual (sesión + cookie)
   - Sincronización automática
   - Validación mejorada

✅ empresas/views.py
   - seleccionar_empresa() → Guardado dual
   - Mensaje mejorado con ✓

✅ PERSISTENCIA_EMPRESA_ACTIVA.md
   - Documentación completa
```

---

## 🎉 **BENEFICIOS**

✅ **Persistencia real**: 30 días sin pérdida
✅ **Redundancia**: Doble almacenamiento (sesión + cookie)
✅ **Fallback automático**: Si falla una fuente, usa la otra
✅ **Seguridad**: Cookies HTTP-only, SameSite
✅ **Experiencia mejorada**: No se pierde el contexto de trabajo
✅ **Sincronización**: Ambas fuentes siempre actualizadas
✅ **Escalable**: Funciona con múltiples usuarios y empresas

---

## 🔍 **DEBUGGING**

### **Ver empresa activa actual**:

```python
# En Django shell
python manage.py shell

from django.contrib.sessions.models import Session
from empresas.models import Empresa

# Ver todas las sesiones activas
for s in Session.objects.all():
    data = s.get_decoded()
    empresa_id = data.get('empresa_activa_id')
    if empresa_id:
        try:
            empresa = Empresa.objects.get(id=empresa_id)
            print(f"Sesión: {s.session_key[:10]}... → Empresa: {empresa.nombre}")
        except:
            print(f"Sesión: {s.session_key[:10]}... → Empresa ID: {empresa_id} (no existe)")
```

### **Limpiar sesiones expiradas**:

```bash
python manage.py clearsessions
```

### **Ver cookies en navegador**:

```
Chrome: DevTools → Application → Cookies → localhost
Firefox: DevTools → Storage → Cookies → localhost
Buscar: empresa_activa_id
```

---

## ⚙️ **CONFIGURACIÓN RECOMENDADA POR ENTORNO**

### **Desarrollo**:
```python
SESSION_COOKIE_AGE = 30 * 24 * 60 * 60  # 30 días
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True
```

### **Producción**:
```python
SESSION_COOKIE_AGE = 30 * 24 * 60 * 60  # 30 días
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SECURE = True  # Solo HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'  # Máxima seguridad
```

---

**Estado**: ✅ COMPLETADO E IMPLEMENTADO  
**Fecha**: 07/10/2025  
**Versión**: 2.0 (Persistencia Mejorada)

---

## 🚀 **PARA PROBAR**

1. **Cambiar de empresa**:
   ```
   → Empresas → Seleccionar Empresa
   → Elegir otra empresa
   → Verificar mensaje: "✓ Empresa cambiada a: XXX"
   ```

2. **Cerrar y abrir navegador**:
   ```
   → Cerrar completamente el navegador
   → Esperar 1 minuto
   → Abrir navegador
   → Hacer login
   → ✅ Debería mantener la empresa anterior
   ```

3. **Verificar en DevTools**:
   ```
   → F12 → Application → Cookies
   → Buscar: empresa_activa_id
   → Verificar: Valor = ID de empresa
   → Verificar: Expires = 30 días adelante
   ```

¡La empresa activa ahora es persistente y no se pierde! 🎉




















