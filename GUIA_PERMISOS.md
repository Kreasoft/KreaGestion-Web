# Guía de Implementación de Permisos por Roles

Esta guía explica cómo validar los permisos de usuario en el sistema GestionCloud.

## 🔐 Conceptos Básicos

Django proporciona un sistema de permisos basado en:
- **Usuarios (User)**: Cuentas individuales
- **Grupos (Group)**: Roles que agrupan permisos
- **Permisos (Permission)**: Acciones específicas sobre modelos

Cada modelo automáticamente tiene 4 permisos:
- `add_<modelo>`: Crear nuevos registros
- `change_<modelo>`: Editar registros existentes
- `delete_<modelo>`: Eliminar registros
- `view_<modelo>`: Ver/listar registros

## 📋 Formato de Permisos

Los permisos en Django siguen el formato: `app_label.codename`

Ejemplos:
- `articulos.view_articulo` - Ver artículos
- `articulos.add_articulo` - Crear artículos
- `articulos.change_articulo` - Editar artículos
- `articulos.delete_articulo` - Eliminar artículos
- `ventas.add_venta` - Crear ventas
- `clientes.view_cliente` - Ver clientes

## 🎯 Implementación en 3 Niveles

### 1. Validación en el Menú (base.html)

El menú lateral oculta las opciones según los permisos del usuario.

```django
<!-- Ejemplo: Submenú de Artículos -->
{% if perms.articulos.view_articulo or perms.articulos.view_categoriaarticulo or user.is_superuser %}
<div class="nav-item has-submenu">
    <a href="#" class="nav-link submenu-toggle">
        <i class="nav-icon fas fa-box"></i>
        <span class="nav-text">Artículos</span>
    </a>
    <div class="collapse submenu">
        <div class="submenu-items">
            {% if perms.articulos.view_articulo or user.is_superuser %}
            <a href="{% url 'articulos:articulo_list' %}">
                <i class="fas fa-list me-2"></i>
                <span>Lista de Artículos</span>
            </a>
            {% endif %}
            
            {% if perms.articulos.view_categoriaarticulo or user.is_superuser %}
            <a href="{% url 'articulos:categoria_list' %}">
                <i class="fas fa-tags me-2"></i>
                <span>Categorías</span>
            </a>
            {% endif %}
        </div>
    </div>
</div>
{% endif %}
```

**Reglas:**
- El menú principal se muestra si el usuario tiene AL MENOS UN permiso de esa sección
- Cada opción del submenú se valida individualmente
- Siempre incluir `or user.is_superuser` para que los superusuarios vean todo

### 2. Validación en Templates (Botones y Acciones)

Los botones de crear, editar y eliminar se ocultan según los permisos.

```django
<!-- Ejemplo: Botones en el header de una lista -->
<div class="btn-group">
    {% if perms.articulos.view_categoriaarticulo or user.is_superuser %}
    <a href="{% url 'articulos:categoria_list' %}" class="btn btn-outline-light">
        <i class="fas fa-tags"></i> Categorías
    </a>
    {% endif %}
    
    {% if perms.articulos.add_articulo or user.is_superuser %}
    <a href="{% url 'articulos:articulo_create' %}" class="btn btn-primary">
        <i class="fas fa-plus me-2"></i> Nuevo Artículo
    </a>
    {% endif %}
</div>

<!-- Ejemplo: Menú dropdown de acciones en tabla -->
<div class="dropdown">
    <button class="btn btn-sm dropdown-toggle" data-bs-toggle="dropdown">
        <i class="fas fa-ellipsis-v"></i>
    </button>
    <ul class="dropdown-menu">
        {% if perms.articulos.view_articulo or user.is_superuser %}
        <li>
            <a class="dropdown-item" href="{% url 'articulos:articulo_detail' articulo.pk %}">
                <i class="fas fa-eye me-2"></i>Ver detalles
            </a>
        </li>
        {% endif %}
        
        {% if perms.articulos.change_articulo or user.is_superuser %}
        <li>
            <a class="dropdown-item" href="{% url 'articulos:articulo_update' articulo.pk %}">
                <i class="fas fa-edit me-2"></i>Editar
            </a>
        </li>
        {% endif %}
        
        {% if perms.articulos.delete_articulo or user.is_superuser %}
        <li><hr class="dropdown-divider"></li>
        <li>
            <a class="dropdown-item" href="{% url 'articulos:articulo_delete' articulo.pk %}">
                <i class="fas fa-trash me-2"></i>Eliminar
            </a>
        </li>
        {% endif %}
    </ul>
</div>
```

**Reglas:**
- Botón "Nuevo/Crear" → requiere `add_<modelo>`
- Botón "Ver/Detalle" → requiere `view_<modelo>`
- Botón "Editar" → requiere `change_<modelo>`
- Botón "Eliminar" → requiere `delete_<modelo>`

### 3. Validación en Backend (views.py)

Las vistas deben validar permisos para prevenir acceso directo por URL.

```python
from django.contrib.auth.decorators import login_required, permission_required
from empresas.decorators import requiere_empresa

# Lista/Ver registros
@requiere_empresa
@login_required
@permission_required('articulos.view_articulo', raise_exception=True)
def articulo_list(request):
    # ... código de la vista
    pass

# Crear nuevos registros
@requiere_empresa
@login_required
@permission_required('articulos.add_articulo', raise_exception=True)
def articulo_create(request):
    # ... código de la vista
    pass

# Editar registros existentes
@requiere_empresa
@login_required
@permission_required('articulos.change_articulo', raise_exception=True)
def articulo_update(request, pk):
    # ... código de la vista
    pass

# Eliminar registros
@requiere_empresa
@login_required
@permission_required('articulos.delete_articulo', raise_exception=True)
def articulo_delete(request, pk):
    # ... código de la vista
    pass
```

**Orden de decoradores (IMPORTANTE):**
1. `@requiere_empresa` (validar empresa activa)
2. `@login_required` (validar autenticación)
3. `@permission_required` (validar permiso específico)

**Parámetros:**
- `raise_exception=True`: Muestra página de error 403 (Acceso Denegado) si no tiene permiso
- Sin `raise_exception`: Redirige a login (no recomendado)

## 📝 Lista de Permisos por Aplicación

### Artículos
- `articulos.view_articulo`
- `articulos.add_articulo`
- `articulos.change_articulo`
- `articulos.delete_articulo`
- `articulos.view_categoriaarticulo`
- `articulos.add_categoriaarticulo`
- `articulos.change_categoriaarticulo`
- `articulos.delete_categoriaarticulo`
- `articulos.view_unidadmedida`
- `articulos.add_unidadmedida`
- `articulos.change_unidadmedida`
- `articulos.delete_unidadmedida`
- `articulos.view_impuestoespecifico`
- `articulos.view_stockarticulo`

### Ventas
- `ventas.view_venta`
- `ventas.add_venta` (para POS)
- `ventas.change_venta`
- `ventas.delete_venta`
- `ventas.view_cotizacion`
- `ventas.add_cotizacion`
- `ventas.change_cotizacion`
- `ventas.delete_cotizacion`
- `ventas.view_vendedor`
- `ventas.add_vendedor`
- `ventas.change_vendedor`
- `ventas.delete_vendedor`
- `ventas.view_formapago`
- `ventas.add_formapago`
- `ventas.change_formapago`
- `ventas.delete_formapago`
- `ventas.view_estaciontrabajo`
- `ventas.add_estaciontrabajo`
- `ventas.change_estaciontrabajo`
- `ventas.delete_estaciontrabajo`

### Clientes
- `clientes.view_cliente`
- `clientes.add_cliente`
- `clientes.change_cliente`
- `clientes.delete_cliente`
- `clientes.view_contactocliente`

### Compras
- `compras.view_ordencompra`
- `compras.add_ordencompra`
- `compras.change_ordencompra`
- `compras.delete_ordencompra`

### Documentos
- `documentos.view_documento`
- `documentos.add_documento`
- `documentos.change_documento`
- `documentos.delete_documento`

### Proveedores
- `proveedores.view_proveedor`
- `proveedores.add_proveedor`
- `proveedores.change_proveedor`
- `proveedores.delete_proveedor`
- `proveedores.view_contactoproveedor`

### Inventario
- `inventario.view_movimientoinventario`
- `inventario.add_movimientoinventario`
- `inventario.view_ajusteinventario`
- `inventario.add_ajusteinventario`
- `inventario.change_ajusteinventario`
- `inventario.delete_ajusteinventario`
- `inventario.add_cargainicial`

### Bodegas
- `bodegas.view_bodega`
- `bodegas.add_bodega`
- `bodegas.change_bodega`
- `bodegas.delete_bodega`

### Tesorería
- `tesoreria.view_cuentacorriente`
- `tesoreria.add_pago`
- `tesoreria.add_cobro`

### Empresas
- `empresas.view_empresa`
- `empresas.change_empresa`
- `empresas.view_sucursal`
- `empresas.add_sucursal`
- `empresas.change_sucursal`
- `empresas.delete_sucursal`

### Usuarios (Django Auth)
- `auth.view_user`
- `auth.add_user`
- `auth.change_user`
- `auth.delete_user`
- `auth.view_group`
- `auth.add_group`
- `auth.change_group`
- `auth.delete_group`

## 🚀 Pasos para Implementar en un Nuevo Módulo

### Paso 1: Actualizar el Menú (base.html)
1. Localizar el submenú correspondiente
2. Envolver el menú principal con `{% if perms.app.view_modelo or user.is_superuser %}`
3. Envolver cada opción del submenú con su permiso específico

### Paso 2: Actualizar los Templates de Lista
1. Localizar botones de "Nuevo/Crear" → agregar `{% if perms.app.add_modelo or user.is_superuser %}`
2. Localizar menús dropdown de acciones:
   - Ver → `{% if perms.app.view_modelo or user.is_superuser %}`
   - Editar → `{% if perms.app.change_modelo or user.is_superuser %}`
   - Eliminar → `{% if perms.app.delete_modelo or user.is_superuser %}`

### Paso 3: Actualizar las Vistas (views.py)
1. Importar: `from django.contrib.auth.decorators import permission_required`
2. Agregar decorador a cada vista:
   - Lista → `@permission_required('app.view_modelo', raise_exception=True)`
   - Detalle → `@permission_required('app.view_modelo', raise_exception=True)`
   - Crear → `@permission_required('app.add_modelo', raise_exception=True)`
   - Editar → `@permission_required('app.change_modelo', raise_exception=True)`
   - Eliminar → `@permission_required('app.delete_modelo', raise_exception=True)`

## 🔍 Verificación

### Probar con Usuario sin Permisos
1. Crear un grupo/rol nuevo sin ningún permiso
2. Crear un usuario y asignarlo a ese grupo
3. Iniciar sesión con ese usuario
4. Verificar que NO vea ningún menú ni botón

### Probar con Permisos Parciales
1. Crear un grupo con solo permiso `view` (ver)
2. Asignar usuario a ese grupo
3. Verificar que:
   - ✅ Ve el menú y puede listar
   - ❌ NO ve botones de crear/editar/eliminar
   - ❌ Si intenta acceder por URL a crear/editar/eliminar → Error 403

### Probar con Permisos Completos
1. Crear un grupo con todos los permisos (`add`, `change`, `delete`, `view`)
2. Asignar usuario a ese grupo
3. Verificar que puede hacer todo

## ⚠️ Notas Importantes

1. **Superusuarios**: Siempre tienen todos los permisos, por eso usamos `or user.is_superuser`

2. **Orden de Validación**: 
   - Frontend (template) → Oculta opciones visualmente
   - Backend (views) → Previene acceso directo por URL
   - **AMBOS son necesarios** para seguridad completa

3. **Permisos Personalizados**: Si necesitas permisos más específicos (ej: "anular_venta"), puedes crearlos en el modelo:
   ```python
   class Venta(models.Model):
       # ... campos ...
       
       class Meta:
           permissions = [
               ("anular_venta", "Puede anular ventas"),
               ("ver_reporte_ventas", "Puede ver reportes de ventas"),
           ]
   ```

4. **Migrar después de cambiar permisos**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

## 📚 Recursos Adicionales

- [Documentación oficial Django Permissions](https://docs.djangoproject.com/en/stable/topics/auth/default/#permissions-and-authorization)
- [Django Permission Required Decorator](https://docs.djangoproject.com/en/stable/topics/auth/default/#the-permission-required-decorator)

---

**Última actualización**: Octubre 2025
**Sistema**: GestionCloud v1.0












