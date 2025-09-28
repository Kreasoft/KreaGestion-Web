from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from empresas.models import Empresa, Sucursal
from clientes.models import Cliente
# from productos.models import Producto


class Pedido(models.Model):
    """Modelo para gestionar pedidos de venta"""
    
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('pendiente', 'Pendiente'),
        ('confirmado', 'Confirmado'),
        ('en_preparacion', 'En Preparación'),
        ('listo_entrega', 'Listo para Entrega'),
        ('enviado', 'Enviado'),
        ('entregado', 'Entregado'),
        ('cancelado', 'Cancelado'),
    ]
    
    TIPO_ENTREGA_CHOICES = [
        ('local', 'Retiro en Local'),
        ('domicilio', 'Entrega a Domicilio'),
        ('envio', 'Envío a Otra Ciudad'),
    ]
    
    # Información básica
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    
    # Información del pedido
    numero_pedido = models.CharField(max_length=20, unique=True, verbose_name="Número de Pedido")
    fecha_pedido = models.DateTimeField(default=timezone.now, verbose_name="Fecha del Pedido")
    fecha_entrega_esperada = models.DateTimeField(verbose_name="Fecha de Entrega Esperada")
    fecha_entrega_real = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de Entrega Real")
    
    # Estado y tipo de entrega
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    tipo_entrega = models.CharField(max_length=20, choices=TIPO_ENTREGA_CHOICES, default='local')
    
    # Información de entrega
    direccion_entrega = models.TextField(blank=True, verbose_name="Dirección de Entrega")
    comuna_entrega = models.CharField(max_length=100, blank=True, verbose_name="Comuna de Entrega")
    ciudad_entrega = models.CharField(max_length=100, blank=True, verbose_name="Ciudad de Entrega")
    telefono_contacto = models.CharField(max_length=20, blank=True, verbose_name="Teléfono de Contacto")
    
    # Información adicional
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    instrucciones_entrega = models.TextField(blank=True, verbose_name="Instrucciones de Entrega")
    
    # Totales
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    descuento = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    iva = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Auditoría
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos_creados')
    vendedor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos_vendidos')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-fecha_pedido', '-numero_pedido']
    
    def __str__(self):
        return f"P-{self.numero_pedido} - {self.cliente.nombre}"
    
    def calcular_totales(self):
        """Calcula los totales del pedido"""
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
            'pendiente': 'warning',
            'confirmado': 'info',
            'en_preparacion': 'primary',
            'listo_entrega': 'success',
            'enviado': 'info',
            'entregado': 'success',
            'cancelado': 'danger',
        }
        return colores.get(self.estado, 'secondary')
    
    def puede_confirmar(self):
        """Verifica si el pedido puede ser confirmado"""
        return self.estado == 'pendiente'
    
    def puede_entregar(self):
        """Verifica si el pedido puede ser entregado"""
        return self.estado in ['listo_entrega', 'enviado']


# class ItemPedido(models.Model):
#     """Items individuales de un pedido (temporalmente deshabilitado)"""
#     
#     pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='items')
#     producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
#     
#     cantidad = models.DecimalField(
#         max_digits=10, 
#         decimal_places=2, 
#         validators=[MinValueValidator(Decimal('0.01'))],
#         verbose_name="Cantidad"
#     )
#     
#     precio_unitario = models.DecimalField(
#         max_digits=15, 
#         decimal_places=2, 
#         validators=[MinValueValidator(Decimal('0.01'))],
#         verbose_name="Precio Unitario"
#     )
#     descuento_unitario = models.DecimalField(
#         max_digits=15, 
#         decimal_places=2, 
#         default=Decimal('0.00'),
#         verbose_name="Descuento Unitario"
#     )
#     
#     subtotal = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Subtotal")
#     
#     # Información adicional
#     observaciones = models.TextField(blank=True, verbose_name="Observaciones")
#     
#     class Meta:
#         verbose_name = "Item de Pedido"
#         verbose_name_plural = "Items de Pedidos"
#         unique_together = ['pedido', 'producto']
#     
#     def __str__(self):
#         return f"{self.producto.nombre} - {self.cantidad}"
#     
#     def save(self, *args, **kwargs):
#         """Calcula el subtotal al guardar"""
#         self.subtotal = (self.precio_unitario - self.descuento_unitario) * self.cantidad
#         super().save(*args, **kwargs)
#         self.pedido.calcular_totales()


class Venta(models.Model):
    """Modelo para gestionar las ventas realizadas"""
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagada', 'Pagada'),
        ('parcialmente_pagada', 'Parcialmente Pagada'),
        ('anulada', 'Anulada'),
        ('devuelta', 'Devuelta'),
    ]
    
    FORMA_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('tarjeta_debito', 'Tarjeta de Débito'),
        ('tarjeta_credito', 'Tarjeta de Crédito'),
        ('transferencia', 'Transferencia Bancaria'),
        ('cheque', 'Cheque'),
        ('cuenta_corriente', 'Cuenta Corriente'),
        ('otro', 'Otro'),
    ]
    
    # Información básica
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    pedido = models.ForeignKey(Pedido, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Información de la venta
    numero_venta = models.CharField(max_length=20, unique=True, verbose_name="Número de Venta")
    fecha_venta = models.DateTimeField(default=timezone.now, verbose_name="Fecha de Venta")
    
    # Estado y forma de pago
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES, verbose_name="Forma de Pago")
    
    # Información de pago
    monto_pagado = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        verbose_name="Monto Pagado"
    )
    monto_pendiente = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        verbose_name="Monto Pendiente"
    )
    
    # Totales
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    descuento = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    iva = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Información adicional
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    
    # Auditoría
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas_creadas')
    vendedor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas_vendidas')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-fecha_venta', '-numero_venta']
    
    def __str__(self):
        return f"V-{self.numero_venta} - {self.cliente.nombre}"
    
    def calcular_totales(self):
        """Calcula los totales de la venta"""
        subtotal = sum(item.subtotal for item in self.items.all())
        iva = subtotal * Decimal('0.19')  # 19% IVA
        
        self.subtotal = subtotal
        self.iva = iva
        self.total = subtotal + iva - self.descuento
        self.monto_pendiente = self.total - self.monto_pagado
        self.save()
    
    def get_estado_display_color(self):
        """Retorna el color CSS para el estado"""
        colores = {
            'pendiente': 'warning',
            'pagada': 'success',
            'parcialmente_pagada': 'info',
            'anulada': 'danger',
            'devuelta': 'secondary',
        }
        return colores.get(self.estado, 'secondary')
    
    def registrar_pago(self, monto, forma_pago=None):
        """Registra un pago parcial o total"""
        self.monto_pagado += monto
        if forma_pago:
            self.forma_pago = forma_pago
        
        if self.monto_pagado >= self.total:
            self.estado = 'pagada'
        elif self.monto_pagado > 0:
            self.estado = 'parcialmente_pagada'
        
        self.save()


# class ItemVenta(models.Model):
#     """Items individuales de una venta (temporalmente deshabilitado)"""
#     
#     venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='items')
#     producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
#     
#     cantidad = models.DecimalField(
#         max_digits=10, 
#         decimal_places=2, 
#         validators=[MinValueValidator(Decimal('0.01'))],
#         verbose_name="Cantidad"
#     )
#     
#     precio_unitario = models.DecimalField(
#         max_digits=15, 
#         decimal_places=2, 
#         validators=[MinValueValidator(Decimal('0.01'))],
#         verbose_name="Precio Unitario"
#     )
#     descuento_unitario = models.DecimalField(
#         max_digits=15, 
#         decimal_places=2, 
#         default=Decimal('0.00'),
#         verbose_name="Descuento Unitario"
#     )
#     
#     subtotal = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Subtotal")
#     
#     # Información adicional
#     observaciones = models.TextField(blank=True, verbose_name="Observaciones")
#     
#     class Meta:
#         verbose_name = "Item de Venta"
#         verbose_name_plural = "Items de Ventas"
#         unique_together = ['venta', 'producto']
#     
#     def __str__(self):
#         return f"{self.producto.nombre} - {self.cantidad}"
#     
#     def save(self, *args, **kwargs):
#         """Calcula el subtotal al guardar"""
#         self.subtotal = (self.precio_unitario - self.descuento_unitario) * self.cantidad
#         super().save(*args, **kwargs)
#         self.venta.calcular_totales()
#     
#     def actualizar_stock(self):
#         """Actualiza el stock del producto al vender"""
#         if self.producto.control_stock:
#             # Buscar stock en la sucursal de la venta
#             try:
#                 stock = self.producto.stocks.get(sucursal=self.venta.sucursal)
#                 stock.cantidad_disponible -= self.cantidad
#                 if stock.cantidad_disponible < 0:
#                     stock.cantidad_disponible = Decimal('0.00')
#                 stock.save()
#             except:
#                 pass  # Si no hay stock configurado, no se actualiza


class Devolucion(models.Model):
    """Modelo para gestionar devoluciones de productos"""
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
        ('procesada', 'Procesada'),
    ]
    
    # Información básica
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='devoluciones')
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    
    # Información de la devolución
    numero_devolucion = models.CharField(max_length=20, unique=True, verbose_name="Número de Devolución")
    fecha_devolucion = models.DateTimeField(default=timezone.now, verbose_name="Fecha de Devolución")
    motivo = models.TextField(verbose_name="Motivo de la Devolución")
    
    # Estado
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    
    # Totales
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    iva = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Información adicional
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    
    # Auditoría
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    aprobado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='devoluciones_aprobadas')
    fecha_aprobacion = models.DateTimeField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Devolución"
        verbose_name_plural = "Devoluciones"
        ordering = ['-fecha_devolucion', '-numero_devolucion']
    
    def __str__(self):
        return f"D-{self.numero_devolucion} - {self.venta.numero_venta}"
    
    def calcular_totales(self):
        """Calcula los totales de la devolución"""
        subtotal = sum(item.subtotal for item in self.items.all())
        iva = subtotal * Decimal('0.19')  # 19% IVA
        
        self.subtotal = subtotal
        self.iva = iva
        self.total = subtotal + iva
        self.save()
    
    def get_estado_display_color(self):
        """Retorna el color CSS para el estado"""
        colores = {
            'pendiente': 'warning',
            'aprobada': 'info',
            'rechazada': 'danger',
            'procesada': 'success',
        }
        return colores.get(self.estado, 'secondary')


# class ItemDevolucion(models.Model):
#     """Items individuales de una devolución (temporalmente deshabilitado)"""
#     
#     devolucion = models.ForeignKey(Devolucion, on_delete=models.CASCADE, related_name='items')
#     item_venta = models.ForeignKey(ItemVenta, on_delete=models.CASCADE)
#     
#     cantidad_devuelta = models.DecimalField(
#         max_digits=10, 
#         decimal_places=2, 
#         validators=[MinValueValidator(Decimal('0.01'))],
#         verbose_name="Cantidad Devuelta"
#     )
#     
#     precio_unitario = models.DecimalField(
#         max_digits=15, 
#         decimal_places=2, 
#         verbose_name="Precio Unitario"
#     )
#     
#     subtotal = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Subtotal")
#     
#     # Información adicional
#     motivo = models.TextField(blank=True, verbose_name="Motivo Específico")
#     
#     class Meta:
#         verbose_name = "Item de Devolución"
#         verbose_name_plural = "Items de Devoluciones"
#         unique_together = ['devolucion', 'item_venta']
#     
#     def __str__(self):
#         return f"{self.item_venta.producto.nombre} - {self.cantidad_devuelta}"
#     
#     def save(self, *args, **kwargs):
#         """Calcula el subtotal al guardar"""
#         self.subtotal = self.precio_unitario * self.cantidad_devuelta
#         super().save(*args, **kwargs)
#         self.devolucion.calcular_totales()
#     
#     def actualizar_stock(self):
#         """Actualiza el stock del producto al devolver"""
#         if self.item_venta.producto.control_stock:
#             try:
#                 stock = self.item_venta.producto.stocks.get(sucursal=self.devolucion.venta.sucursal)
#                 stock.cantidad_disponible += self.cantidad_devuelta
#                 stock.save()
#             except:
#                 pass
