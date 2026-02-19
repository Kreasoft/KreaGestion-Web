# Estándar de Diseño Terroso - GestionCloud

## 📋 Descripción General

Este documento define el estándar visual y de diseño para todas las interfaces del sistema GestionCloud. El objetivo es mantener consistencia visual en todo el sistema usando una paleta de colores terrosos profesionales.

## 🎨 Paleta de Colores Principal

### Colores Base
- **Fondo Principal**: `linear-gradient(135deg, #FAFAF8 0%, #F5F1E8 100%)`
- **Header/Banner**: `linear-gradient(135deg, #F5F1E8 0%, #E8DCC8 100%)`
- **Texto Primario**: `#6F5B44`
- **Texto Secundario**: `#8B7355`
- **Bordes**: `#D4C4A8`, `#E8DCC8`

### Tarjetas de Estadísticas (Gradientes)
1. **Stat Card 1**: `linear-gradient(135deg, #D4A574 0%, #C19461 100%)`
2. **Stat Card 2**: `linear-gradient(135deg, #B8956A 0%, #A67C52 100%)`
3. **Stat Card 3**: `linear-gradient(135deg, #8B7355 0%, #6F5B44 100%)`
4. **Stat Card 4**: `linear-gradient(135deg, #A0826D 0%, #8B6F5C 100%)`

### Botones
- **Botón Principal**: `linear-gradient(135deg, #8B7355 0%, #6F5B44 100%)`
- **Botón Secundario**: `rgba(111, 91, 68, 0.15)` con borde `rgba(111, 91, 68, 0.25)`
- **Hover**: `transform: translateY(-2px)` + `box-shadow: 0 4px 10px rgba(139, 115, 85, 0.3)`

### Tabla
- **Header**: `linear-gradient(135deg, #8B7355 0%, #6F5B44 100%)`
- **Bordes de Fila**: `#F5F1E8`
- **Fondo**: `white` con `border-radius: 8px`

## 🏗️ Estructura HTML Estándar

### 1. Banner Superior Fijo
```html
<div style="position: fixed; top: 0; left: 0; right: 0; background: linear-gradient(135deg, #F5F1E8 0%, #E8DCC8 100%); color: #6F5B44; text-align: center; padding: 8px; font-size: 0.8rem; font-weight: 500; font-family: 'Poppins', sans-serif; z-index: 9999; border-bottom: 1px solid #D4C4A8;">
    [Nombre del Módulo] - Estilo Terroso Estándar
</div>
```

### 2. Contenedor Principal
```html
<div class="container-fluid" style="margin-top: 80px;">
    <div class="row">
        <div class="col-12">
            <div class="card shadow-sm" style="border: 2px solid #E8DCC8; border-radius: 15px; overflow: hidden;">
```

### 3. Header de Card
```html
<div class="card-header" style="background: linear-gradient(135deg, #F5F1E8 0%, #E8DCC8 100%); border: none; border-bottom: 2px solid #D4C4A8; padding: 10px 15px; font-family: 'Poppins', sans-serif;">
    <div class="d-flex justify-content-between align-items-center">
        <div class="d-flex align-items-center">
            <i class="fas fa-[icono] fa-lg me-2" style="color: #6F5B44;"></i>
            <div>
                <h5 class="mb-0" style="font-size: 1.1rem; font-family: 'Poppins', sans-serif; font-weight: 600; color: #6F5B44;">
                    [Título del Módulo]
                </h5>
                <small style="font-size: 0.75rem; font-family: 'Poppins', sans-serif; color: #8B7355;">
                    [Descripción breve]
                </small>
            </div>
        </div>
        <div class="d-flex align-items-center">
            <!-- Botones de acción -->
        </div>
    </div>
</div>
```

### 4. Tarjetas de Estadísticas
```html
<div class="row mb-2">
    <div class="col-md-3 mb-1">
        <div class="stat-card stat-card-1 p-2 position-relative">
            <div class="stat-value" style="font-size: 1.1rem;">[Valor]</div>
            <div class="stat-label" style="font-size: 0.7rem;">[Etiqueta]</div>
            <i class="fas fa-[icono] stat-icon"></i>
        </div>
    </div>
    <!-- Repetir para stat-card-2, stat-card-3, stat-card-4 -->
</div>
```

### 5. Sección de Filtros
```html
<div class="filter-section">
    <form method="get" action="">
        <div class="row g-2">
            <div class="col-md-3">
                <label class="form-label fw-bold" style="font-size: 0.7rem; color: #6F5B44;">
                    <i class="fas fa-search me-1"></i>[Label]
                </label>
                <input type="text" name="search" class="form-control form-control-sm" placeholder="...">
            </div>
            <!-- Más filtros -->
        </div>
    </form>
</div>
```

### 6. Tabla Compacta
```html
<div class="table-responsive" style="background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
    <table class="table table-hover table-compact mb-0">
        <thead>
            <tr>
                <th style="width: [%];">[Columna]</th>
                <!-- Más columnas -->
            </tr>
        </thead>
        <tbody>
            <!-- Filas con style="border-bottom: 1px solid #F5F1E8;" -->
        </tbody>
    </table>
</div>
```

## 📐 CSS Estándar Requerido

### Estilos Base
```css
/* Fondo terroso suave */
body {
    background: linear-gradient(135deg, #FAFAF8 0%, #F5F1E8 100%) !important;
    min-height: 100vh;
}

/* Tarjetas de estadísticas */
.stat-card {
    border: none;
    border-radius: 12px;
    transition: all 0.3s ease;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.stat-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.12);
}

.stat-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: white;
    margin-bottom: 0.25rem;
}

.stat-label {
    color: rgba(255,255,255,0.9);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 500;
}

.stat-icon {
    font-size: 2rem;
    color: rgba(255,255,255,0.3);
    position: absolute;
    right: 15px;
    bottom: 15px;
}

/* Sección de filtros */
.filter-section {
    background: linear-gradient(135deg, #FAF8F3 0%, #F5F1E8 100%);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

/* Tabla compacta */
.table-compact {
    font-size: 0.75rem;
    line-height: 1.1;
}

.table-compact thead th {
    padding: 4px 2px;
    font-weight: 600;
    background: linear-gradient(135deg, #8B7355 0%, #6F5B44 100%);
    color: white;
    border: none;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.2px;
    line-height: 1.1;
}

.table-compact tbody td {
    padding: 2px 3px;
    vertical-align: middle;
    line-height: 1.2;
    font-size: 0.7rem;
}

.table-compact tbody tr {
    height: 28px;
}

/* Botones */
.btn-filter {
    background: linear-gradient(135deg, #8B7355 0%, #6F5B44 100%);
    border: none;
    color: white;
    padding: 8px 20px;
    font-weight: 500;
    border-radius: 8px;
    transition: all 0.3s ease;
}

.btn-filter:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 10px rgba(139, 115, 85, 0.3);
    color: white;
}

.btn-action {
    padding: 4px 10px;
    font-size: 0.75rem;
    border-radius: 6px;
}
```

## 📝 Tipografía

- **Fuente Principal**: `'Poppins', sans-serif`
- **Tamaños**:
  - Título Principal: `1.1rem`, `font-weight: 600`
  - Subtítulo: `0.75rem`, `font-weight: 500`
  - Texto de Tabla: `0.7rem`
  - Labels de Filtros: `0.7rem`, `font-weight: bold`
  - Badges: `0.6rem`

## 🎯 Iconos

- Usar **Font Awesome** para todos los iconos
- Color de iconos en headers: `#6F5B44`
- Color de iconos en stat-cards: `rgba(255,255,255,0.3)`

## ✅ Módulos que Implementan este Estándar

### Usuarios
1. ✅ **Gestión de Usuarios** (`usuarios/templates/usuarios/usuario_list.html`)

### Inventario (Completado)
1. ✅ **Lista de Movimientos** (`inventario/templates/inventario/inventario_list.html`)
2. ✅ **Lista de Ajustes** (`inventario/templates/inventario/ajustes_list_simple.html`)
3. ✅ **Formulario de Movimiento** (`inventario/templates/inventario/inventario_form.html`)
4. ✅ **Formulario de Ajuste** (`inventario/templates/inventario/ajuste_form_simple.html`)
5. ✅ **Edición Manual** (`inventario/templates/inventario/edicion_manual_inventario.html`)
6. ✅ **Carga Inicial** (`inventario/templates/inventario/carga_inicial.html`)
7. ✅ **Configuración Correlativos** (`inventario/templates/inventario/correlativos_config.html`)

## 📌 Indicador Visual

Agregar al final de cada template que implemente este estándar:

```html
<div style="position: fixed; bottom: 10px; right: 10px; background: linear-gradient(135deg, #8B7355 0%, #6F5B44 100%); color: white; padding: 8px 15px; border-radius: 15px; font-size: 0.7rem; font-family: 'Poppins', sans-serif; z-index: 9999;">
    🎨 Estilo Terroso Estándar - [Nombre del Módulo]
</div>
```

## 🔄 Próximos Módulos a Actualizar

- [ ] Gestión de Artículos
- [ ] Gestión de Clientes
- [ ] Gestión de Proveedores
- [ ] Gestión de Ventas
- [ ] Gestión de Compras
- [ ] Gestión de Bodegas
- [ ] Reportes
- [ ] Facturación Electrónica
- [ ] Sistema de Caja
- [ ] Tesorería

## 📖 Notas de Implementación

1. Siempre incluir el bloque `{% block extra_head %}` con el estilo del body
2. Usar `{% block body_class %}hide-top-bar{% endblock %}` para ocultar la barra superior
3. Mantener el `margin-top: 80px` en el contenedor principal para el banner fijo
4. Usar clases de Bootstrap 5 cuando sea posible
5. Mantener la consistencia en los tamaños de fuente y espaciados
6. Todos los formularios de filtro deben usar `form-control-sm` y `form-select-sm`
7. Los badges deben usar `font-size: 0.6rem`

---

**Última actualización**: 2025-10-08  
**Versión**: 1.0  
**Autor**: Sistema GestionCloud
