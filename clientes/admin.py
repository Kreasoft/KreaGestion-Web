from django.contrib import admin
from .models import Cliente, ContactoCliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'rut', 'ruta', 'estado', 'limite_credito', 'empresa')
    list_filter = ('estado', 'ruta', 'tipo_cliente', 'empresa')
    search_fields = ('nombre', 'rut', 'email', 'telefono')
    ordering = ['nombre']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'rut', 'nombre', 'tipo_cliente', 'giro', 'estado')
        }),
        ('Ubicación', {
            'fields': ('direccion', 'comuna', 'ciudad', 'region', 'ruta')
        }),
        ('Contacto', {
            'fields': ('telefono', 'email', 'sitio_web')
        }),
        ('Información Comercial', {
            'fields': ('limite_credito', 'plazo_pago', 'descuento_porcentaje')
        }),
        ('Observaciones', {
            'fields': ('observaciones',)
        }),
        ('Auditoría', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('fecha_creacion', 'fecha_modificacion')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filtrar por empresa del usuario si aplica
        return qs


@admin.register(ContactoCliente)
class ContactoClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cliente', 'cargo', 'tipo_contacto', 'telefono', 'email', 'es_contacto_principal')
    list_filter = ('tipo_contacto', 'es_contacto_principal', 'cliente__empresa')
    search_fields = ('nombre', 'cliente__nombre', 'email', 'telefono', 'celular')
    ordering = ['cliente', 'nombre']
