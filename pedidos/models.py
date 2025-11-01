from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal

from empresas.models import Empresa
from clientes.models import Cliente
from articulos.models import Articulo
from bodegas.models import Bodega


class OrdenPedido(models.Model):
    """Modelo para gestionar órdenes de pedido de clientes"""
    
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('confirmada', 'Confirmada'),
        ('en_proceso', 'En Proceso'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]
    
    # Relaciones
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente", related_name="ordenes_pedido")
    bodega = models.ForeignKey(Bodega, on_delete=models.CASCADE, verbose_name="Bodega")
    
    # Vinculación con Cotización (OPCIONAL) - Por implementar
    # cotizacion = models.ForeignKey(
    #     'ventas.Cotizacion',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='ordenes_pedido_generadas',
    #     verbose_name="Cotización Asociada"
    # )
    
    # Información del pedido
    numero_pedido = models.CharField(max_length=20, unique=True, verbose_name="Número de Pedido")
    fecha_pedido = models.DateField(default=timezone.now, verbose_name="Fecha de Pedido")
    fecha_entrega_estimada = models.DateField(blank=True, null=True, verbose_name="Fecha de Entrega Estimada")
    
    # Información de OC del cliente (opcional)
    numero_oc_cliente = models.CharField(max_length=50, blank=True, verbose_name="N° OC Cliente")
    fecha_oc_cliente = models.DateField(blank=True, null=True, verbose_name="Fecha OC Cliente")
    
    # Estado
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador', verbose_name="Estado")
    
    # Totales
    subtotal = models.IntegerField(default=0, verbose_name="Subtotal")
    descuentos_totales = models.IntegerField(default=0, verbose_name="Descuentos Totales")
    impuestos_totales = models.IntegerField(default=0, verbose_name="Impuestos Totales")
    total_pedido = models.IntegerField(default=0, verbose_name="Total Pedido")
    
    # Información adicional
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    condiciones_pago = models.CharField(max_length=100, blank=True, verbose_name="Condiciones de Pago")
    
    # Auditoría
    creado_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pedidos_creados', verbose_name="Creado por")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Modificación")
    
    class Meta:
        verbose_name = "Orden de Pedido"
        verbose_name_plural = "Órdenes de Pedido"
        ordering = ['-fecha_pedido', '-numero_pedido']
    
    def __str__(self):
        return f"Pedido {self.numero_pedido} - {self.cliente.nombre}"
    
    def calcular_totales(self):
        """Calcula los totales del pedido basado en sus items"""
        items = self.items.all()
        
        self.subtotal = sum(item.get_subtotal() for item in items)
        self.descuentos_totales = sum(item.get_descuento_monto() for item in items)
        self.impuestos_totales = sum(item.get_impuesto_monto() for item in items)
        self.total_pedido = self.subtotal - self.descuentos_totales + self.impuestos_totales
        
        self.save()
    
    def generar_numero_pedido(self):
        """Genera el número de pedido automático y correlativo"""
        ultimo_pedido = OrdenPedido.objects.filter(
            empresa=self.empresa
        ).order_by('-numero_pedido').first()
        
        if ultimo_pedido and ultimo_pedido.numero_pedido:
            try:
                ultimo_numero = int(ultimo_pedido.numero_pedido.split('-')[-1])
                nuevo_numero = ultimo_numero + 1
            except (ValueError, IndexError):
                nuevo_numero = 1
        else:
            nuevo_numero = 1
        
        self.numero_pedido = f"PED-{nuevo_numero:06d}"
        return self.numero_pedido

    def actualizar_estado_segun_despachos(self):
        """Verifica si todos los items están despachados y actualiza el estado."""
        if self.estado in ['cancelada', 'completada']:
            return

        items = self.items.all()
        if not items:
            return

        # Comprueba si todos los items tienen cantidad pendiente cero o menos
        completada = all(item.cantidad_pendiente <= 0 for item in items)

        if completada:
            self.estado = 'completada'
            self.save(update_fields=['estado', 'fecha_modificacion'])


class ItemOrdenPedido(models.Model):
    """Items de una orden de pedido"""
    
    orden_pedido = models.ForeignKey(OrdenPedido, on_delete=models.CASCADE, related_name='items', verbose_name="Orden de Pedido")
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, verbose_name="Artículo")
    
    # Cantidades
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad")
    
    # Precios
    precio_unitario = models.IntegerField(verbose_name="Precio Unitario")
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Descuento %")
    impuesto_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=19, verbose_name="Impuesto %")
    
    # Información adicional
    observaciones = models.CharField(max_length=200, blank=True, verbose_name="Observaciones")
    
    class Meta:
        verbose_name = "Item de Orden de Pedido"
        verbose_name_plural = "Items de Orden de Pedido"
    
    def __str__(self):
        return f"{self.articulo.nombre} - {self.cantidad} unidades"
    
    def get_subtotal(self):
        """Calcula el subtotal del item (cantidad * precio)"""
        return int(Decimal(str(self.cantidad)) * Decimal(str(self.precio_unitario)))
    
    def get_descuento_monto(self):
        """Calcula el monto del descuento"""
        subtotal = self.get_subtotal()
        return int(subtotal * Decimal(str(self.descuento_porcentaje)) / Decimal('100'))
    
    def get_base_imponible(self):
        """Calcula la base imponible (subtotal - descuento)"""
        return self.get_subtotal() - self.get_descuento_monto()
    
    def get_impuesto_monto(self):
        """Calcula el monto del impuesto"""
        base_imponible = self.get_base_imponible()
        return int(base_imponible * Decimal(str(self.impuesto_porcentaje)) / Decimal('100'))
    
    def get_total(self):
        """Calcula el total del item"""
        return self.get_base_imponible() + self.get_impuesto_monto()

    @property
    def cantidad_despachada(self):
        """Calcula la cantidad total despachada para este item."""
        total_despachado = self.despachos.filter(
            orden_despacho__estado__in=['despachado', 'entregado']
        ).aggregate(total=models.Sum('cantidad'))['total'] or Decimal('0')
        return total_despachado

    @property
    def cantidad_pendiente(self):
        """Calcula la cantidad pendiente por despachar."""
        return self.cantidad - self.cantidad_despachada


# Importar modelos de despacho y transporte
from .models_despacho import OrdenDespacho, DetalleOrdenDespacho
from .models_transporte import Chofer, Vehiculo