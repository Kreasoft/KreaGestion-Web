"""
Modelos para gestionar Órdenes de Despacho
Permiten la trazabilidad de pedidos y vinculación con guías y facturas
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal

from empresas.models import Empresa
from .models import OrdenPedido, ItemOrdenPedido


class OrdenDespacho(models.Model):
    """
    Orden de Despacho para controlar el despacho de pedidos
    Permite vincular pedidos con guías de despacho y facturas
    """
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_preparacion', 'En Preparación'),
        ('despachado', 'Despachado'),
        ('en_transito', 'En Tránsito'),
        ('entregado', 'Entregado'),
        ('cancelado', 'Cancelado'),
    ]
    
    # Relaciones principales
    empresa = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.CASCADE,
        verbose_name="Empresa",
        related_name='ordenes_despacho'
    )
    
    orden_pedido = models.ForeignKey(
        OrdenPedido,
        on_delete=models.CASCADE,
        verbose_name="Orden de Pedido",
        related_name='despachos'
    )
    
    # Información del despacho
    numero_despacho = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Número de Despacho"
    )
    
    fecha_despacho = models.DateField(
        default=timezone.now,
        verbose_name="Fecha de Despacho"
    )
    
    fecha_entrega_estimada = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de Entrega Estimada"
    )
    
    fecha_entrega_real = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de Entrega Real"
    )
    
    # Estado
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name="Estado"
    )
    
    # Información de transporte
    chofer = models.ForeignKey(
        'Chofer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='despachos',
        verbose_name="Chofer Asignado"
    )
    
    vehiculo = models.ForeignKey(
        'Vehiculo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='despachos',
        verbose_name="Vehículo Asignado"
    )
    
    transportista_externo = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Transportista Externo",
        help_text="Solo si el transporte es externo"
    )
    
    # Información adicional
    direccion_entrega = models.TextField(
        blank=True,
        verbose_name="Dirección de Entrega"
    )
    
    observaciones = models.TextField(
        blank=True,
        verbose_name="Observaciones"
    )
    
    # Auditoría
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='despachos_creados',
        verbose_name="Creado por"
    )
    
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    
    fecha_modificacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Modificación"
    )
    
    class Meta:
        verbose_name = "Orden de Despacho"
        verbose_name_plural = "Órdenes de Despacho"
        ordering = ['-fecha_despacho', '-numero_despacho']
    
    def __str__(self):
        return f"Despacho {self.numero_despacho} - Pedido {self.orden_pedido.numero_pedido}"
    
    def generar_numero_despacho(self):
        """Genera número consecutivo de despacho POR ORDEN DE PEDIDO"""
        # Contar cuántos despachos existen para esta orden de pedido
        despachos_existentes = OrdenDespacho.objects.filter(
            orden_pedido=self.orden_pedido
        ).count()
        
        nuevo_numero = despachos_existentes + 1
        
        # Formato: DESP-<ID_PEDIDO>-<NUMERO_CORRELATIVO>
        self.numero_despacho = f"DESP-{self.orden_pedido.id}-{nuevo_numero}"
        return self.numero_despacho
    
    def get_total_items(self):
        """Retorna la cantidad total de items en el despacho"""
        return self.items.aggregate(
            total=models.Sum('cantidad')
        )['total'] or 0
    
    def save(self, *args, **kwargs):
        """Sobrescribe el método save para actualizar el estado del pedido."""
        super().save(*args, **kwargs)
        # Llama a la actualización del estado de la orden de pedido principal
        self.orden_pedido.actualizar_estado_segun_despachos()

    def get_documentos_asociados(self):
        """Retorna lista de documentos (guías y facturas) asociados"""
        documentos = []
        for item in self.items.all():
            if item.guia_despacho and item.guia_despacho not in documentos:
                documentos.append({
                    'tipo': 'Guía',
                    'numero': item.guia_despacho.folio,
                    'fecha': item.guia_despacho.fecha_emision,
                    'documento': item.guia_despacho
                })
            if item.factura and item.factura not in documentos:
                documentos.append({
                    'tipo': 'Factura',
                    'numero': item.factura.folio,
                    'fecha': item.factura.fecha_emision,
                    'documento': item.factura
                })
        return documentos


class DetalleOrdenDespacho(models.Model):
    """
    Detalle de items de la Orden de Despacho
    Vincula items del pedido con documentos (guías/facturas)
    """
    
    # Relaciones
    orden_despacho = models.ForeignKey(
        OrdenDespacho,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Orden de Despacho"
    )
    
    item_pedido = models.ForeignKey(
        ItemOrdenPedido,
        on_delete=models.CASCADE,
        related_name='despachos',
        verbose_name="Item del Pedido"
    )
    
    # Cantidad a despachar
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Cantidad a Despachar"
    )
    
    # Documentos tributarios asociados
    guia_despacho = models.ForeignKey(
        'facturacion_electronica.DocumentoTributarioElectronico',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='detalles_despacho_guia',
        verbose_name="Guía de Despacho",
        limit_choices_to={'tipo_dte': '52'}  # Solo guías
    )
    
    factura = models.ForeignKey(
        'facturacion_electronica.DocumentoTributarioElectronico',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='detalles_despacho_factura',
        verbose_name="Factura",
        limit_choices_to={'tipo_dte__in': ['33', '34']}  # Facturas
    )
    
    # Información adicional
    lote = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Lote"
    )
    
    fecha_vencimiento = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de Vencimiento"
    )
    
    observaciones = models.TextField(
        blank=True,
        verbose_name="Observaciones"
    )
    
    # Auditoría
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    
    class Meta:
        verbose_name = "Detalle de Orden de Despacho"
        verbose_name_plural = "Detalles de Órdenes de Despacho"
        ordering = ['id']
    
    def __str__(self):
        return f"{self.item_pedido.articulo.nombre} - {self.cantidad}"
    
    def get_articulo(self):
        """Retorna el artículo del item del pedido"""
        return self.item_pedido.articulo
    
    def get_cantidad_pendiente(self):
        """Calcula la cantidad pendiente del item del pedido"""
        total_despachado = DetalleOrdenDespacho.objects.filter(
            item_pedido=self.item_pedido,
            orden_despacho__estado__in=['despachado', 'en_transito', 'entregado']
        ).aggregate(
            total=models.Sum('cantidad')
        )['total'] or 0
        
        return self.item_pedido.cantidad - total_despachado

