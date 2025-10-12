# 🚀 GestionCloud - Sistema de Gestión de Ventas e Inventario

## 📋 Descripción

**GestionCloud** es un sistema completo de gestión empresarial desarrollado en Python y Django, diseñado específicamente para el mercado chileno. El sistema maneja múltiples empresas y sucursales, con control completo de inventario, ventas, compras y cuenta corriente de clientes y proveedores.

## ✨ Características Principales

### 🏢 **Multiempresa y Multisucursal**
- Gestión independiente de múltiples empresas
- Control de sucursales por empresa
- Configuraciones personalizables por empresa
- Colores y branding personalizados

### 📦 **Control de Inventario Avanzado**
- Gestión de productos con categorías y subcategorías
- Control de stock por sucursal
- Control de lotes y fechas de vencimiento
- Alertas de stock mínimo
- Códigos de barras y SKU

### 💰 **Gestión de Ventas**
- Pedidos y ventas
- Control de precios y descuentos
- Gestión de devoluciones
- Historial de ventas por cliente

### 🛒 **Sistema de Compras**
- Órdenes de compra a proveedores
- Recepción de mercancías
- Control de calidad
- Flujo de aprobaciones

### 👥 **Cuenta Corriente**
- **Clientes**: Límites de crédito, plazos de pago
- **Proveedores**: Control de pagos y saldos
- Movimientos automáticos
- Reportes de saldos

### 📄 **Documentos Tributarios Chilenos**
- **Facturas Electrónicas (F33)**
- **Boletas Electrónicas (B14)**
- **Guías de Despacho (G43)**
- **Notas de Crédito y Débito**
- Integración con SII (Servicio de Impuestos Internos)

### 📊 **Reportes y Dashboard**
- Dashboard ejecutivo
- Reportes de ventas e inventario
- Análisis de rentabilidad
- Indicadores KPI

## 🏗️ Arquitectura del Sistema

```
GestionCloud/
├── gestioncloud/          # Proyecto principal
├── empresas/              # Gestión multiempresa y sucursales
├── productos/             # Control de inventario
├── ventas/                # Gestión de ventas
├── compras/               # Gestión de compras
├── clientes/              # Cuenta corriente de clientes
├── proveedores/           # Gestión de proveedores
├── documentos/            # Documentos tributarios
├── reportes/              # Dashboard y reportes
└── usuarios/              # Sistema de usuarios y permisos
```

## 🚀 Instalación

### 1. **Clonar el Repositorio**
```bash
git clone <url-del-repositorio>
cd GestionCloud
```

### 2. **Crear Ambiente Virtual**
```bash
python -m venv venv
venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate    # Linux/Mac
```

### 3. **Instalar Dependencias**
```bash
pip install -r requirements.txt
```

### 4. **Configurar Variables de Entorno**
```bash
cp .env.example .env
# Editar .env con tus configuraciones
```

### 5. **Ejecutar Migraciones**
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. **Crear Superusuario**
```bash
python manage.py createsuperuser
```

### 7. **Ejecutar el Servidor**
```bash
python manage.py runserver
```

## 🛠️ Tecnologías Utilizadas

- **Backend**: Python 3.13, Django 4.2.7
- **Base de Datos**: SQLite (desarrollo), PostgreSQL/MySQL (producción)
- **Frontend**: Bootstrap 5, Django Templates
- **API**: Django REST Framework
- **Autenticación**: Django Auth
- **Formularios**: Django Crispy Forms
- **Tablas**: Django Tables2
- **Validaciones**: Django Validators
- **Imágenes**: Pillow
- **Reportes**: ReportLab, XHTML2PDF

## 📱 Módulos del Sistema

### **🏢 Empresas**
- Configuración de empresas
- Gestión de sucursales
- Configuraciones por empresa
- Colores y branding

### **📦 Productos**
- Categorías y subcategorías
- Control de inventario
- Precios y costos
- Control de lotes
- Imágenes de productos

### **💰 Ventas**
- Pedidos de venta
- Facturación
- Control de precios
- Gestión de devoluciones

### **🛒 Compras**
- Órdenes de compra
- Recepción de mercancías
- Control de calidad
- Flujo de aprobaciones

### **👥 Clientes**
- Gestión de clientes
- Cuenta corriente
- Límites de crédito
- Historial de precios

### **🏭 Proveedores**
- Gestión de proveedores
- Evaluaciones
- Historial de precios
- Categorías de productos

### **📄 Documentos**
- Facturas electrónicas
- Boletas electrónicas
- Guías de despacho
- Integración SII

### **📊 Reportes**
- Dashboard ejecutivo
- Reportes de ventas
- Análisis de inventario
- Indicadores KPI

## 🔐 Seguridad

- Autenticación de usuarios
- Sistema de permisos por rol
- Auditoría de cambios
- Validación de datos
- Protección CSRF
- Filtrado de datos

## 📊 Características de Negocio

### **Control de Inventario**
- Stock mínimo y máximo
- Punto de reorden
- Alertas automáticas
- Control de lotes
- Trazabilidad

### **Gestión Financiera**
- Cuenta corriente clientes
- Cuenta corriente proveedores
- Control de límites de crédito
- Plazos de pago
- Descuentos por cliente

### **Documentos Tributarios**
- Cumplimiento normativo chileno
- Numeración automática
- Plantillas personalizables
- Envío automático por email
- Almacenamiento digital

## 🚀 Funcionalidades Avanzadas

### **Multiempresa**
- Cada empresa tiene su propia configuración
- Colores y branding personalizados
- Configuraciones tributarias independientes
- Usuarios por empresa

### **Multisucursal**
- Control de stock por sucursal
- Transferencias entre sucursales
- Configuraciones independientes
- Reportes por sucursal

### **Integración SII**
- Emisión de documentos electrónicos
- Firma electrónica
- Validación automática de RUTs
- Cumplimiento normativo

## 📈 Reportes Disponibles

- **Dashboard Ejecutivo**: Resumen general del negocio
- **Ventas**: Por período, cliente, producto, vendedor
- **Inventario**: Stock actual, movimientos, valorización
- **Clientes**: Saldos, movimientos, antigüedad
- **Proveedores**: Compras, evaluaciones, saldos
- **Financiero**: Flujo de caja, cuentas por cobrar/pagar

## 🔧 Configuración

### **Variables de Entorno**
```bash
# Configuración básica
SECRET_KEY=tu-clave-secreta
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Base de datos
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3

# SII Chile
SII_USERNAME=tu-usuario-sii
SII_PASSWORD=tu-password-sii
```

### **Configuración de Empresa**
- Logo y colores corporativos
- Configuración tributaria
- Prefijos de documentos
- Configuración de impresión

## 📦 Scripts de Carga de Stock Inicial

El sistema incluye varios scripts para facilitar la carga inicial de inventario:

### **Script Rápido** (Recomendado para inicio)
```bash
# Editar configuración en el archivo
python cargar_stock_rapido.py
```

### **Script Interactivo** (Control total)
```bash
python cargar_stock_inicial.py
# Menú interactivo con opciones
```

### **Script desde CSV**
```bash
# Crear archivo CSV con formato: codigo,cantidad
python cargar_stock_desde_csv.py stock.csv
```

### **Verificar Stock**
```bash
python verificar_stock.py
# Ver resumen y exportar reportes
```

📖 **Documentación completa**: Ver `GUIA_CARGA_STOCK_INICIAL.md` y `README_SCRIPTS_STOCK.md`

## 🚀 Despliegue

### **Desarrollo**
```bash
python manage.py runserver
```

### **Producción**
```bash
# Configurar variables de entorno
DEBUG=False
ALLOWED_HOSTS=tu-dominio.com

# Recolectar archivos estáticos
python manage.py collectstatic

# Configurar servidor web (Nginx/Apache)
# Configurar base de datos PostgreSQL/MySQL
```

## 🤝 Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 📞 Soporte

- **Email**: soporte@gestioncloud.cl
- **Documentación**: [docs.gestioncloud.cl](https://docs.gestioncloud.cl)
- **Issues**: [GitHub Issues](https://github.com/tu-usuario/gestioncloud/issues)

## 🎯 Roadmap

### **Versión 1.0** ✅
- Sistema base multiempresa
- Control de inventario
- Gestión de ventas y compras
- Documentos tributarios básicos

### **Versión 1.1** 🚧
- Dashboard avanzado
- Reportes personalizables
- Integración con sistemas contables
- API REST completa

### **Versión 1.2** 📋
- Aplicación móvil
- Integración con e-commerce
- Sistema de alertas avanzado
- Análisis predictivo

---

**GestionCloud** - Transformando la gestión empresarial en Chile 🇨🇱
