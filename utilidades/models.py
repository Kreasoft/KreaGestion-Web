from django.db import models


class PermisoUtilidad(models.Model):
    """Permisos para el módulo de Utilidades"""
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ('view_utilidades', 'Ver Utilidades del Sistema y Diseños'),
        ]
        verbose_name = 'Utilidad'
        verbose_name_plural = 'Utilidades'

