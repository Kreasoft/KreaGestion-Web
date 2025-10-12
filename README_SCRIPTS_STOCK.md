# Scripts de Carga de Stock Inicial

## 🚀 Inicio Rápido

### Opción 1: Script Rápido (Más Simple)
```bash
# 1. Editar cargar_stock_rapido.py
#    Cambiar: EMPRESA_ID, BODEGA_ID, STOCK_DEFAULT

# 2. Ejecutar
python cargar_stock_rapido.py
```

### Opción 2: Script Interactivo (Más Control)
```bash
python cargar_stock_inicial.py
# Seguir menú interactivo
```

### Opción 3: Desde CSV
```bash
# 1. Crear archivo stock.csv:
#    codigo,cantidad
#    ART001,100
#    ART002,50

# 2. Ejecutar
python cargar_stock_desde_csv.py stock.csv
```

---

## 📂 Archivos Disponibles

| Archivo | Descripción | Uso |
|---------|-------------|-----|
| `cargar_stock_rapido.py` | Carga rápida con cantidad uniforme | Inicial masiva |
| `cargar_stock_inicial.py` | Menú interactivo completo | Control total |
| `cargar_stock_desde_csv.py` | Carga desde archivo CSV | Cantidades variables |
| `GUIA_CARGA_STOCK_INICIAL.md` | Guía completa | Referencia |

---

## 💡 Ejemplos Comunes

### Cargar 100 unidades a todos los productos
```bash
# Editar cargar_stock_rapido.py
STOCK_DEFAULT = 100

# Ejecutar
python cargar_stock_rapido.py
```

### Cargar cantidades específicas
```bash
# Crear stock.csv
echo "codigo,cantidad" > stock.csv
echo "ART001,50" >> stock.csv
echo "ART002,100" >> stock.csv

# Ejecutar
python cargar_stock_desde_csv.py stock.csv
```

### Ver empresas y bodegas disponibles
```bash
python cargar_stock_inicial.py
# Opción 3: Ver empresas
# Opción 4: Ver bodegas
```

---

## ⚠️ Importante

1. **Hacer backup** antes de cargas masivas
2. **Verificar IDs** de empresa y bodega
3. **Probar primero** con pocos productos
4. **Revisar resultados** después de cargar

---

## 🔍 Verificar Carga

Después de ejecutar, verificar en:
- Web: `Inventario → Stock`
- Web: `Inventario → Movimientos`

---

## 📞 Ayuda

Ver guía completa: `GUIA_CARGA_STOCK_INICIAL.md`
