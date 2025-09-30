from django.contrib import admin
from .models import Proveedor, ContactoProveedor, CategoriaProveedor, HistorialPreciosProveedor, EvaluacionProveedor


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'rut', 'tipo_proveedor', 'calificacion', 'estado', 'fecha_alta']
    list_filter = ['tipo_proveedor', 'estado', 'fecha_alta']
    search_fields = ['nombre', 'razon_social', 'rut', 'email']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    ordering = ['nombre']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'rut', 'nombre', 'razon_social', 'giro')
        }),
        ('Clasificación', {
            'fields': ('tipo_proveedor', 'categoria_principal')
        }),
        ('Dirección', {
            'fields': ('direccion', 'comuna', 'ciudad', 'region')
        }),
        ('Contacto', {
            'fields': ('telefono', 'email', 'sitio_web')
        }),
        ('Información Comercial', {
            'fields': ('plazo_entrega', 'condiciones_pago', 'descuento_porcentaje', 'calificacion', 'observaciones_calidad')
        }),
        ('Estado', {
            'fields': ('estado', 'observaciones', 'fecha_alta')
        }),
        ('Auditoría', {
            'fields': ('creado_por', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ContactoProveedor)
class ContactoProveedorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'proveedor', 'cargo', 'tipo_contacto', 'telefono', 'email', 'es_contacto_principal']
    list_filter = ['tipo_contacto', 'es_contacto_principal']
    search_fields = ['nombre', 'proveedor__nombre', 'email']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    ordering = ['proveedor', 'tipo_contacto', 'nombre']


@admin.register(CategoriaProveedor)
class CategoriaProveedorAdmin(admin.ModelAdmin):
    list_display = ['proveedor', 'es_categoria_principal', 'descuento_categoria', 'activa']
    list_filter = ['es_categoria_principal', 'activa']
    search_fields = ['proveedor__nombre']
    ordering = ['proveedor']


@admin.register(HistorialPreciosProveedor)
class HistorialPreciosProveedorAdmin(admin.ModelAdmin):
    list_display = ['proveedor', 'precio_anterior', 'precio_nuevo', 'fecha_cambio', 'cambiado_por']
    list_filter = ['fecha_cambio']
    search_fields = ['proveedor__nombre']
    readonly_fields = ['fecha_cambio']
    ordering = ['-fecha_cambio']


@admin.register(EvaluacionProveedor)
class EvaluacionProveedorAdmin(admin.ModelAdmin):
    list_display = ['proveedor', 'fecha_evaluacion', 'periodo_evaluado', 'calificacion_general', 'recomendacion']
    list_filter = ['fecha_evaluacion', 'recomendacion']
    search_fields = ['proveedor__nombre', 'periodo_evaluado']
    readonly_fields = ['fecha_creacion', 'calificacion_general']
    ordering = ['-fecha_evaluacion']
