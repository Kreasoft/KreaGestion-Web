from django.db import models
from empresas.models import Empresa

class Bodega(models.Model):
    """
    Modelo simple para gestionar bodegas/almacenes de la empresa
    """
    empresa = models.ForeignKey(
        Empresa, 
        on_delete=models.CASCADE, 
        verbose_name="Empresa",
        related_name='bodegas'
    )
    codigo = models.CharField(max_length=20, verbose_name="Código")
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    activa = models.BooleanField(default=True, verbose_name="Activa")

    class Meta:
        verbose_name = "Bodega"
        verbose_name_plural = "Bodegas"
        ordering = ['nombre']
        unique_together = ['empresa', 'codigo']  # Código único por empresa

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"