from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from empresas.models import Empresa
from bodegas.models import Bodega
from articulos.models import Articulo
from django.core.validators import MinValueValidator

class AjusteStock(models.Model):
    """Cabecera de un Ajuste de Inventario (Maestro)"""
    
    TIPO_AJUSTE_CHOICES = [
        ('entrada', 'Entrada de Mercadería (Suma al Stock)'),
        ('salida', 'Salida de Mercadería (Resta al Stock)'),
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='ajustes_stock')
    numero_folio = models.CharField(max_length=20, unique=True, verbose_name="Número de Folio")
    tipo_ajuste = models.CharField(max_length=10, choices=TIPO_AJUSTE_CHOICES, verbose_name="Tipo de Ajuste")
    fecha_ajuste = models.DateTimeField(default=timezone.now, verbose_name="Fecha del Ajuste")
    bodega = models.ForeignKey(Bodega, on_delete=models.CASCADE, related_name='ajustes_stock', verbose_name="Bodega")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Observaciones / Motivo")
    
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Ajuste de Stock"
        verbose_name_plural = "Ajustes de Stock"
        ordering = ['-fecha_ajuste', '-fecha_creacion']

    def __str__(self):
        return f"{self.numero_folio} - {self.get_tipo_ajuste_display()}"


class DetalleAjuste(models.Model):
    """Línea de artículo de un Ajuste de Inventario (Detalle)"""
    
    ajuste = models.ForeignKey(AjusteStock, on_delete=models.CASCADE, related_name='detalles')
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, related_name='detalles_ajuste')
    cantidad = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        verbose_name="Cantidad"
    )
    comentario = models.CharField(max_length=255, blank=True, null=True, verbose_name="Comentario")
    
    # Referencia al movimiento de inventario generado
    movimiento = models.OneToOneField(
        'inventario.Inventario', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='detalle_ajuste_master'
    )

    class Meta:
        verbose_name = "Detalle de Ajuste"
        verbose_name_plural = "Detalles de Ajuste"

    def __str__(self):
        return f"{self.articulo.nombre} - {self.cantidad}"
