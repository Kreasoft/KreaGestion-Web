# ✅ ALERTAS DE FOLIOS POR TIPO DE DOCUMENTO - IMPLEMENTADO

## 📋 Resumen

Se ha implementado un sistema de **alertas de folios configurables por tipo de documento**, permitiendo que cada tipo de DTE (Boleta, Factura, Guía, etc.) tenga su propio umbral de alerta según su volumen de uso.

---

## 🎯 Problema Resuelto

**Antes**: Había un único umbral de alerta para todos los documentos.

**Ahora**: Cada tipo de documento tiene su propio umbral configurable, adaptándose al volumen real de uso de cada uno.

---

## 🆕 Modelo ConfiguracionAlertaFolios

Se creó un nuevo modelo para almacenar las configuraciones de alertas:

```python
class ConfiguracionAlertaFolios(models.Model):
    """Configuración de alertas de folios por tipo de documento"""
    
    empresa = ForeignKey(Empresa)
    tipo_documento = CharField  # '33', '39', '52', etc.
    folios_minimos = IntegerField  # Umbral de alerta
    activo = BooleanField  # Si la alerta está activa
    fecha_creacion = DateTimeField
    fecha_modificacion = DateTimeField
    
    class Meta:
        unique_together = ['empresa', 'tipo_documento']
```

**Características**:
- Una configuración por empresa y tipo de documento
- Valor por defecto: 20 folios
- Se puede activar/desactivar individualmente
- Registro de fechas de creación y modificación

---

## 🎨 Nueva Vista de Configuración

**URL**: `/facturacion-electronica/alertas-folios/`

**Función**: `alertas_folios_config(request)`

### Características

✅ **Carga automática**: Crea configuraciones para todos los tipos de documento si no existen
✅ **Formulario visual**: Cards por cada tipo de documento con sugerencias personalizadas
✅ **Activación individual**: Toggle para activar/desactivar alertas por tipo
✅ **Ejemplos prácticos**: Sugerencias según el tipo de negocio

### Interfaz

Cada tipo de documento tiene su propia card con:

```
┌────────────────────────────────────────────────┐
│ 📄 Factura Electrónica         [Código: 33]   │
├────────────────────────────────────────────────┤
│                                                │
│ ☑️ Alerta Activa                              │
│                                                │
│ ⚠️ Alertar cuando queden:                     │
│ [____20____] folios o menos                   │
│                                                │
│ Sugerencia:                                    │
│ Las facturas suelen tener volumen medio.      │
│ Recomendado: 20-50 folios                     │
│                                                │
└────────────────────────────────────────────────┘
```

---

## 🔔 Sistema de Alertas Actualizado

### En la Lista de CAF

Las alertas ahora se muestran según la configuración de cada tipo de documento:

```python
# Vista caf_list actualizada
alertas_config = {}
for config in ConfiguracionAlertaFolios.objects.filter(
    empresa=request.empresa, 
    activo=True
):
    alertas_config[config.tipo_documento] = config.folios_minimos
```

### Template con Filtro Personalizado

```django
{% load fe_tags %}

{% for caf in archivos_caf %}
    {% with umbral=alertas_config|get_item:caf.tipo_documento %}
        {% if umbral and caf.folios_disponibles <= umbral %}
            <div class="alert alert-warning">
                ⚠️ ¡Folios por agotarse!
                El CAF de {{ caf.get_tipo_documento_display }}
                tiene solo {{ caf.folios_disponibles }} folios
                (umbral: {{ umbral }})
            </div>
        {% endif %}
    {% endwith %}
{% endfor %}
```

---

## 📱 Acceso a la Configuración

### 1. Desde la Lista de CAF

Botón destacado en la parte superior:

```html
<a href="{% url 'facturacion_electronica:alertas_folios_config' %}" 
   class="btn btn-warning">
    🔔 Configurar Alertas
</a>
```

### 2. Desde Configuración de Empresa

En la pestaña "Facturación Electrónica", hay una nota con enlace directo:

```
ℹ️ Alertas de Folios por Tipo de Documento
Las alertas se configuran por tipo de documento para mayor flexibilidad.

[⚙️ Configurar Alertas de Folios]
```

---

## 🎯 Sugerencias por Tipo de Documento

El sistema proporciona recomendaciones contextuales:

### Boletas (39, 41)
- **Volumen**: Alto
- **Recomendado**: 50-100 folios
- **Razón**: Las boletas suelen emitirse en grandes volúmenes diariamente

### Facturas (33, 34)
- **Volumen**: Medio
- **Recomendado**: 20-50 folios
- **Razón**: Las facturas tienen un volumen moderado y constante

### Guías (52)
- **Volumen**: Variable
- **Recomendado**: 20-40 folios
- **Razón**: El volumen depende del tipo de negocio

### Notas de Crédito/Débito (56, 61)
- **Volumen**: Bajo
- **Recomendado**: 10-20 folios
- **Razón**: Estos documentos se emiten ocasionalmente

---

## 📊 Ejemplos por Tipo de Negocio

### Negocio de Retail
```
Boletas:   100-200 folios  (emiten 50-100/día)
Facturas:   30-50 folios   (emiten 10-20/día)
Notas:      10-20 folios   (bajo volumen)
```

### Empresa de Servicios
```
Facturas:   50-80 folios   (emiten 20-30/día)
Boletas:    30-50 folios   (volumen medio)
Notas:      20-30 folios   (uso frecuente)
```

### Pequeño Negocio
```
Boletas:    20-30 folios   (emiten 5-10/día)
Facturas:   10-20 folios   (bajo volumen)
Notas:       5-10 folios   (uso ocasional)
```

---

## 🛠️ Archivos Modificados/Creados

### Nuevos Archivos

```
✅ facturacion_electronica/models.py
   + ConfiguracionAlertaFolios

✅ facturacion_electronica/admin.py
   + ConfiguracionAlertaFoliosAdmin

✅ facturacion_electronica/views.py
   + alertas_folios_config()

✅ facturacion_electronica/urls.py
   + path('alertas-folios/', ...)

✅ facturacion_electronica/templates/facturacion_electronica/
   + alertas_folios_config.html

✅ facturacion_electronica/templatetags/
   + __init__.py
   + fe_tags.py (filtro get_item)

✅ facturacion_electronica/migrations/
   + 0002_configuracionalertafolios.py
```

### Archivos Modificados

```
✅ empresas/models.py
   - Eliminado campo alerta_folios_minimos

✅ empresas/forms.py
   - Eliminado alerta_folios_minimos del formulario

✅ empresas/migrations/
   + 0009_remove_empresa_alerta_folios_minimos.py

✅ templates/empresas/editar_empresa_activa.html
   - Reemplazada sección con enlace a nueva configuración

✅ facturacion_electronica/templates/facturacion_electronica/caf_list.html
   + Load fe_tags
   + Botón "Configurar Alertas"
   + Lógica de alertas con umbral por tipo
```

---

## 🚀 Flujo de Uso

### 1. Acceder a Configuración

```
Usuario → Lista CAF → [Configurar Alertas]
```

O bien:

```
Usuario → Editar Empresa → Tab FE → [Configurar Alertas]
```

### 2. Configurar por Tipo

```
1. Activar/desactivar alerta (toggle)
2. Ingresar cantidad de folios
3. Ver sugerencia contextual
4. Guardar
```

### 3. Ver Alertas

```
Al listar CAF, el sistema compara:
- Folios disponibles del CAF
- Umbral configurado para ese tipo
- Si disponibles <= umbral → ALERTA
```

---

## 💡 Ventajas del Nuevo Sistema

✅ **Precisión**: Cada documento tiene su umbral específico
✅ **Flexibilidad**: Se puede activar/desactivar por tipo
✅ **Contextual**: Sugerencias según el tipo de documento
✅ **Escalable**: Fácil agregar nuevos tipos de documento
✅ **Visual**: Interfaz clara y fácil de usar
✅ **Inteligente**: Ejemplos según tipo de negocio

---

## 🔄 Migración desde Sistema Anterior

El sistema anterior con `Empresa.alerta_folios_minimos` ha sido:

1. ✅ **Eliminado** del modelo Empresa
2. ✅ **Eliminado** del formulario de FE
3. ✅ **Reemplazado** con enlace a nueva configuración
4. ✅ **Migrado** automáticamente (campo eliminado de BD)

**Nota**: El valor anterior (20 folios) se usa como default para el nuevo sistema.

---

## 📝 Uso de Template Tags

Se creó un filtro personalizado para acceder al diccionario de alertas:

```python
# fe_tags.py
@register.filter(name='get_item')
def get_item(dictionary, key):
    """Obtener item de diccionario por clave"""
    if dictionary is None:
        return None
    return dictionary.get(key)
```

**Uso en template**:
```django
{% load fe_tags %}
{% with umbral=alertas_config|get_item:caf.tipo_documento %}
    {{ umbral }}
{% endwith %}
```

---

## 🎉 Resultado Final

```
🔔 ALERTAS DE FOLIOS POR TIPO DE DOCUMENTO

┌─────────────────────────────────────────────┐
│ Boleta Electrónica (39)                     │
│ ☑️ Activa | Umbral: 100 folios             │
├─────────────────────────────────────────────┤
│ Factura Electrónica (33)                    │
│ ☑️ Activa | Umbral: 30 folios              │
├─────────────────────────────────────────────┤
│ Guía de Despacho (52)                       │
│ ☑️ Activa | Umbral: 20 folios              │
├─────────────────────────────────────────────┤
│ Nota de Crédito (61)                        │
│ ☐ Inactiva | Umbral: 10 folios             │
└─────────────────────────────────────────────┘

Sistema adaptado al volumen real de cada documento ✅
```

---

## 🎯 Próximos Pasos Posibles

1. **Dashboard de alertas**: Panel centralizado con todas las alertas
2. **Notificaciones por email**: Enviar alertas por correo
3. **Alertas múltiples**: Configurar varios umbrales (crítico, advertencia, info)
4. **Historial**: Registro de cuándo se activan las alertas
5. **Predicción**: Calcular cuántos días quedan según ritmo de consumo

---

**Estado**: ✅ COMPLETADO E IMPLEMENTADO
**Fecha**: 06/10/2025
**Versión**: 1.0





















