# Guía de Carga Inicial de Stock

Esta guía explica las diferentes formas de cargar stock inicial a los productos en GestionCloud.

## 📋 Opciones Disponibles

### 1. Interfaz Web (Recomendado para usuarios)
### 2. Script Interactivo (Recomendado para administradores)
### 3. Script Rápido (Para cargas masivas simples)

---

## 🌐 Opción 1: Interfaz Web

### Acceso
1. Ir a **Inventario** → **Carga Inicial**
2. URL: `http://localhost:8000/inventario/carga-inicial/`

### Métodos Disponibles

#### A) Importar desde Excel
1. **Descargar plantilla**
   - Click en "Descargar Plantilla Excel"
   - Se descarga un archivo con todos los productos

2. **Completar plantilla**
   - Columna `STOCK_INICIAL`: Cantidad a cargar
   - Columnas `STOCK_MINIMO` y `STOCK_MAXIMO`: Opcional

3. **Subir archivo**
   - Seleccionar bodega destino
   - Arrastrar archivo o hacer click para seleccionar
   - Click en "Cargar Inventario"

#### B) Edición Manual
1. Click en "Ir a Edición Manual"
2. Seleccionar bodega
3. Buscar productos y editar cantidades
4. Guardar cambios

**Ventajas:**
- ✅ Interfaz amigable
- ✅ No requiere conocimientos técnicos
- ✅ Validación en tiempo real
- ✅ Exporta plantilla con productos actuales

---

## 🖥️ Opción 2: Script Interactivo

### Archivo: `cargar_stock_inicial.py`

### Uso
```bash
python cargar_stock_inicial.py
```

### Características
- ✅ Menú interactivo
- ✅ Lista empresas y bodegas disponibles
- ✅ Carga masiva con cantidad uniforme
- ✅ Carga personalizada por producto
- ✅ Opción de sobrescribir stock existente

### Menú Principal
```
1. Cargar stock masivo (misma cantidad para todos)
2. Cargar stock personalizado (cantidad por artículo)
3. Ver empresas disponibles
4. Ver bodegas de una empresa
5. Salir
```

### Ejemplo: Carga Masiva
```
1. Seleccionar opción 1
2. Ingresar ID de empresa: 1
3. Ingresar ID de bodega: 1
4. Ingresar cantidad por defecto: 100
5. ¿Sobrescribir existente? n
6. Confirmar: s
```

### Ejemplo: Carga Personalizada
Editar el script y agregar:
```python
datos_stock = {
    'ART001': 50,
    'ART002': 100,
    'ART003': 75,
    'PROD001': 200,
}

cargar_stock_personalizado(
    empresa_id=1,
    bodega_id=1,
    datos_stock=datos_stock
)
```

**Ventajas:**
- ✅ Control total del proceso
- ✅ Puede procesar miles de productos
- ✅ Muestra progreso en tiempo real
- ✅ Resumen detallado de resultados

---

## ⚡ Opción 3: Script Rápido

### Archivo: `cargar_stock_rapido.py`

### Configuración
Editar las variables al inicio del archivo:
```python
EMPRESA_ID = 1          # ID de tu empresa
BODEGA_ID = 1           # ID de la bodega
STOCK_DEFAULT = 100     # Cantidad para todos los productos
SOBRESCRIBIR = False    # True = actualiza existentes
```

### Uso
```bash
python cargar_stock_rapido.py
```

### Proceso
1. Muestra configuración
2. Solicita confirmación
3. Procesa todos los productos
4. Muestra resumen

**Ventajas:**
- ✅ Muy rápido
- ✅ Configuración simple
- ✅ Ideal para cargas iniciales masivas
- ✅ Sin interacción durante el proceso

---

## 📊 Comparación de Métodos

| Característica | Web | Script Interactivo | Script Rápido |
|----------------|-----|-------------------|---------------|
| Facilidad de uso | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Velocidad | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Personalización | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| Requiere Excel | ✅ | ❌ | ❌ |
| Requiere terminal | ❌ | ✅ | ✅ |
| Carga masiva | ✅ | ✅ | ✅ |
| Carga selectiva | ✅ | ✅ | ❌ |

---

## 🔍 Verificar Carga

Después de cargar el stock, verificar en:

### 1. Lista de Stock
- Ir a **Inventario** → **Stock**
- Verificar cantidades por bodega

### 2. Movimientos de Inventario
- Ir a **Inventario** → **Movimientos**
- Filtrar por tipo "Entrada"
- Verificar movimientos creados

### 3. Desde Artículos
- Ir a **Artículos** → **Lista de Artículos**
- Ver columna "Stock Actual"

---

## ⚠️ Consideraciones Importantes

### Antes de Cargar
1. **Verificar Empresa**: Asegurarse de seleccionar la empresa correcta
2. **Verificar Bodega**: Confirmar que la bodega esté activa
3. **Backup**: Hacer respaldo de la base de datos (recomendado)
4. **Artículos Activos**: Solo se procesan artículos activos

### Durante la Carga
1. **No interrumpir**: Dejar que el proceso termine
2. **Revisar errores**: Anotar cualquier error mostrado
3. **Verificar progreso**: Observar el contador de procesados

### Después de Cargar
1. **Verificar totales**: Comparar con lo esperado
2. **Revisar movimientos**: Confirmar que se crearon correctamente
3. **Probar ventas**: Hacer una venta de prueba para verificar descuento de stock

---

## 🐛 Solución de Problemas

### Error: "Empresa no encontrada"
**Solución**: Verificar el ID de la empresa
```bash
python cargar_stock_inicial.py
# Seleccionar opción 3 para ver empresas
```

### Error: "Bodega no encontrada"
**Solución**: Verificar el ID de la bodega
```bash
python cargar_stock_inicial.py
# Seleccionar opción 4 para ver bodegas
```

### Error: "Artículo con código X no encontrado"
**Solución**: 
- Verificar que el código sea correcto
- Confirmar que el artículo esté activo
- Revisar que pertenezca a la empresa correcta

### Stock no se descuenta en ventas
**Solución**:
1. Verificar que el artículo tenga `control_stock = True`
2. Confirmar que la venta esté en estado "confirmada"
3. Revisar que exista stock en la bodega

---

## 📝 Ejemplos de Uso

### Ejemplo 1: Primera Carga (100 productos, stock 50)
```bash
# Opción recomendada: Script Rápido
1. Editar cargar_stock_rapido.py
   EMPRESA_ID = 1
   BODEGA_ID = 1
   STOCK_DEFAULT = 50
   SOBRESCRIBIR = False

2. Ejecutar:
   python cargar_stock_rapido.py

3. Confirmar: s
```

### Ejemplo 2: Actualizar Stock Existente
```bash
# Opción recomendada: Script Interactivo
1. python cargar_stock_inicial.py
2. Opción: 1
3. Empresa: 1
4. Bodega: 1
5. Stock: 100
6. Sobrescribir: s
7. Confirmar: s
```

### Ejemplo 3: Cargar Stock Diferenciado
```bash
# Opción recomendada: Web (Excel)
1. Descargar plantilla desde web
2. Editar columna STOCK_INICIAL con cantidades específicas
3. Subir archivo
```

---

## 🎯 Mejores Prácticas

1. **Hacer backup antes de cargas masivas**
2. **Probar primero con pocos productos**
3. **Usar Excel para cantidades diferenciadas**
4. **Usar script rápido para cantidades uniformes**
5. **Verificar siempre después de cargar**
6. **Documentar las cargas realizadas**

---

## 📞 Soporte

Si encuentra problemas:
1. Revisar logs del sistema
2. Verificar configuración de bodegas
3. Confirmar permisos de usuario
4. Contactar al administrador del sistema

---

## 🔄 Actualización de Stock

Para actualizar stock después de la carga inicial, usar:
- **Ajustes de Stock**: Para correcciones
- **Movimientos de Entrada**: Para compras
- **Movimientos de Salida**: Para ventas (automático)
- **Transferencias**: Para mover entre bodegas

---

**Última actualización**: Octubre 2025
**Versión**: 1.0
