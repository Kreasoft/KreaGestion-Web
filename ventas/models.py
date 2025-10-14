from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
from empresas.models import Empresa, Sucursal
from clientes.models import Cliente
from articulos.models import Articulo

# Constantes para tipos de documentos
TIPO_DOCUMENTO_CHOICES = [
    ('factura', 'Factura'),
    ('boleta', 'Boleta'),
    ('guia', 'Guía de Despacho'),
    ('cotizacion', 'Cotización'),
    ('vale', 'Vale Facturable'),
]


class Vendedor(models.Model):
    """Modelo para gestionar vendedores"""
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    codigo = models.CharField(max_length=20, verbose_name="Código")
    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    porcentaje_comision = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        verbose_name="% Comisión"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Vendedor"
        verbose_name_plural = "Vendedores"
        ordering = ['nombre']
        unique_together = ['empresa', 'codigo']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class FormaPago(models.Model):
    """Modelo para gestionar formas de pago"""
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    codigo = models.CharField(max_length=20, verbose_name="Código")
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    es_cuenta_corriente = models.BooleanField(
        default=False,
        verbose_name="Es Cuenta Corriente",
        help_text="Si está marcado, la factura pasa a cuenta corriente del cliente"
    )
    requiere_cheque = models.BooleanField(
        default=False,
        verbose_name="Requiere Cheque",
        help_text="Si está marcado, se debe registrar información del cheque al usar esta forma de pago"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Forma de Pago"
        verbose_name_plural = "Formas de Pago"
        ordering = ['nombre']
        unique_together = ['empresa', 'codigo']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Venta(models.Model):
    """Modelo para gestionar ventas del POS"""
    
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('confirmada', 'Confirmada'),
        ('anulada', 'Anulada'),
    ]
    
    ESTADO_COTIZACION_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('enviada', 'Enviada'),
        ('aceptada', 'Aceptada'),
        ('rechazada', 'Rechazada'),
        ('vencida', 'Vencida'),
        ('convertida', 'Convertida en Venta'),
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    numero_venta = models.CharField(max_length=20, verbose_name="Número de Venta")
    fecha = models.DateField(default=timezone.now, verbose_name="Fecha")
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cliente")
    vendedor = models.ForeignKey('Vendedor', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Vendedor")
    forma_pago = models.ForeignKey('FormaPago', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Forma de Pago")
    estacion_trabajo = models.ForeignKey('EstacionTrabajo', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Estación de Trabajo")
    tipo_documento = models.CharField(max_length=20, choices=TIPO_DOCUMENTO_CHOICES, default='boleta', verbose_name="Tipo de Documento")

    # Tipo de documento planeado para cuando se procese (útil para tickets)
    tipo_documento_planeado = models.CharField(max_length=20, choices=TIPO_DOCUMENTO_CHOICES, null=True, blank=True, verbose_name="Tipo de Documento Planeado")

    # Totales
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Subtotal")
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Descuento")
    neto = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Neto")
    iva = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="IVA")
    impuesto_especifico = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Impuesto Específico")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Total")
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador', verbose_name="Estado")
    estado_cotizacion = models.CharField(max_length=20, choices=ESTADO_COTIZACION_CHOICES, default='pendiente', verbose_name="Estado Cotización", blank=True, null=True)
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    
    # Auditoría
    usuario_creacion = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ventas_creadas', verbose_name="Usuario Creación")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-fecha_creacion']
        unique_together = ['empresa', 'numero_venta']
    
    def __str__(self):
        return f"Venta {self.numero_venta} - {self.fecha}"
    
    def calcular_totales(self):
        """
        Calcula todos los totales de la venta.
        IMPORTANTE: Los precios en precio_total YA INCLUYEN IVA e impuestos.
        Este método extrae el IVA del subtotal, no lo agrega.
        """
        detalles = self.ventadetalle_set.all()
        
        # Subtotal: suma de todos los precios totales (YA incluye IVA)
        subtotal = sum(detalle.precio_total for detalle in detalles)
        
        # Impuesto específico: suma de impuestos específicos de cada detalle
        impuesto_especifico = sum(detalle.impuesto_especifico for detalle in detalles)
        
        # El total es el subtotal (que ya incluye IVA) más impuestos específicos
        total = subtotal + impuesto_especifico - self.descuento
        
        # Extraer el IVA del subtotal (subtotal incluye IVA)
        # subtotal = neto + iva
        # subtotal = neto * 1.19
        # neto = subtotal / 1.19
        neto = (subtotal - self.descuento) / Decimal('1.19')
        iva = (subtotal - self.descuento) - neto
        
        self.subtotal = subtotal
        self.neto = neto
        self.iva = iva
        self.impuesto_especifico = impuesto_especifico
        self.total = total
        self.save()
    
    def es_cotizacion_vencida(self):
        """Verifica si una cotización está vencida (30 días)"""
        if self.tipo_documento != 'cotizacion':
            return False
        
        from datetime import timedelta
        fecha_vencimiento = self.fecha + timedelta(days=30)
        return timezone.now().date() > fecha_vencimiento
    
    def actualizar_estado_cotizacion(self):
        """Actualiza el estado de la cotización según su fecha"""
        if self.tipo_documento == 'cotizacion' and self.estado_cotizacion in ['pendiente', 'enviada']:
            if self.es_cotizacion_vencida():
                self.estado_cotizacion = 'vencida'
                self.save()


class VentaDetalle(models.Model):
    """Modelo para los detalles de una venta"""
    
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, verbose_name="Venta")
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, verbose_name="Artículo")
    cantidad = models.DecimalField(max_digits=10, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))], verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], verbose_name="Precio Unitario")
    precio_total = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], verbose_name="Precio Total")
    impuesto_especifico = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Impuesto Específico")
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Detalle de Venta"
        verbose_name_plural = "Detalles de Venta"
        ordering = ['fecha_creacion']
    
    def __str__(self):
        return f"{self.articulo.codigo} - {self.cantidad} x {self.precio_unitario}"
    
    def save(self, *args, **kwargs):
        # Calcular precio total
        self.precio_total = self.cantidad * self.precio_unitario
        
        # Calcular impuesto específico si el artículo lo tiene
        if self.articulo.impuesto_especifico:
            # Convertir a Decimal para evitar errores de tipo
            impuesto_porcentaje = Decimal(str(self.articulo.impuesto_especifico))
            self.impuesto_especifico = self.precio_total * (impuesto_porcentaje / 100)
        
        super().save(*args, **kwargs)
        
        # Recalcular totales de la venta
        if self.venta:
            self.venta.calcular_totales()


class EstacionTrabajo(models.Model):
    """Modelo para gestionar estaciones de trabajo del POS"""
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    numero = models.CharField(max_length=10, verbose_name="Número de Estación")
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Estación")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    
    # Correlativo único de la estación
    correlativo_ticket = models.PositiveIntegerField(default=1, verbose_name="Correlativo de Ticket")
    
    # Tipos de documentos permitidos
    puede_facturar = models.BooleanField(default=False, verbose_name="Puede Emitir Facturas")
    puede_boletar = models.BooleanField(default=True, verbose_name="Puede Emitir Boletas")
    puede_guia = models.BooleanField(default=False, verbose_name="Puede Emitir Guías")
    puede_cotizar = models.BooleanField(default=True, verbose_name="Puede Emitir Cotizaciones")
    puede_vale = models.BooleanField(default=False, verbose_name="Puede Emitir Vales")
    
    # Configuración de límites
    max_items_factura = models.PositiveIntegerField(default=20, verbose_name="Máx. Items Factura")
    max_items_boleta = models.PositiveIntegerField(default=35, verbose_name="Máx. Items Boleta")
    max_items_guia = models.PositiveIntegerField(default=50, verbose_name="Máx. Items Guía")
    max_items_cotizacion = models.PositiveIntegerField(default=50, verbose_name="Máx. Items Cotización")
    max_items_vale = models.PositiveIntegerField(default=30, verbose_name="Máx. Items Vale")
    
    activo = models.BooleanField(default=True, verbose_name="Activo")
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Estación de Trabajo"
        verbose_name_plural = "Estaciones de Trabajo"
        ordering = ['numero']
        unique_together = ['empresa', 'numero']
    
    def __str__(self):
        return f"Estación {self.numero} - {self.nombre}"
    
    def get_tipos_documentos_permitidos(self):
        """Retorna los tipos de documentos que puede emitir esta estación"""
        tipos = []
        if self.puede_facturar:
            tipos.append('factura')
        if self.puede_boletar:
            tipos.append('boleta')
        if self.puede_guia:
            tipos.append('guia')
        if self.puede_cotizar:
            tipos.append('cotizacion')
        if self.puede_vale:
            tipos.append('vale')
        return tipos
    
    def get_max_items_por_tipo(self, tipo_documento):
        """Retorna el máximo de items permitido para un tipo de documento"""
        max_items = {
            'factura': self.max_items_factura,
            'boleta': self.max_items_boleta,
            'guia': self.max_items_guia,
            'cotizacion': self.max_items_cotizacion,
            'vale': self.max_items_vale,
        }
        return max_items.get(tipo_documento, 20)
    
    def get_correlativo_ticket(self):
        """Retorna el correlativo actual de ticket de la estación"""
        return self.correlativo_ticket
    
    def incrementar_correlativo_ticket(self):
        """Incrementa el correlativo de ticket de la estación"""
        self.correlativo_ticket += 1
        self.save()
        return self.correlativo_ticket


class Devolucion(models.Model):
    """Modelo para gestionar devoluciones de ventas"""
    
    MOTIVO_CHOICES = [
        ('defectuoso', 'Producto Defectuoso'),
        ('equivocado', 'Producto Equivocado'),
        ('insatisfaccion', 'Insatisfacción del Cliente'),
        ('garantia', 'Garantía'),
        ('otro', 'Otro Motivo'),
    ]
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
        ('procesada', 'Procesada'),
    ]
    
    # Relaciones
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='devoluciones', verbose_name="Empresa")
    venta = models.ForeignKey('Venta', on_delete=models.CASCADE, related_name='devoluciones', verbose_name="Venta Original")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, verbose_name="Cliente")
    
    # Información de la devolución
    numero_devolucion = models.CharField(max_length=50, verbose_name="Número de Devolución")
    fecha_devolucion = models.DateTimeField(default=timezone.now, verbose_name="Fecha de Devolución")
    motivo = models.CharField(max_length=20, choices=MOTIVO_CHOICES, default='otro', verbose_name="Motivo")
    descripcion_motivo = models.TextField(blank=True, null=True, verbose_name="Descripción del Motivo")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente', verbose_name="Estado")
    
    # Montos
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Monto Total")
    
    # Usuario que procesa
    usuario_creacion = models.ForeignKey(User, on_delete=models.PROTECT, related_name='devoluciones_creadas', verbose_name="Usuario Creación")
    usuario_aprobacion = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='devoluciones_aprobadas', verbose_name="Usuario Aprobación")
    fecha_aprobacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha Aprobación")
    
    # Observaciones
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Devolución"
        verbose_name_plural = "Devoluciones"
        ordering = ['-fecha_devolucion']
        unique_together = ['empresa', 'numero_devolucion']
    
    def __str__(self):
        return f"Devolución {self.numero_devolucion} - Venta {self.venta.numero_ticket}"


class DevolucionDetalle(models.Model):
    """Modelo para el detalle de devoluciones"""
    
    # Relaciones
    devolucion = models.ForeignKey(Devolucion, on_delete=models.CASCADE, related_name='detalles', verbose_name="Devolución")
    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT, verbose_name="Artículo")
    
    # Cantidades
    cantidad_devuelta = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], verbose_name="Cantidad Devuelta")
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Unitario")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Subtotal")
    
    # Información adicional
    motivo_especifico = models.TextField(blank=True, null=True, verbose_name="Motivo Específico del Artículo")
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Detalle de Devolución"
        verbose_name_plural = "Detalles de Devoluciones"
        ordering = ['id']
    
    def __str__(self):
        return f"{self.articulo.nombre} - Cant: {self.cantidad_devuelta}"
    
    def save(self, *args, **kwargs):
        """Calcular subtotal antes de guardar"""
        self.subtotal = self.cantidad_devuelta * self.precio_unitario
        super().save(*args, **kwargs)
