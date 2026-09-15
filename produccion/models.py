from django.db import models


class PermisoProduccion(models.Model):
    """Permisos para el módulo de Producción"""
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ('view_produccion', 'Ver Módulo y Órdenes de Producción'),
            ('add_produccion', 'Crear Órdenes de Producción'),
            ('change_produccion', 'Modificar / Procesar Órdenes de Producción'),
            ('delete_produccion', 'Anular / Eliminar Órdenes de Producción'),
        ]
        verbose_name = 'Producción'
        verbose_name_plural = 'Producción'

