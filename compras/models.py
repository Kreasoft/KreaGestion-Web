from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from empresas.models import Empresa, Sucursal
from proveedores.models import Proveedor
from articulos.models import Articulo
from bodegas.models import Bodega


class OrdenCompra(models.Model):
    """Modelo para gestionar órdenes de compra a proveedores"""
    
    ESTADO_ORDEN_CHOICES = [
        ('en_proceso', 'En Proceso'),
        ('aprobada', 'Aprobada'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]
    
    ESTADO_PAGO_CHOICES = [
        ('pagada', 'Pagada'),
        ('credito', 'Crédito'),
        ('parcial', 'Pago Parcial'),
        ('vencida', 'Vencida'),
    ]
    
    PRIORIDAD_CHOICES = [
        ('baja', 'Baja'),
        ('normal', 'Normal'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, verbose_name="Sucursal", null=True, blank=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, verbose_name="Proveedor")
    bodega = models.ForeignKey(Bodega, on_delete=models.CASCADE, verbose_name="Bodega", null=True, blank=True)
    
    # Información de la orden
    numero_orden = models.CharField(max_length=20, unique=True, verbose_name="Número de Orden")
    fecha_orden = models.DateField(default=timezone.now, verbose_name="Fecha de Orden")
    fecha_entrega_esperada = models.DateField(verbose_name="Fecha de Entrega Esperada")
    fecha_entrega_real = models.DateField(blank=True, null=True, verbose_name="Fecha de Entrega Real")
    
    # Estados
    estado_orden = models.CharField(max_length=30, choices=ESTADO_ORDEN_CHOICES, default='en_proceso', verbose_name="Estado de la Orden")
    estado_pago = models.CharField(max_length=20, choices=ESTADO_PAGO_CHOICES, default='credito', verbose_name="Estado de Pago")
    prioridad = models.CharField(max_length=20, choices=PRIORIDAD_CHOICES, default='normal', verbose_name="Prioridad")
    
    # Información adicional
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    condiciones_pago = models.CharField(max_length=200, blank=True, verbose_name="Condiciones de Pago")
    plazo_entrega = models.CharField(max_length=100, blank=True, verbose_name="Plazo de Entrega")
    
    # Totales (usando IntegerField como en documentos)
    subtotal = models.IntegerField(default=0, verbose_name="Subtotal")
    descuentos_totales = models.IntegerField(default=0, verbose_name="Descuentos Totales")
    impuestos_totales = models.IntegerField(default=0, verbose_name="Impuestos Totales")
    total_orden = models.IntegerField(default=0, verbose_name="Total Orden")
    
    # Campos para cuentas corrientes (similar a documentos)
    en_cuenta_corriente = models.BooleanField(default=False, verbose_name="En Cuenta Corriente")
    fecha_registro_cc = models.DateTimeField(blank=True, null=True, verbose_name="Fecha Registro CC")
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Monto Pagado")
    saldo_pendiente = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Saldo Pendiente")
    
    # Auditoría
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_compra_creadas', verbose_name="Creado por")
    aprobado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordenes_aprobadas')
    fecha_aprobacion = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de Aprobación")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Modificación")
    
    class Meta:
        verbose_name = "Orden de Compra"
        verbose_name_plural = "Órdenes de Compra"
        ordering = ['-fecha_orden', '-numero_orden']
    
    def __str__(self):
        return f"OC-{self.numero_orden} - {self.proveedor.nombre}"
    
    def calcular_totales(self):
        """Calcula los totales de la orden de compra basado en sus items"""
        # Marcar que estamos calculando totales para evitar bucles infinitos
        self._calculando_totales = True
        
        items = self.items.all()
        
        self.subtotal = sum(item.get_subtotal() for item in items)
        self.descuentos_totales = sum(item.get_descuento_monto() for item in items)
        self.impuestos_totales = sum(item.get_impuesto_monto() for item in items)
        self.total_orden = self.subtotal - self.descuentos_totales + self.impuestos_totales
        
        # Actualizar saldo pendiente
        self.saldo_pendiente = self.total_orden - self.monto_pagado
        
        # El estado de pago se maneja en el modelo CuentaCorrienteProveedor
        
        self.save()
        
        # Limpiar la marca
        delattr(self, '_calculando_totales')
    
    def get_estado_display_color(self):
        """Retorna el color CSS para el estado de la orden"""
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
        return colores.get(self.estado_orden, 'secondary')
    
    def get_estado_pago_display_color(self):
        """Retorna el color CSS para el estado de pago"""
        colores = {
            'pagada': 'success',
            'credito': 'info',
            'parcial': 'warning',
            'vencida': 'danger',
        }
        return colores.get(self.estado_pago, 'secondary')
    
    def puede_editar(self):
        """Verifica si la orden puede ser editada"""
        return self.estado_orden in ['borrador', 'pendiente_aprobacion']
    
    def puede_aprobar(self):
        """Verifica si la orden puede ser aprobada"""
        return self.estado_orden == 'pendiente_aprobacion'
    
    def puede_recibir(self):
        """Verifica si la orden puede recibir mercancías"""
        return self.estado_orden in ['aprobada', 'en_proceso', 'parcialmente_recibida']
    
    def debe_ir_a_cuenta_corriente(self):
        """Verifica si la orden debe ir a cuenta corriente"""
        return self.estado_pago in ['credito', 'parcial'] and self.estado_orden == 'aprobada'
    
    def registrar_en_cuenta_corriente(self):
        """Registra la orden en cuenta corriente"""
        if self.debe_ir_a_cuenta_corriente() and not self.en_cuenta_corriente:
            self.en_cuenta_corriente = True
            self.fecha_registro_cc = timezone.now()
            self.save()
            return True
        return False


class ItemOrdenCompra(models.Model):
    """Items individuales de una orden de compra"""
    
    orden_compra = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name='items', verbose_name="Orden de Compra")
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, verbose_name="Artículo")
    
    # Información del item
    cantidad_solicitada = models.IntegerField(default=1, validators=[MinValueValidator(1)], verbose_name="Cantidad Solicitada")
    cantidad_recibida = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="Cantidad Recibida")
    precio_unitario = models.IntegerField(validators=[MinValueValidator(0)], verbose_name="Precio Unitario")
    
    # Descuentos e impuestos
    descuento_porcentaje = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="Descuento (%)")
    impuesto_porcentaje = models.IntegerField(default=19, validators=[MinValueValidator(0)], verbose_name="Impuesto (%)")
    
    # Totales del item
    subtotal = models.IntegerField(default=0, verbose_name="Subtotal")
    descuento_monto = models.IntegerField(default=0, verbose_name="Descuento Monto")
    impuesto_monto = models.IntegerField(default=0, verbose_name="Impuesto Monto")
    total_item = models.IntegerField(default=0, verbose_name="Total Item")
    
    # Información adicional
    especificaciones = models.TextField(blank=True, verbose_name="Especificaciones")
    fecha_entrega_item = models.DateField(blank=True, null=True, verbose_name="Fecha de Entrega del Item")
    
    class Meta:
        verbose_name = "Item de Orden de Compra"
        verbose_name_plural = "Items de Órdenes de Compra"
        unique_together = ['orden_compra', 'articulo']
        ordering = ['id']
    
    def __str__(self):
        return f"{self.articulo.nombre} - {self.cantidad_solicitada}"
    
    def save(self, *args, **kwargs):
        """Calcula automáticamente los totales al guardar"""
        self.subtotal = self.cantidad_solicitada * self.precio_unitario
        self.descuento_monto = round(self.subtotal * (self.descuento_porcentaje / 100))
        self.impuesto_monto = round((self.subtotal - self.descuento_monto) * (self.impuesto_porcentaje / 100))
        self.total_item = self.subtotal - self.descuento_monto + self.impuesto_monto
        super().save(*args, **kwargs)
        
        # Solo calcular totales si no estamos en medio de un cálculo de totales
        if not hasattr(self.orden_compra, '_calculando_totales'):
            self.orden_compra.calcular_totales()
    
    def get_subtotal(self):
        """Retorna el subtotal del item"""
        return self.cantidad_solicitada * self.precio_unitario
    
    def get_descuento_monto(self):
        """Retorna el monto del descuento"""
        return round(self.subtotal * (self.descuento_porcentaje / 100))
    
    def get_impuesto_monto(self):
        """Retorna el monto del impuesto"""
        return round((self.subtotal - self.get_descuento_monto()) * (self.impuesto_porcentaje / 100))
    
    def get_total(self):
        """Retorna el total del item"""
        return self.get_subtotal() - self.get_descuento_monto() + self.get_impuesto_monto()
    
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
        return f"{self.item_orden.articulo.nombre} - {self.cantidad_recibida}"
    
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
            orden.estado_orden = 'aprobada'
        elif total_recibido < total_solicitado:
            orden.estado_orden = 'parcialmente_recibida'
        else:
            orden.estado_orden = 'completamente_recibida'
        
        orden.save()


