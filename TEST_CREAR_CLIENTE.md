# 🧪 PRUEBA DE DIAGNÓSTICO - Crear Cliente

He creado un archivo de prueba simplificado para diagnosticar el problema.

## 📋 INSTRUCCIONES:

1. **Abre tu navegador** y ve a esta URL:
   ```
   http://127.0.0.1:8000/ventas/test-crear-cliente/
   ```

2. **Observa la página**:
   - Deberías ver "TEST: Crear Cliente"
   - Un botón azul "Crear Cliente"
   - Una sección "Consola de Logs" con mensajes

3. **Verifica los logs en la página**:
   Deberías ver estos mensajes:
   ```
   🔵 Página cargada
   🟢 DOMContentLoaded ejecutado
   ✅ Botón encontrado en el DOM
   ✅ Event listener agregado al botón
   🔵 Script ejecutado hasta el final
   ```

4. **Haz clic en "Crear Cliente"**:
   - Debería aparecer un alert: "✅ La función crearCliente() funciona!"
   - Luego un formulario de SweetAlert pidiendo un nombre
   - En los logs debería aparecer: "🔥 Click detectado en el botón!"

---

## 🎯 POSIBLES RESULTADOS:

### ✅ SI FUNCIONA EN ESTA PÁGINA DE PRUEBA:
Significa que el problema está en el POS específicamente, no en el navegador ni en las librerías.

### ❌ SI NO FUNCIONA NI EN ESTA PÁGINA:
Significa que hay un problema con:
- Las librerías (Bootstrap/SweetAlert2)
- El navegador
- Los permisos del usuario

---

## 📸 POR FAVOR ENVÍAME:

1. ¿Qué mensajes aparecen en la sección "Consola de Logs"?
2. ¿El botón responde al hacer clic?
3. ¿Aparece el alert y el formulario de SweetAlert?

---

**Primero prueba esto antes de continuar con el POS.**



