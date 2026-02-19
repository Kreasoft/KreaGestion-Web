# INSTRUCCIONES PARA IMPLEMENTAR CAFs POR SUCURSAL

## PROBLEMA ACTUAL
Hay un error en el modelo Empresa que está impidiendo ejecutar migraciones.
Error: FieldError relacionado con campos del modelo Empresa.

## PASOS PARA COMPLETAR LA IMPLEMENTACIÓN

### 1. Resolver error del modelo Empresa
Primero debes resolver el error actual en el modelo Empresa que impide ejecutar migraciones.

### 2. Aplicar la migración de CAFs
Una vez resuelto el error anterior, ejecutar:
```bash
python manage.py migrate facturacion_electronica 0011
```

Esta migración:
- Agrega campo `sucursal` a ArchivoCAF
- Agrega campo `oculto` para poder ocultar CAFs agotados
- Asigna automáticamente la casa matriz a todos los CAFs existentes
- Actualiza los índices de base de datos

### 3. Archivos modificados

#### models.py
- `facturacion_electronica/models.py`: Se agregaron campos `sucursal` y `oculto` al modelo ArchivoCAF

#### Migración creada
- `facturacion_electronica/migrations/0011_add_sucursal_oculto_to_caf.py`

### 4. Próximos pasos pendientes

Una vez aplicada la migración, necesitas:

1. **Actualizar vistas de gestión de CAFs**:
   - Filtrar CAFs por sucursal del usuario
   - Agregar botones para ocultar/mostrar CAFs
   - Agregar botón para eliminar CAFs agotados/vencidos

2. **Actualizar formulario de carga de CAFs**:
   - Agregar selector de sucursal
   - Validar que el usuario tenga permisos para cargar CAFs en esa sucursal

3. **Actualizar lógica de facturación**:
   - Al generar factura, buscar CAF activo de la sucursal del usuario
   - Validar que el CAF pertenezca a la sucursal correcta
   - Asignar automáticamente el siguiente folio disponible

4. **Crear vista de administración de CAFs**:
   - Listar CAFs por sucursal
   - Filtrar por estado (activo, agotado, vencido, anulado)
   - Opción para mostrar/ocultar CAFs agotados
   - Opción para eliminar CAFs (solo los que no tienen DTEs asociados)

## FUNCIONES IMPORTANTES A IMPLEMENTAR

### Obtener CAF activo por sucursal
```python
def obtener_caf_activo(empresa, sucursal, tipo_documento):
    """
    Obtiene el CAF activo para una sucursal y tipo de documento específico
    """
    return ArchivoCAF.objects.filter(
        empresa=empresa,
        sucursal=sucursal,
        tipo_documento=tipo_documento,
        estado='activo',
        oculto=False
    ).order_by('folio_actual').first()
```

### Ocultar CAFs agotados
```python
def ocultar_cafs_agotados(empresa_id, sucursal_id=None):
    """
    Oculta todos los CAFs agotados o vencidos
    """
    filtro = {
        'empresa_id': empresa_id,
        'estado__in': ['agotado', 'vencido'],
        'oculto': False
    }
    if sucursal_id:
        filtro['sucursal_id'] = sucursal_id
    
    return ArchivoCAF.objects.filter(**filtro).update(oculto=True)
```

### Eliminar CAFs sin uso
```python
def eliminar_cafs_sin_uso(empresa_id):
    """
    Elimina CAFs que nunca fueron utilizados (folios_utilizados = 0)
    y que están agotados o venc idos
    """
    return ArchivoCAF.objects.filter(
        empresa_id=empresa_id,
        folios_utilizados=0,
        estado__in=['agotado', 'vencido', 'anulado']
    ).delete()
```

## CONTACTO
Si necesitas ayuda para resolver el error del modelo Empresa o implementar
los siguientes pasos, avísame.
