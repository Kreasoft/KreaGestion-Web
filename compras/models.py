from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from empresas.models import Empresa, Sucursal
# from proveedores.models import Proveedor
# from productos.models import Producto


class OrdenCompra(models.Model):
    """Modelo para gestionar órdenes de compra a proveedores"""
    
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('pendiente_aprobacion', 'Pendiente de Aprobación'),
        ('aprobada', 'Aprobada'),
        ('en_proceso', 'En Proceso'),
        ('parcialmente_recibida', 'Parcialmente Recibida'),
        ('completamente_recibida', 'Completamente Recibida'),
        ('cancelada', 'Cancelada'),
        ('cerrada', 'Cerrada'),
    ]
    
    PRIORIDAD_CHOICES = [
        ('baja', 'Baja'),
        ('normal', 'Normal'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE)
    proveedor = models.CharField(max_length=200, verbose_name="Proveedor")  # Temporal
    
    # Información de la orden
    numero_orden = models.CharField(max_length=20, unique=True, verbose_name="Número de Orden")
    fecha_orden = models.DateField(default=timezone.now, verbose_name="Fecha de Orden")
    fecha_entrega_esperada = models.DateField(verbose_name="Fecha de Entrega Esperada")
    fecha_entrega_real = models.DateField(blank=True, null=True, verbose_name="Fecha de Entrega Real")
    
    # Estado y prioridad
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='borrador')
    prioridad = models.CharField(max_length=20, choices=PRIORIDAD_CHOICES, default='normal')
    
    # Información adicional
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    condiciones_pago = models.CharField(max_length=200, blank=True, verbose_name="Condiciones de Pago")
    plazo_entrega = models.CharField(max_length=100, blank=True, verbose_name="Plazo de Entrega")
    
    # Totales
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    iva = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    descuento = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Auditoría
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_creadas')
    aprobado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_aprobadas')
    fecha_aprobacion = models.DateTimeField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Orden de Compra"
        verbose_name_plural = "Órdenes de Compra"
        ordering = ['-fecha_orden', '-numero_orden']
    
    def __str__(self):
        return f"OC-{self.numero_orden} - {self.proveedor}"
    
    def calcular_totales(self):
        """Calcula los totales de la orden de compra"""
        subtotal = sum(item.subtotal for item in self.items.all())
        iva = subtotal * Decimal('0.19')  # 19% IVA
        self.subtotal = subtotal
        self.iva = iva
        self.total = subtotal + iva - self.descuento
        self.save()
    
    def get_estado_display_color(self):
        """Retorna el color CSS para el estado"""
        colores = {
            'borrador': 'secondary',
            'pendiente_aprobacion': 'warning',
            'aprobada': 'info',
            'en_proceso': 'primary',
            'parcialmente_recibida': 'warning',
            'completamente_recibida': 'success',
            'cancelada': 'danger',
            'cerrada': 'dark',
        }
        return colores.get(self.estado, 'secondary')
    
    def puede_aprobar(self):
        """Verifica si la orden puede ser aprobada"""
        return self.estado == 'pendiente_aprobacion'
    
    def puede_recibir(self):
        """Verifica si la orden puede recibir mercancías"""
        return self.estado in ['aprobada', 'en_proceso', 'parcialmente_recibida']


class ItemOrdenCompra(models.Model):
    """Items individuales de una orden de compra"""
    
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name='items')
    producto = models.CharField(max_length=200, verbose_name="Producto")  # Temporal
    
    cantidad_solicitada = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Cantidad Solicitada"
    )
    cantidad_recibida = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        verbose_name="Cantidad Recibida"
    )
    
    precio_unitario = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Precio Unitario"
    )
    descuento_unitario = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        verbose_name="Descuento Unitario"
    )
    
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Subtotal")
    
    # Información adicional
    especificaciones = models.TextField(blank=True, verbose_name="Especificaciones")
    fecha_entrega_item = models.DateField(blank=True, null=True, verbose_name="Fecha de Entrega del Item")
    
    class Meta:
        verbose_name = "Item de Orden de Compra"
        verbose_name_plural = "Items de Órdenes de Compra"
        unique_together = ['orden_compra', 'producto']
    
    def __str__(self):
        return f"{self.producto} - {self.cantidad_solicitada}"
    
    def save(self, *args, **kwargs):
        """Calcula el subtotal al guardar"""
        self.subtotal = (self.precio_unitario - self.descuento_unitario) * self.cantidad_solicitada
        super().save(*args, **kwargs)
        self.orden_compra.calcular_totales()
    
    def get_cantidad_pendiente(self):
        """Retorna la cantidad pendiente de recibir"""
        return self.cantidad_solicitada - self.cantidad_recibida
    
    def get_porcentaje_recibido(self):
        """Retorna el porcentaje de cantidad recibida"""
        if self.cantidad_solicitada > 0:
            return (self.cantidad_recibida / self.cantidad_solicitada) * 100
        return 0


class RecepcionMercancia(models.Model):
    """Modelo para gestionar la recepción de mercancías de órdenes de compra"""
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_revision', 'En Revisión'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]
    
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name='recepciones')
    numero_recepcion = models.CharField(max_length=20, unique=True, verbose_name="Número de Recepción")
    fecha_recepcion = models.DateField(default=timezone.now, verbose_name="Fecha de Recepción")
    
    # Estado de la recepción
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    
    # Información del transporte
    transportista = models.CharField(max_length=200, blank=True, verbose_name="Transportista")
    numero_guia = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número de Guía")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    
    # Auditoría
    recibido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    revisado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='recepciones_revisadas')
    fecha_revision = models.DateTimeField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Recepción de Mercancía"
        verbose_name_plural = "Recepciones de Mercancías"
        ordering = ['-fecha_recepcion', '-numero_recepcion']
    
    def __str__(self):
        return f"RM-{self.numero_recepcion} - {self.orden_compra.numero_orden}"
    
    def get_estado_display_color(self):
        """Retorna el color CSS para el estado"""
        colores = {
            'pendiente': 'warning',
            'en_revision': 'info',
            'aprobada': 'success',
            'rechazada': 'danger',
        }
        return colores.get(self.estado, 'secondary')


class ItemRecepcion(models.Model):
    """Items individuales de una recepción de mercancía"""
    
    recepcion = models.ForeignKey(RecepcionMercancia, on_delete=models.CASCADE, related_name='items')
    item_orden = models.ForeignKey(ItemOrdenCompra, on_delete=models.CASCADE)
    
    cantidad_recibida = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Cantidad Recibida"
    )
    
    # Calidad y estado
    calidad_aceptable = models.BooleanField(default=True, verbose_name="Calidad Aceptable")
    observaciones_calidad = models.TextField(blank=True, verbose_name="Observaciones de Calidad")
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Item de Recepción"
        verbose_name_plural = "Items de Recepción"
        unique_together = ['recepcion', 'item_orden']
    
    def __str__(self):
        return f"{self.item_orden.producto} - {self.cantidad_recibida}"
    
    def save(self, *args, **kwargs):
        """Actualiza la cantidad recibida del item de la orden"""
        super().save(*args, **kwargs)
        # Actualizar cantidad recibida en el item de la orden
        self.item_orden.cantidad_recibida = sum(
            item.cantidad_recibida for item in self.item_orden.recepciones.all()
        )
        self.item_orden.save()
        
        # Actualizar estado de la orden de compra
        self.actualizar_estado_orden()
    
    def actualizar_estado_orden(self):
        """Actualiza el estado de la orden de compra según las recepciones"""
        orden = self.recepcion.orden_compra
        total_solicitado = sum(item.cantidad_solicitada for item in orden.items.all())
        total_recibido = sum(item.cantidad_recibida for item in orden.items.all())
        
        if total_recibido == 0:
            orden.estado = 'aprobada'
        elif total_recibido < total_solicitado:
            orden.estado = 'parcialmente_recibida'
        else:
            orden.estado = 'completamente_recibida'
        
        orden.save()


class CuentaCorrienteProveedor(models.Model):
    """Modelo para gestionar la cuenta corriente de proveedores"""
    
    TIPO_MOVIMIENTO_CHOICES = [
        ('compra', 'Compra'),
        ('pago', 'Pago'),
        ('nota_credito', 'Nota de Crédito'),
        ('nota_debito', 'Nota de Débito'),
        ('ajuste', 'Ajuste'),
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    proveedor = models.CharField(max_length=200, verbose_name="Proveedor")  # Temporal
    
    # Información del movimiento
    fecha = models.DateField(default=timezone.now, verbose_name="Fecha del Movimiento")
    tipo_movimiento = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO_CHOICES, verbose_name="Tipo de Movimiento")
    
    # Referencias
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.SET_NULL, null=True, blank=True)
    factura_proveedor = models.CharField(max_length=50, blank=True, verbose_name="Número de Factura del Proveedor")
    
    # Montos
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Monto")
    saldo_anterior = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Saldo Anterior")
    saldo_nuevo = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Saldo Nuevo")
    
    # Información adicional
    descripcion = models.TextField(verbose_name="Descripción")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    
    # Auditoría
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Movimiento de Cuenta Corriente de Proveedor"
        verbose_name_plural = "Movimientos de Cuenta Corriente de Proveedores"
        ordering = ['-fecha', '-id']
    
    def __str__(self):
        return f"{self.proveedor} - {self.tipo_movimiento} - {self.monto}"
    
    def save(self, *args, **kwargs):
        """Calcula el saldo nuevo al guardar"""
        if not self.pk:  # Solo para nuevos registros
            # Obtener el último saldo del proveedor
            ultimo_movimiento = CuentaCorrienteProveedor.objects.filter(
                empresa=self.empresa,
                proveedor=self.proveedor
            ).order_by('-fecha', '-id').first()
            
            if ultimo_movimiento:
                self.saldo_anterior = ultimo_movimiento.saldo_nuevo
            else:
                self.saldo_anterior = Decimal('0.00')
            
            # Calcular saldo nuevo según el tipo de movimiento
            if self.tipo_movimiento in ['compra', 'nota_debito', 'ajuste']:
                self.saldo_nuevo = self.saldo_anterior + self.monto
            else:  # pago, nota_credito
                self.saldo_nuevo = self.saldo_anterior - self.monto
        
        super().save(*args, **kwargs)
    
    def get_tipo_movimiento_display_color(self):
        """Retorna el color CSS para el tipo de movimiento"""
        colores = {
            'compra': 'danger',
            'pago': 'success',
            'nota_credito': 'info',
            'nota_debito': 'warning',
            'ajuste': 'secondary',
        }
        return colores.get(self.tipo_movimiento, 'secondary')
