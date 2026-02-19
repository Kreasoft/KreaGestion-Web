# Sistema de Importación de Datos desde MySQL

## 📋 Descripción

Sistema completo para importar datos desde bases de datos MySQL externas (locales o remotas) al sistema GestionCloud. Permite importar:

- ✅ **Clientes**
- ✅ **Proveedores**
- ✅ **Familias de Artículos**
- ✅ **Artículos**

## 🎯 Características

### 1. Conexión Flexible
- Conexión a bases de datos MySQL locales o remotas
- Soporte para diferentes puertos
- Autenticación con usuario y contraseña
- Validación de conexión antes de proceder

### 2. Wizard de 4 Pasos

#### Paso 1: Conexión
- Formulario para ingresar datos de conexión
- Host (localhost, IP o dominio)
- Puerto (por defecto 3306)
- Nombre de base de datos
- Usuario y contraseña
- Validación automática de conexión

#### Paso 2: Selección
- Selección visual del tipo de datos a importar (cards interactivas)
- Lista desplegable con todas las tablas disponibles en la BD
- Interfaz intuitiva con iconos

#### Paso 3: Mapeo de Campos
- Mapeo visual de campos origen → destino
- Indicación de campos obligatorios (*)
- Vista previa de datos (primeras 5 filas)
- Tabla interactiva para relacionar campos

#### Paso 4: Resultado
- Resumen de importación
- Cantidad de registros importados exitosamente
- Lista de errores (si los hay)
- Opciones para nueva importación o volver al dashboard

### 3. Mapeo Inteligente

#### Clientes
- **Obligatorios**: RUT, Nombre
- **Opcionales**: Giro, Dirección, Comuna, Ciudad, Región, Teléfono, Email
- **Filtro Automático**: Solo importa registros donde `ES_CLI = 'S'`
- **Nota**: Compatible con tablas unificadas de VB6 (bd_clpr)

#### Proveedores
- **Obligatorios**: RUT, Nombre
- **Opcionales**: Giro, Dirección, Comuna, Ciudad, Teléfono, Email
- **Filtro Automático**: Solo importa registros donde `ES_PRO = 'S'`
- **Nota**: Compatible con tablas unificadas de VB6 (bd_clpr)

#### Familias
- **Obligatorios**: Código, Nombre
- **Opcionales**: Descripción

#### Artículos
- **Obligatorios**: Código, Nombre
- **Opcionales**: Descripción, Código Familia, Precio, Costo, Stock, Código de Barras

### 4. Seguridad
- Datos de conexión almacenados temporalmente en sesión
- Se eliminan al cerrar el navegador
- Validación de permisos de usuario
- Transacciones atómicas (todo o nada)

### 5. Manejo de Errores
- Validación de campos requeridos
- Registro detallado de errores
- Continuación de importación aunque haya errores parciales
- Actualización de registros existentes (update_or_create)

## 🎨 Diseño

### Colores del Sistema Terroso
- **Primario**: #8B7355 (Marrón)
- **Secundario**: #6F5B44 (Marrón Oscuro)
- **Acento**: #F4E4BC (Beige Claro)
- **Fondo Cards**: #F5F0EB → #E8DED5 (Gradiente)

### Componentes Visuales
- **Cards Interactivas**: Efecto hover con elevación
- **Wizard Steps**: Indicadores visuales de progreso
- **Tablas Responsivas**: Diseño adaptable
- **Badges**: Indicadores de estado
- **Alertas**: Mensajes informativos y de error

## 📁 Estructura de Archivos

```
utilidades/
├── __init__.py
├── apps.py                 # Configuración de la app
├── urls.py                 # URLs de la app
├── views.py                # Vistas y lógica de importación
├── forms.py                # Formularios de conexión
├── templates/
│   └── utilidades/
│       ├── dashboard.html          # Dashboard de utilidades
│       └── importar_datos.html     # Wizard de importación
└── migrations/
```

## 🔧 Uso

### 1. Acceso
- Menú lateral → **Utilidades** → **Importar Datos MySQL**
- URL directa: `/utilidades/importar/`

### 2. Proceso de Importación

#### Paso 1: Conectar
```
Host: localhost (o IP remota)
Puerto: 3306
Base de Datos: nombre_bd
Usuario: root
Contraseña: ****
```

#### Paso 2: Seleccionar
- Clic en el tipo de datos (Clientes, Proveedores, etc.)
- Seleccionar tabla de origen en el dropdown
- Clic en "Continuar al Mapeo"

#### Paso 3: Mapear
- Relacionar cada campo de MySQL con los campos del sistema
- Los campos con * son obligatorios
- Revisar vista previa de datos
- Clic en "Iniciar Importación"

#### Paso 4: Resultado
- Ver resumen de importación
- Revisar errores si los hay
- Opción para nueva importación

## 🔄 Compatibilidad con Sistemas VB6

### Tabla Unificada `bd_clpr`
El sistema detecta automáticamente si un registro es Cliente o Proveedor mediante los campos:
- **`ES_CLI`**: Si es `'S'`, el registro se importa como **Cliente**
- **`ES_PRO`**: Si es `'S'`, el registro se importa como **Proveedor**

**Nota**: Un mismo registro puede ser tanto Cliente como Proveedor si ambos campos son `'S'`.

### Ejemplo de Tabla Unificada
```sql
CREATE TABLE bd_clpr (
    rut VARCHAR(12),
    nombre VARCHAR(200),
    direccion TEXT,
    telefono VARCHAR(20),
    ES_CLI CHAR(1),  -- 'S' = Es Cliente
    ES_PRO CHAR(1),  -- 'S' = Es Proveedor
    ...
);
```

### Proceso de Importación
1. **Importar Clientes**: Selecciona tabla `bd_clpr` → Solo importa donde `ES_CLI = 'S'`
2. **Importar Proveedores**: Selecciona tabla `bd_clpr` → Solo importa donde `ES_PRO = 'S'`

El sistema muestra cuántos registros fueron omitidos por no cumplir el criterio.

## 🔍 Ejemplo de Mapeo

### Tabla MySQL: `tbl_clientes`
```
id | rut_cliente | nombre_cliente | direccion | telefono | email
```

### Mapeo a GestionCloud
```
rut_cliente    → rut
nombre_cliente → nombre
direccion      → direccion
telefono       → telefono
email          → email
```

## ⚠️ Consideraciones

### Datos Existentes
- Si un registro ya existe (mismo RUT/código), se **actualiza**
- No se crean duplicados
- Usa `update_or_create` de Django

### Rendimiento
- Importación en lote
- Transacciones atómicas
- Manejo eficiente de errores

### Validaciones
- RUT/Código únicos por empresa
- Campos requeridos validados
- Formato de datos verificado

## 🚀 Próximas Funcionalidades

- [ ] Exportar datos a Excel/CSV
- [ ] Respaldo y restauración de BD
- [ ] Importación desde Excel/CSV
- [ ] Programación de importaciones automáticas
- [ ] Logs detallados de importación
- [ ] Validación avanzada de datos

## 📊 Tecnologías Utilizadas

- **Backend**: Django 4.2.7
- **Base de Datos**: PyMySQL 1.1.0
- **Frontend**: Bootstrap 5, SweetAlert2
- **Iconos**: Font Awesome 6
- **Tipografía**: Poppins (Google Fonts)

## 🎯 Casos de Uso

### 1. Migración desde Sistema Antiguo
Importa toda la base de clientes y proveedores desde un sistema legacy en MySQL.

### 2. Integración con Sistemas Externos
Sincroniza artículos desde un sistema de inventario externo.

### 3. Carga Inicial de Datos
Importa catálogo completo de productos al iniciar el sistema.

### 4. Actualización Masiva
Actualiza precios o datos de contacto de múltiples registros.

## 📝 Notas Técnicas

- La conexión MySQL se cierra automáticamente después de cada operación
- Los datos de conexión NO se almacenan en la base de datos
- Compatible con MySQL 5.7+ y MariaDB 10.2+
- Soporta codificación UTF-8

## 🔐 Seguridad

- ✅ Validación de permisos de usuario
- ✅ Protección CSRF
- ✅ Datos de conexión en sesión (no en BD)
- ✅ Transacciones atómicas
- ✅ Sanitización de nombres de tablas

---

**Desarrollado para GestionCloud** | Sistema de Gestión Multiempresa
