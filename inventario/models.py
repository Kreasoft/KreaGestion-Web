from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from empresas.models import Empresa
from bodegas.models import Bodega
from articulos.models import Articulo

# Los modelos de ajustes se manejan directamente en las vistas


class TransferenciaInventario(models.Model):
    """Modelo para agrupar transferencias de múltiples artículos"""
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('confirmado', 'Confirmado'),
        ('cancelado', 'Cancelado'),
    ]
    
    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.CASCADE, related_name='transferencias')
    numero_folio = models.CharField(max_length=20, unique=True, verbose_name="Número de Folio")
    bodega_origen = models.ForeignKey('bodegas.Bodega', on_delete=models.CASCADE, related_name='transferencias_origen')
    bodega_destino = models.ForeignKey('bodegas.Bodega', on_delete=models.CASCADE, related_name='transferencias_destino', null=True, blank=True)
    
    fecha_transferencia = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Transferencia")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='confirmado')
    
    # Guía de despacho asociada
    guia_despacho = models.ForeignKey(
        'facturacion_electronica.DocumentoTributarioElectronico',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transferencias',
        verbose_name="Guía de Despacho"
    )
    
    creado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Transferencia de Inventario"
        verbose_name_plural = "Transferencias de Inventario"
        ordering = ['-fecha_transferencia']
    
    def __str__(self):
        return f"{self.numero_folio} - {self.bodega_origen.nombre} → {self.bodega_destino.nombre}"


class Inventario(models.Model):
    """Modelo para gestionar el inventario de productos"""
    
    TIPO_MOVIMIENTO_CHOICES = [
        ('entrada', 'Entrada'),
        ('salida', 'Salida'),
        ('ajuste', 'Ajuste'),
        ('transferencia', 'Transferencia'),
    ]
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('confirmado', 'Confirmado'),
        ('cancelado', 'Cancelado'),
        ('completado', 'Completado'),
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='inventarios')
    bodega_destino = models.ForeignKey(Bodega, on_delete=models.CASCADE, related_name='inventarios_destino', null=True, blank=True)
    bodega_origen = models.ForeignKey(Bodega, on_delete=models.CASCADE, related_name='inventarios_origen', null=True, blank=True)
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, related_name='inventarios')
    
    # Relación con transferencia agrupada (para transferencias con múltiples artículos)
    transferencia = models.ForeignKey(
        TransferenciaInventario,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='detalles',
        verbose_name="Transferencia"
    )
    
    # Número de folio para ajustes
    numero_folio = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número de Folio")
    
    # Información del movimiento
    tipo_movimiento = models.CharField(
        max_length=20, 
        choices=TIPO_MOVIMIENTO_CHOICES,
        verbose_name="Tipo de Movimiento"
    )
    cantidad = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        verbose_name="Cantidad"
    )
    precio_unitario = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Precio Unitario",
        default=0
    )
    total = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Total",
        default=0
    )
    
    # Información adicional
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción del Movimiento")
    motivo = models.TextField(blank=True, null=True, verbose_name="Motivo del Movimiento")
    numero_documento = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name="Número de Documento"
    )
    proveedor = models.CharField(
        max_length=200, 
        blank=True, 
        null=True, 
        verbose_name="Proveedor"
    )
    
    # Estado y auditoría
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    fecha_movimiento = models.DateTimeField(verbose_name="Fecha del Movimiento", default=timezone.now)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"
        ordering = ['-fecha_movimiento', '-fecha_creacion']
    
    def __str__(self):
        return f"{self.get_tipo_movimiento_display()} - {self.articulo.nombre} - {self.cantidad}"
    
    def save(self, *args, **kwargs):
        """Calcula el total automáticamente"""
        self.total = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)
    
    def get_tipo_badge_class(self):
        """Retorna la clase CSS para el badge del tipo de movimiento"""
        classes = {
            'entrada': 'bg-success',
            'salida': 'bg-danger',
            'ajuste': 'bg-warning',
            'transferencia': 'bg-info',
        }
        return classes.get(self.tipo_movimiento, 'bg-secondary')
    
    def get_estado_badge_class(self):
        """Retorna la clase CSS para el badge del estado"""
        classes = {
            'pendiente': 'bg-warning',
            'confirmado': 'bg-success',
            'cancelado': 'bg-danger',
            'completado': 'bg-primary',
        }
        return classes.get(self.estado, 'bg-secondary')


class Stock(models.Model):
    """Modelo para controlar el stock actual de cada artículo por bodega"""
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='stocks')
    bodega = models.ForeignKey(Bodega, on_delete=models.CASCADE, related_name='stocks')
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, related_name='stocks')
    
    # Stock actual
    cantidad = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Cantidad"
    )
    stock_minimo = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Stock Mínimo"
    )
    stock_maximo = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Stock Máximo"
    )
    
    # Precio promedio
    precio_promedio = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Precio Promedio"
    )
    
    # Auditoría
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Stock"
        verbose_name_plural = "Stocks"
        unique_together = ['empresa', 'bodega', 'articulo']
        ordering = ['articulo__nombre']
    
    def __str__(self):
        return f"{self.articulo.nombre} - {self.bodega.nombre} - Stock: {self.cantidad}"
    
    def get_estado_stock(self):
        """Retorna el estado del stock"""
        if self.cantidad <= 0:
            return 'sin_stock'
        elif self.cantidad <= self.stock_minimo:
            return 'stock_bajo'
        elif self.cantidad >= self.stock_maximo:
            return 'stock_alto'
        else:
            return 'stock_normal'
    
    def get_estado_badge_class(self):
        """Retorna la clase CSS para el badge del estado del stock"""
        classes = {
            'sin_stock': 'bg-danger',
            'stock_bajo': 'bg-warning',
            'stock_normal': 'bg-success',
            'stock_alto': 'bg-info',
        }
        return classes.get(self.get_estado_stock(), 'bg-secondary')
    
    def get_estado_text(self):
        """Retorna el texto del estado del stock"""
        textos = {
            'sin_stock': 'Sin Stock',
            'stock_bajo': 'Stock Bajo',
            'stock_normal': 'Stock Normal',
            'stock_alto': 'Stock Alto',
        }
        return textos.get(self.get_estado_stock(), 'Desconocido')


