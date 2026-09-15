from django.db import models


class PermisoInforme(models.Model):
    """Permisos para el módulo de Informes"""
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ('view_informe', 'Ver Dashboard de Informes'),
            ('ver_informe_ventas', 'Ver Informes de Ventas (Período, Vendedor, Productos)'),
            ('ver_informe_stock', 'Ver Informes de Inventario y Stock'),
            ('ver_informe_compras', 'Ver Informes de Compras por Período'),
            ('ver_informe_tesoreria', 'Ver Informes de Tesorería (Cuentas por Cobrar y Pagos)'),
            ('ver_informe_caja', 'Ver Informes de Cierres de Caja'),
            ('ver_informe_rentabilidad', 'Ver Informes de Utilidad y Rentabilidad'),
            ('exportar_informes', 'Exportar Informes a Excel / PDF'),
        ]
        verbose_name = 'Informe'
        verbose_name_plural = 'Informes'

