# 📦 Instrucciones para Carga Rápida de Stock

## Script de Carga Rápida

El script `cargar_stock_rapido.py` permite cargar stock inicial a todos los productos de forma automática y rápida.

### 🚀 Uso Rápido

1. **Editar configuración del script:**
   
   Abre el archivo `cargar_stock_rapido.py` y modifica estas líneas según tus necesidades:

   ```python
   EMPRESA_ID = 1          # ID de la empresa
   BODEGA_ID = 1           # ID de la bodega
   STOCK_DEFAULT = 100     # Cantidad de stock por defecto
   SOBRESCRIBIR = False    # True = sobrescribe, False = solo crea nuevos
   ```

2. **Ejecutar el script:**

   ```bash
   # Activar entorno virtual
   .venv\Scripts\activate

   # Ejecutar script
   python cargar_stock_rapido.py
   ```

3. **Confirmar la operación:**
   
   El script mostrará un resumen y pedirá confirmación antes de procesar.

### 📋 Ejemplo de Salida

```
======================================================================
CARGA RÁPIDA DE STOCK INICIAL
======================================================================

📦 Empresa: Mi Empresa
🏢 Bodega: Bodega Principal
📊 Stock por defecto: 100
♻️  Sobrescribir: No

📋 Total de artículos: 407

======================================================================
¿Desea continuar con la carga? (s/n): s

🔄 Procesando...

[10/407] Procesando... (Creados: 10, Actualizados: 0)
[20/407] Procesando... (Creados: 20, Actualizados: 0)
...

======================================================================
✅ CARGA COMPLETADA
======================================================================
✅ Creados: 407
✏️  Actualizados: 0
⏭️  Omitidos: 0
❌ Errores: 0
======================================================================
```

### ⚙️ Opciones de Configuración

- **EMPRESA_ID**: ID de la empresa (puedes verlo en la base de datos o admin de Django)
- **BODEGA_ID**: ID de la bodega donde se cargará el stock
- **STOCK_DEFAULT**: Cantidad de stock que se asignará a cada producto
- **SOBRESCRIBIR**: 
  - `False` (recomendado): Solo crea stock para productos que no tienen
  - `True`: Sobrescribe el stock existente con el valor por defecto

### 🔍 Cómo obtener los IDs

**Opción 1: Desde Django Admin**
1. Accede a `http://localhost:8000/admin/`
2. Ve a Empresas o Bodegas
3. Los IDs aparecen en la lista

**Opción 2: Desde Django Shell**
```bash
python manage.py shell
```

```python
from empresas.models import Empresa
from bodegas.models import Bodega

# Ver empresas
for e in Empresa.objects.all():
    print(f"ID: {e.id} - {e.nombre}")

# Ver bodegas
for b in Bodega.objects.all():
    print(f"ID: {b.id} - {b.nombre} (Empresa: {b.empresa.nombre})")
```

### ⚠️ Notas Importantes

1. **Backup**: Siempre haz un backup de la base de datos antes de ejecutar scripts masivos
2. **Transacciones**: El script usa transacciones atómicas, si hay un error se revierte todo
3. **Movimientos**: Se crean movimientos de inventario automáticamente para cada producto
4. **Permisos**: Asegúrate de tener permisos de administrador

### 🐛 Solución de Problemas

**Error: Empresa no encontrada**
- Verifica que el `EMPRESA_ID` sea correcto

**Error: Bodega no encontrada**
- Verifica que el `BODEGA_ID` sea correcto y pertenezca a la empresa

**Error: No hay artículos**
- Asegúrate de tener artículos activos en la empresa

---

## 🌐 Interfaz Web (Alternativa)

Si prefieres usar la interfaz web:

1. Ve a **Inventario → Carga Inicial**
2. Selecciona una de las opciones:
   - **Importar desde Excel**: Descarga plantilla, llénala y súbela
   - **Edición Manual**: Edita stock producto por producto con paginación

### ✅ Mejoras Implementadas

- ✅ **Paginación funcional**: 20 productos por página
- ✅ **Botón de copiar stock**: Ahora funciona correctamente
- ✅ **Búsqueda en tiempo real**: Filtra por código o nombre
- ✅ **Contador de cambios**: Muestra productos modificados

---

**Última actualización**: 11/10/2025
