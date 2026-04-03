from django.contrib import admin
from .models import Empresa, Sucursal, PlanSaaS, Suscripcion, ConfiguracionEmpresa

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'rut', 'plan', 'estado', 'fecha_limite_pago')
    list_filter = ('estado', 'plan')
    search_fields = ('nombre', 'rut')

@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'empresa', 'codigo', 'es_principal')
    list_filter = ('empresa', 'es_principal')

@admin.register(PlanSaaS)
class PlanSaaSAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio_mensual', 'max_usuarios', 'max_sucursales', 'activo')
    list_filter = ('activo',)

@admin.register(Suscripcion)
class SuscripcionAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'plan', 'fecha_inicio', 'fecha_fin', 'estado_pago')
    list_filter = ('estado_pago', 'plan')

@admin.register(ConfiguracionEmpresa)
class ConfiguracionEmpresaAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'frecuencia_respaldo')
