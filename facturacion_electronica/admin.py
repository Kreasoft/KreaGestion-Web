from django.contrib import admin
from .models import (
    ConfiguracionAlertaFolios,
    ArchivoCAF,
    DocumentoTributarioElectronico,
    EnvioDTE,
    AcuseRecibo
)


@admin.register(ConfiguracionAlertaFolios)
class ConfiguracionAlertaFoliosAdmin(admin.ModelAdmin):
    list_display = [
        'empresa',
        'tipo_documento',
        'folios_minimos',
        'activo',
        'fecha_modificacion'
    ]
    list_filter = ['empresa', 'tipo_documento', 'activo']
    search_fields = ['empresa__nombre', 'empresa__rut']
    list_editable = ['folios_minimos', 'activo']
    
    fieldsets = (
        ('Configuración', {
            'fields': ('empresa', 'tipo_documento', 'folios_minimos', 'activo')
        }),
        ('Auditoría', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']


@admin.register(ArchivoCAF)
class ArchivoCAFAdmin(admin.ModelAdmin):
    list_display = [
        'empresa',
        'tipo_documento',
        'folio_desde',
        'folio_hasta',
        'cantidad_folios',
        'folios_utilizados',
        'estado',
        'fecha_carga'
    ]
    list_filter = ['empresa', 'tipo_documento', 'estado', 'fecha_carga']
    search_fields = ['empresa__nombre', 'empresa__rut']
    readonly_fields = ['fecha_carga', 'fecha_agotamiento', 'folios_utilizados', 'folio_actual']
    
    fieldsets = (
        ('Información General', {
            'fields': ('empresa', 'tipo_documento', 'estado')
        }),
        ('Rango de Folios', {
            'fields': ('folio_desde', 'folio_hasta', 'cantidad_folios', 'folio_actual', 'folios_utilizados')
        }),
        ('Archivo CAF', {
            'fields': ('archivo_xml', 'contenido_caf', 'firma_electronica', 'fecha_autorizacion')
        }),
        ('Auditoría', {
            'fields': ('usuario_carga', 'fecha_carga', 'fecha_agotamiento')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es un nuevo objeto
            obj.usuario_carga = request.user
            obj.folio_actual = obj.folio_desde - 1
        super().save_model(request, obj, form, change)


@admin.register(DocumentoTributarioElectronico)
class DocumentoTributarioElectronicoAdmin(admin.ModelAdmin):
    list_display = [
        'empresa',
        'tipo_dte',
        'folio',
        'fecha_emision',
        'razon_social_receptor',
        'monto_total',
        'estado_sii'
    ]
    list_filter = ['empresa', 'tipo_dte', 'estado_sii', 'fecha_emision']
    search_fields = [
        'folio',
        'rut_receptor',
        'razon_social_receptor',
        'track_id'
    ]
    readonly_fields = [
        'fecha_creacion',
        'fecha_envio_sii',
        'fecha_respuesta_sii'
    ]
    
    fieldsets = (
        ('Información General', {
            'fields': ('empresa', 'venta', 'caf_utilizado', 'tipo_dte', 'folio', 'fecha_emision')
        }),
        ('Datos del Receptor', {
            'fields': (
                'rut_receptor',
                'razon_social_receptor',
                'giro_receptor',
                'direccion_receptor',
                'comuna_receptor',
                'ciudad_receptor'
            )
        }),
        ('Montos', {
            'fields': ('monto_neto', 'monto_exento', 'monto_iva', 'monto_total')
        }),
        ('XML y Firma', {
            'fields': ('xml_dte', 'xml_firmado', 'timbre_electronico'),
            'classes': ('collapse',)
        }),
        ('Estado SII', {
            'fields': (
                'estado_sii',
                'track_id',
                'fecha_envio_sii',
                'fecha_respuesta_sii',
                'glosa_sii'
            )
        }),
        ('Documento PDF', {
            'fields': ('pdf_documento',)
        }),
        ('Referencias', {
            'fields': ('documento_referencia',)
        }),
        ('Auditoría', {
            'fields': ('usuario_creacion', 'fecha_creacion')
        }),
    )


@admin.register(EnvioDTE)
class EnvioDTEAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'empresa',
        'cantidad_documentos',
        'fecha_envio',
        'track_id',
        'estado'
    ]
    list_filter = ['empresa', 'estado', 'fecha_envio']
    search_fields = ['track_id', 'empresa__nombre']
    readonly_fields = ['fecha_creacion', 'fecha_respuesta']
    filter_horizontal = ['documentos']
    
    fieldsets = (
        ('Información General', {
            'fields': ('empresa', 'cantidad_documentos', 'estado')
        }),
        ('Documentos', {
            'fields': ('documentos',)
        }),
        ('Envío', {
            'fields': ('xml_envio', 'fecha_envio', 'track_id')
        }),
        ('Respuesta', {
            'fields': ('xml_respuesta', 'fecha_respuesta', 'glosa_respuesta')
        }),
        ('Auditoría', {
            'fields': ('usuario', 'fecha_creacion')
        }),
    )


@admin.register(AcuseRecibo)
class AcuseReciboAdmin(admin.ModelAdmin):
    list_display = [
        'dte',
        'tipo_acuse',
        'fecha_recepcion',
        'procesado'
    ]
    list_filter = ['tipo_acuse', 'procesado', 'fecha_recepcion']
    search_fields = ['dte__folio', 'dte__rut_receptor']
    readonly_fields = ['fecha_recepcion']
    
    fieldsets = (
        ('Información General', {
            'fields': ('dte', 'tipo_acuse', 'procesado')
        }),
        ('Acuse', {
            'fields': ('xml_acuse', 'fecha_recepcion')
        }),
    )
