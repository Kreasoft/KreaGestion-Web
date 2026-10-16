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
        ('confirmada', 'Pendiente'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]
    ESTADOS_PENDIENTES = ('borrador', 'confirmada', 'en_proceso', 'preparando_despacho')
    
    # Relaciones
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente", related_name="ordenes_pedido")
    bodega = models.ForeignKey(Bodega, on_delete=models.CASCADE, verbose_name="Bodega")
    
    # Vendedor
    vendedor = models.ForeignKey(
        'ventas.Vendedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordenes_pedido',
        verbose_name="Vendedor"
    )
    
    # Vinculación con Cotización
    cotizacion = models.ForeignKey(
        'ventas.Venta',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordenes_pedido_generadas',
        verbose_name="Cotización Asociada"
    )
    
    # Información del pedido
    numero_pedido = models.CharField(max_length=20, verbose_name="Número de Pedido")
    fecha_pedido = models.DateField(default=timezone.now, verbose_name="Fecha de Pedido")
    fecha_entrega_estimada = models.DateField(blank=True, null=True, verbose_name="Fecha de Entrega Estimada")
    
    # Información de OC del cliente (opcional)
    numero_oc_cliente = models.CharField(max_length=50, blank=True, verbose_name="N° OC Cliente")
    fecha_oc_cliente = models.DateField(blank=True, null=True, verbose_name="Fecha OC Cliente")
    
    # Estado
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='confirmada', verbose_name="Estado")
    
    # Totales
    subtotal = models.IntegerField(default=0, verbose_name="Subtotal")
    descuentos_totales = models.IntegerField(default=0, verbose_name="Descuentos Totales")
    impuestos_totales = models.IntegerField(default=0, verbose_name="Impuestos Totales")
    total_pedido = models.IntegerField(default=0, verbose_name="Total Pedido")
    
    # Información adicional
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    condiciones_pago = models.CharField(max_length=100, blank=True, verbose_name="Condiciones de Pago")
    
    # Dirección de Despacho seleccionada
    direccion_cliente = models.ForeignKey(
        'clientes.DireccionCliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordenes_pedido',
        verbose_name="Dirección / Sucursal Seleccionada"
    )
    direccion_despacho = models.CharField(max_length=255, blank=True, verbose_name="Dirección de Despacho")
    comuna_despacho = models.CharField(max_length=100, blank=True, verbose_name="Comuna de Despacho")
    ciudad_despacho = models.CharField(max_length=100, blank=True, verbose_name="Ciudad de Despacho")
    
    # Auditoría
    creado_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pedidos_creados', verbose_name="Creado por")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Modificación")
    
    class Meta:
        verbose_name = "Orden de Pedido"
        verbose_name_plural = "Órdenes de Pedido"
        ordering = ['-fecha_pedido', '-numero_pedido']
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'numero_pedido'],
                name='pedido_numero_unico_por_empresa',
            ),
        ]
    
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
        """Genera el correlativo independiente y garantizado único de la empresa activa."""
        import re
        pedidos_empresa = OrdenPedido.objects.filter(empresa=self.empresa).values_list('numero_pedido', flat=True)
        
        max_num = 0
        for num_str in pedidos_empresa:
            if not num_str:
                continue
            match = re.search(r'(\d+)$', str(num_str))
            if match:
                try:
                    val = int(match.group(1))
                    if val < 100000000:
                        if val > max_num:
                            max_num = val
                except ValueError:
                    pass
        
        nuevo_numero = max_num + 1
        candidato = f"PED-{nuevo_numero:06d}"
        
        while OrdenPedido.objects.filter(empresa=self.empresa, numero_pedido=candidato).exists():
            nuevo_numero += 1
            candidato = f"PED-{nuevo_numero:06d}"
            
        self.numero_pedido = candidato
        return self.numero_pedido

    @classmethod
    def con_saldo_pendiente(cls, empresa=None):
        """Pedidos con al menos un ítem cuya cantidad aún no está despachada."""
        from django.db.models import Sum, F, Q, DecimalField, Value
        from django.db.models.functions import Coalesce

        items_pendientes = ItemOrdenPedido.objects.annotate(
            despachado=Coalesce(
                Sum(
                    'despachos__cantidad',
                    filter=~Q(despachos__orden_despacho__estado='cancelado'),
                ),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        ).filter(despachado__lt=F('cantidad'))
        qs = cls.objects.filter(
            pk__in=items_pendientes.values('orden_pedido_id')
        ).exclude(estado__in=['completada', 'cancelada'])
        if empresa is not None:
            qs = qs.filter(empresa=empresa)
        return qs

    def estado_por_despacho(self):
        """Ingresado = pendiente (listo para despachar). Completada solo si ya no queda saldo."""
        if self.estado == 'cancelada':
            return 'cancelada'
        items = list(self.items.all())
        if items and all(item.cantidad_pendiente <= 0 for item in items) and any(item.cantidad_despachada > 0 for item in items):
            return 'completada'
        return 'confirmada'

    def etiqueta_estado(self):
        if self.estado == 'cancelada':
            return 'Cancelada'
        if self.estado == 'completada':
            return 'Completada'
        return 'Pendiente'

    def puede_despachar(self):
        return self.estado != 'cancelada' and self.tiene_saldo_pendiente()

    def tiene_saldo_pendiente(self):
        return any(item.cantidad_pendiente > 0 for item in self.items.all())

    def monto_saldo_pendiente(self):
        return sum(item.get_total_pendiente() for item in self.items.all())

    @classmethod
    def total_saldo_por_despachar(cls, qs):
        total = 0
        for pedido in qs.prefetch_related('items__despachos__orden_despacho'):
            total += pedido.monto_saldo_pendiente()
        return total

    def actualizar_estado_segun_despachos(self):
        """Alinea el estado del pedido con el avance real del despacho."""
        if self.estado == 'cancelada':
            return
        nuevo = self.estado_por_despacho()
        if nuevo != self.estado:
            self.estado = nuevo
            self.save(update_fields=['estado', 'fecha_modificacion'])

    @classmethod
    def sincronizar_estados_por_despacho(cls, empresa=None):
        qs = cls.objects.exclude(estado='cancelada')
        if empresa is not None:
            qs = qs.filter(empresa=empresa)
        qs = qs.prefetch_related('items__despachos__orden_despacho')
        for pedido in qs:
            pedido.actualizar_estado_segun_despachos()


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
    
    def save(self, *args, **kwargs):
        """Failsafe para asegurar que el impuesto nunca sea nulo en la BD"""
        if self.impuesto_porcentaje is None:
            self.impuesto_porcentaje = 19
        super().save(*args, **kwargs)
    
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

    def get_total_pendiente(self):
        """Total del saldo aún no despachado (misma lógica de precio/IVA del ítem)."""
        pendiente = self.cantidad_pendiente
        if pendiente <= 0:
            return 0
        subtotal = int(Decimal(str(pendiente)) * Decimal(str(self.precio_unitario)))
        descuento = int(subtotal * Decimal(str(self.descuento_porcentaje or 0)) / Decimal('100'))
        base = subtotal - descuento
        impuesto = int(base * Decimal(str(self.impuesto_porcentaje or 0)) / Decimal('100'))
        return base + impuesto

    @property
    def cantidad_despachada(self):
        """Cantidad ya asignada a despachos vigentes (no cancelados)."""
        total_despachado = self.despachos.exclude(
            orden_despacho__estado='cancelado'
        ).aggregate(total=models.Sum('cantidad'))['total'] or Decimal('0')
        return total_despachado

    @property
    def cantidad_pendiente(self):
        """Calcula la cantidad pendiente por despachar."""
        return self.cantidad - self.cantidad_despachada


# Importar modelos de despacho y transporte
from .models_despacho import OrdenDespacho, DetalleOrdenDespacho
from .models_transporte import Chofer, Vehiculo
