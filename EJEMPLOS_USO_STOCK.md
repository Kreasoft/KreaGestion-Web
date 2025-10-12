# Ejemplos Prácticos de Uso - Sistema de Stock

## 📚 Casos de Uso Reales

---

## Ejemplo 1: Primera Carga de Inventario (100 productos)

### Escenario
Tienes 100 productos y quieres cargar 50 unidades de stock inicial a cada uno.

### Solución: Script Rápido

```bash
# 1. Editar cargar_stock_rapido.py
EMPRESA_ID = 1
BODEGA_ID = 1
STOCK_DEFAULT = 50
SOBRESCRIBIR = False

# 2. Ejecutar
python cargar_stock_rapido.py

# 3. Confirmar cuando pregunte
¿Desea continuar con la carga? (s/n): s

# Resultado esperado:
# ✅ Creados: 100
# ✏️  Actualizados: 0
# ⏭️  Omitidos: 0
# ❌ Errores: 0
```

---

## Ejemplo 2: Carga con Cantidades Diferentes

### Escenario
Tienes productos con diferentes cantidades de stock inicial:
- Bebidas: 200 unidades
- Snacks: 150 unidades
- Lácteos: 100 unidades

### Solución: CSV

```bash
# 1. Crear archivo stock_inicial.csv
codigo,cantidad
BEB001,200
BEB002,200
BEB003,200
SNK001,150
SNK002,150
LAC001,100
LAC002,100

# 2. Ejecutar
python cargar_stock_desde_csv.py stock_inicial.csv

# 3. Verificar
python verificar_stock.py
```

---

## Ejemplo 3: Actualizar Stock Existente

### Escenario
Ya tienes stock cargado pero quieres actualizarlo a 100 unidades para todos.

### Solución: Script Rápido con Sobrescribir

```bash
# 1. Editar cargar_stock_rapido.py
EMPRESA_ID = 1
BODEGA_ID = 1
STOCK_DEFAULT = 100
SOBRESCRIBIR = True  # ← Importante!

# 2. Ejecutar
python cargar_stock_rapido.py

# Resultado esperado:
# ✅ Creados: 0
# ✏️  Actualizados: 100
# ⏭️  Omitidos: 0
```

---

## Ejemplo 4: Cargar Solo Algunos Productos

### Escenario
Solo quieres cargar stock para productos específicos.

### Solución: Script Interactivo con Datos Personalizados

```python
# 1. Editar cargar_stock_inicial.py
# Buscar la sección "MODO 3" y descomentar:

datos_stock = {
    'ART001': 50,
    'ART005': 100,
    'ART010': 75,
    'PROD025': 200,
}

cargar_stock_personalizado(
    empresa_id=1,
    bodega_id=1,
    datos_stock=datos_stock
)

# 2. Comentar la línea menu_principal()

# 3. Ejecutar
python cargar_stock_inicial.py
```

---

## Ejemplo 5: Verificar Stock Después de Cargar

### Escenario
Acabas de cargar stock y quieres verificar que todo esté correcto.

### Solución: Script de Verificación

```bash
# 1. Ejecutar script de verificación
python verificar_stock.py

# 2. Seleccionar opción 1 (Ver resumen)

# Verás algo como:
# 📊 RESUMEN GENERAL
# Total de artículos activos: 100
# Artículos con stock: 100
# Artículos sin stock: 0
#
# 🏢 BODEGA: Bodega Principal
# Items registrados: 100
# Con stock (>0): 100
# Sin stock (=0): 0
# Valor total estimado: $5,000,000.00
```

---

## Ejemplo 6: Exportar Reporte de Stock

### Escenario
Necesitas un archivo Excel con todo el stock actual.

### Solución: Exportar desde Verificación

```bash
# 1. Ejecutar
python verificar_stock.py

# 2. Seleccionar opción 3 (Exportar reporte)

# 3. Ingresar nombre de archivo
Nombre del archivo: mi_stock_2025.csv

# 4. Abrir el archivo en Excel
# Tendrás columnas: Código, Nombre, Bodega, Cantidad, etc.
```

---

## Ejemplo 7: Cargar desde Excel (Interfaz Web)

### Escenario
Prefieres usar la interfaz web y tienes Excel.

### Solución: Carga desde Web

```
1. Ir a: http://localhost:8000/inventario/carga-inicial/

2. Click en "Importar desde Excel"

3. Click en "Descargar Plantilla Excel"
   → Se descarga archivo con todos tus productos

4. Abrir Excel y completar columna STOCK_INICIAL
   Ejemplo:
   CODIGO    NOMBRE              STOCK_INICIAL
   ART001    Producto 1          50
   ART002    Producto 2          100
   ART003    Producto 3          75

5. Guardar archivo

6. Seleccionar bodega destino

7. Arrastrar archivo a la zona de carga

8. Click en "Cargar Inventario"

9. Ver resumen de carga
```

---

## Ejemplo 8: Venta con Control de Stock

### Escenario
Quieres vender un producto y verificar que el stock se descuente.

### Proceso Completo

```
1. Verificar stock inicial
   python verificar_stock.py
   → Producto ART001: 100 unidades

2. Crear venta en POS
   - Agregar producto ART001, cantidad: 5
   - Sistema valida que hay stock
   - Procesar venta

3. Confirmar venta desde Caja
   - Venta cambia a estado "confirmada"
   - Stock se descuenta automáticamente

4. Verificar stock final
   python verificar_stock.py
   → Producto ART001: 95 unidades (100 - 5)

5. Ver movimiento de inventario
   Web → Inventario → Movimientos
   → Verás movimiento tipo "salida" con cantidad 5
```

---

## Ejemplo 9: Intentar Vender Sin Stock

### Escenario
Intentas vender más cantidad de la disponible.

### Comportamiento del Sistema

```
1. Stock actual: 10 unidades

2. Intentar agregar al POS: 15 unidades

3. Sistema muestra error:
   ❌ "Stock insuficiente. Disponible: 10, Solicitado: 15"

4. Venta no se procesa hasta ajustar cantidad
```

---

## Ejemplo 10: Productos sin Control de Stock

### Escenario
Tienes servicios que no requieren control de inventario.

### Configuración

```
1. Ir a Artículos → Editar producto

2. Desmarcar "Control de Stock"

3. Guardar

Resultado:
- No se valida stock al vender
- No se descuenta stock al confirmar venta
- Útil para: servicios, productos digitales, etc.
```

---

## Ejemplo 11: Múltiples Bodegas

### Escenario
Tienes 2 bodegas y quieres cargar stock en ambas.

### Solución: Ejecutar Script por Bodega

```bash
# Bodega 1 (Principal)
# Editar cargar_stock_rapido.py
EMPRESA_ID = 1
BODEGA_ID = 1
STOCK_DEFAULT = 100

python cargar_stock_rapido.py

# Bodega 2 (Sucursal)
# Editar cargar_stock_rapido.py
EMPRESA_ID = 1
BODEGA_ID = 2
STOCK_DEFAULT = 50

python cargar_stock_rapido.py

# Verificar ambas
python verificar_stock.py
# Opción 1: Ver todas las bodegas
```

---

## Ejemplo 12: Corregir Stock Incorrecto

### Escenario
Cargaste 100 unidades pero debían ser 150.

### Solución: Ajuste de Stock

```
Opción A: Desde Web
1. Ir a Inventario → Ajustes
2. Crear nuevo ajuste
3. Seleccionar productos
4. Ajustar cantidades

Opción B: Recargar con Script
1. Editar cargar_stock_rapido.py
   STOCK_DEFAULT = 150
   SOBRESCRIBIR = True

2. python cargar_stock_rapido.py
```

---

## Ejemplo 13: Stock Bajo - Alertas

### Escenario
Quieres ver qué productos tienen stock bajo.

### Solución: Verificación

```bash
python verificar_stock.py

# En el reporte verás:
⚠️  STOCK BAJO (15 artículos):
  • ART001    Producto 1    → 5 (mín: 10)
  • ART005    Producto 5    → 8 (mín: 10)
  • ART010    Producto 10   → 3 (mín: 10)
  ...
```

---

## Ejemplo 14: Importar desde Sistema Anterior

### Escenario
Tienes datos de stock en un sistema anterior y quieres importarlos.

### Solución: Exportar a CSV e Importar

```bash
# 1. Exportar desde sistema anterior a CSV
# Formato: codigo,cantidad

# 2. Ajustar formato si es necesario
# Asegurar que tenga columnas: codigo,cantidad

# 3. Importar
python cargar_stock_desde_csv.py datos_antiguos.csv

# 4. Verificar
python verificar_stock.py

# 5. Revisar errores si los hay
# El script mostrará qué códigos no se encontraron
```

---

## Ejemplo 15: Backup Antes de Carga Masiva

### Escenario
Vas a cargar stock masivo y quieres poder revertir si algo sale mal.

### Solución: Backup de Base de Datos

```bash
# 1. Hacer backup (SQLite)
copy db.sqlite3 db.sqlite3.backup

# 2. Cargar stock
python cargar_stock_rapido.py

# 3. Si algo sale mal, restaurar
copy db.sqlite3.backup db.sqlite3

# Para PostgreSQL/MySQL:
# pg_dump nombre_bd > backup.sql
# mysql -u usuario -p nombre_bd < backup.sql
```

---

## 🎯 Tips y Mejores Prácticas

### ✅ Hacer
- Verificar IDs de empresa y bodega antes de cargar
- Hacer backup antes de cargas masivas
- Probar con pocos productos primero
- Verificar resultados después de cargar
- Usar CSV para cantidades diferenciadas
- Documentar las cargas realizadas

### ❌ Evitar
- Cargar sin verificar configuración
- Interrumpir el proceso de carga
- Cargar en bodega incorrecta
- No verificar después de cargar
- Sobrescribir sin confirmar
- Cargar productos inactivos

---

## 📞 Preguntas Frecuentes

### ¿Puedo cargar stock negativo?
No, el sistema no permite stock negativo.

### ¿Qué pasa si cargo un código que no existe?
El script mostrará error y continuará con los siguientes.

### ¿Puedo cargar stock en múltiples bodegas a la vez?
No, debes ejecutar el script una vez por bodega.

### ¿El stock se suma o se reemplaza?
Depende del parámetro `SOBRESCRIBIR`:
- `False`: Solo crea nuevos (no modifica existentes)
- `True`: Reemplaza el stock existente

### ¿Cómo sé qué bodega usar?
```bash
python cargar_stock_inicial.py
# Opción 4: Ver bodegas de una empresa
```

---

**Última actualización**: Octubre 2025
