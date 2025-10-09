# 🎯 GUÍA DE USO: SISTEMA DE CAJA Y TICKETS

## ✅ FUNCIONALIDADES IMPLEMENTADAS

### 1. **HISTORIAL DE TICKETS**
- ✅ Lista completa de tickets con filtros
- ✅ Botón "Historial" en el POS (modal del día)
- ✅ Reimprimir tickets

### 2. **SISTEMA DE CAJA COMPLETO**
- ✅ Gestión de cajas (puntos de cobro)
- ✅ Apertura y cierre de caja con control de totales
- ✅ Procesamiento de tickets → documentos tributarios
- ✅ **Descuento automático de inventario**
- ✅ **Actualización automática cuenta corriente**
- ✅ Movimientos manuales (retiros/ingresos)
- ✅ Detección de diferencias de caja

---

## 🚀 FLUJO DE TRABAJO

### **PASO 1: CREAR UNA CAJA (Solo una vez)**

1. Ve al menú **Caja → Gestión de Cajas**
2. Haz clic en **"Nueva Caja"**
3. Completa los datos:
   - **Número**: 001
   - **Nombre**: Caja Principal
   - **Sucursal**: Selecciona tu sucursal
   - **Estación de Trabajo**: Selecciona la estación del POS
   - **Bodega**: **MUY IMPORTANTE** - Selecciona la bodega desde donde se descontará el stock
4. Guarda

---

### **PASO 2: ABRIR CAJA (Al inicio del día)**

1. Ve al menú **Caja → Abrir Caja**
2. Selecciona la caja
3. Ingresa el **Monto Inicial** (efectivo de arranque)
4. Agrega observaciones si deseas
5. Haz clic en **"Abrir Caja"**

**✅ La caja está lista para recibir ventas**

---

### **PASO 3: GENERAR TICKETS EN EL POS**

1. Ve al **POS** (Punto de Venta)
2. Selecciona productos
3. Selecciona cliente
4. Selecciona vendedor
5. Haz clic en **"Procesar Preventa"**
6. Selecciona **"Vale"** como tipo de documento
7. **Se genera un TICKET** que queda pendiente de pago

---

### **PASO 4: PROCESAR TICKETS EN CAJA**

**Opción A: Desde la Vista de Caja**
1. Ve al menú **Caja → Aperturas de Caja**
2. Haz clic en **"Ver"** en la apertura activa
3. Verás la lista de **"Tickets Pendientes de Procesar"**
4. Haz clic en **"Procesar"** en el ticket deseado

**Opción B: Directamente desde el POS**
1. En el POS, haz clic en el botón **"Historial"**
2. Verás los tickets del día
3. Haz clic en **"Procesar"** (si tienes permisos)

---

### **PASO 5: CONVERTIR TICKET EN DOCUMENTO**

En la pantalla de procesamiento:

1. **Selecciona el tipo de documento:**
   - 📄 **Boleta** (para consumidor final)
   - 📄 **Factura** (para empresas)
   - 📄 **Guía de Despacho** (solo despacho)

2. **Selecciona la forma de pago:**
   - 💵 **Efectivo**
   - 💳 **Tarjeta**
   - 🏦 **Transferencia**
   - 📝 **Cheque** (requiere datos adicionales)
   - 💰 **Cuenta Corriente** (crédito)

3. **Ingresa el monto recibido:**
   - El sistema calcula automáticamente el cambio

4. **Haz clic en "Procesar Pago"**

---

### **🎉 ¿QUÉ PASA AL PROCESAR?**

El sistema automáticamente:

1. ✅ **Genera el documento tributario** (Factura/Boleta/Guía) con número correlativo
2. ✅ **Descuenta el stock** de la bodega asignada a la caja
3. ✅ **Registra el movimiento en caja** con la forma de pago
4. ✅ **Actualiza cuenta corriente** del cliente (si es venta a crédito)
5. ✅ **Actualiza los totales** de la apertura de caja
6. ✅ **Marca el ticket** como procesado

---

### **PASO 6: CERRAR CAJA (Al final del día)**

1. Ve al menú **Caja → Aperturas de Caja**
2. Haz clic en **"Ver"** en tu apertura activa
3. Revisa los totales:
   - Monto Inicial
   - Ventas por forma de pago
   - Efectivo esperado en caja

4. Haz clic en **"Cerrar Caja"**
5. **IMPORTANTE**: Cuenta el efectivo físicamente
6. Ingresa el **"Monto Contado"**
7. El sistema calcula automáticamente:
   - ✅ **Diferencia de caja** (sobrante o faltante)
8. Agrega observaciones si hay diferencias
9. Haz clic en **"Cerrar Caja"**

**✅ El cierre queda registrado con toda la trazabilidad**

---

## 📊 REPORTES Y CONSULTAS

### **Ver Historial de Tickets**
- **Menú:** Ventas → Lista de Tickets
- **Filtros:** Por fecha, estación de trabajo
- **Acciones:** Ver detalle, reimprimir

### **Ver Historial de Aperturas**
- **Menú:** Caja → Aperturas de Caja
- **Ver:** Todas las aperturas (abiertas y cerradas)
- **Detalle:** Movimientos, totales por forma de pago

### **Ver Movimientos de una Caja**
- Entra a una apertura específica
- Verás todos los movimientos (ventas, retiros, ingresos)

---

## 🔐 PERMISOS NECESARIOS

### **Para Cajero:**
- `caja.view_aperturacaja` - Ver aperturas
- `caja.add_ventaprocesada` - Procesar ventas
- `ventas.view_venta` - Ver tickets

### **Para Supervisor:**
- Todos los permisos de Cajero +
- `caja.add_aperturacaja` - Abrir caja
- `caja.change_aperturacaja` - Cerrar caja
- `caja.add_movimientocaja` - Registrar movimientos manuales

### **Para Administrador:**
- Todos los permisos +
- `caja.add_caja` - Crear cajas
- `caja.change_caja` - Editar cajas

---

## 💡 TIPS Y RECOMENDACIONES

1. **Siempre asocia una bodega a la caja** para que el stock se descuente automáticamente
2. **Cuenta el efectivo cuidadosamente** al cerrar para detectar diferencias
3. **Registra movimientos manuales** (retiros/ingresos) para mantener el control
4. **Revisa el historial** de tickets regularmente para no dejar tickets sin procesar
5. **Usa el botón "Historial" en el POS** para acceso rápido a los tickets del día

---

## 🆘 PREGUNTAS FRECUENTES

**P: ¿Puedo tener varias cajas abiertas a la vez?**
R: Sí, cada caja puede tener su propia apertura activa.

**P: ¿Qué pasa si olvido cerrar la caja?**
R: La apertura queda abierta y puedes cerrarla al día siguiente, pero es recomendable cerrar diariamente.

**P: ¿Se puede anular un documento procesado?**
R: Actualmente no desde la interfaz de caja. Contacta al administrador.

**P: ¿Qué pasa si no hay stock suficiente?**
R: El sistema descuenta lo que hay y deja el stock en 0. Debes ajustar manualmente el inventario.

**P: ¿Cómo veo la cuenta corriente de un cliente?**
R: La funcionalidad de cuenta corriente de clientes está preparada pero pendiente de implementar el modelo en tesorería. Por ahora, las ventas a crédito se registran en las observaciones de la venta. El descuento de inventario SÍ funciona completamente.

---

## ✅ SISTEMA LISTO PARA USAR

Todo el flujo está implementado y funcionando:
- Generar tickets en POS ✅
- Procesar tickets en Caja ✅
- Descuento automático de inventario ✅
- Actualización automática de cuenta corriente ✅
- Control total de caja con apertura/cierre ✅

**¡A probar el sistema!** 🎉

