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
    sucursal = models.ForeignKey(
        'empresas.Sucursal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Sucursal",
        related_name='ventas',
        help_text="Sucursal donde se realizó la venta"
    )
    numero_venta = models.CharField(max_length=20, verbose_name="Número de Venta")
    fecha = models.DateField(default=timezone.now, verbose_name="Fecha")
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cliente")
    vendedor = models.ForeignKey('Vendedor', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Vendedor")
    forma_pago = models.ForeignKey('FormaPago', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Forma de Pago")
    estacion_trabajo = models.ForeignKey('EstacionTrabajo', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Estación de Trabajo")
    
    # Campos para sistema de despacho (guías)
    vehiculo = models.ForeignKey('pedidos.Vehiculo', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Vehículo")
    chofer = models.ForeignKey('pedidos.Chofer', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Chofer")
    
    tipo_documento = models.CharField(max_length=20, choices=TIPO_DOCUMENTO_CHOICES, default='boleta', verbose_name="Tipo de Documento")

    # Tipo de documento planeado para cuando se procese (útil para tickets)
    tipo_documento_planeado = models.CharField(max_length=20, choices=TIPO_DOCUMENTO_CHOICES, null=True, blank=True, verbose_name="Tipo de Documento Planeado")
    
    # Tipo de despacho (solo para guías) - Motivo de Traslado según SII
    TIPO_DESPACHO_CHOICES = [
        ('1', 'Venta'),
        ('2', 'Venta por efectuar (anticipada)'),
        ('3', 'Consignación'),
        ('4', 'Devolución'),
        ('5', 'Traslado interno'),
        ('6', 'Transformación de productos'),
        ('7', 'Entrega gratuita'),
        ('8', 'Otros'),
    ]
    tipo_despacho = models.CharField(max_length=2, choices=TIPO_DESPACHO_CHOICES, null=True, blank=True, verbose_name="Tipo de Despacho")

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
    
    # Información de pago
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Monto Pagado")
    saldo_pendiente = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Saldo Pendiente")

    # Auditoría
    usuario_creacion = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ventas_creadas', verbose_name="Usuario Creación")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-fecha_creacion']
        unique_together = ['empresa', 'tipo_documento', 'numero_venta']
    
    @property
    def dte_asociado(self):
        from caja.models import VentaProcesada
        try:
            venta_procesada = VentaProcesada.objects.get(venta_final=self)
            return venta_procesada.dte_generado
        except VentaProcesada.DoesNotExist:
            return None

    def __str__(self):
        return f"Venta {self.numero_venta} - {self.fecha}"

    def save(self, *args, **kwargs):
        """Calcula automáticamente el saldo pendiente antes de guardar"""
        # Si es una venta confirmada, calcular saldo pendiente
        if self.estado == 'confirmada' and self.forma_pago:
            if self.forma_pago.es_cuenta_corriente:
                self.saldo_pendiente = self.total - self.monto_pagado
            else:
                # Si no es cuenta corriente, el monto pagado debe ser igual al total
                self.monto_pagado = self.total
                self.saldo_pendiente = Decimal('0.00')

        super().save(*args, **kwargs)
    
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
    
    # Modo de operación del POS
    modo_pos = models.CharField(
        max_length=20,
        choices=[
            ('normal', 'Normal - Cliente al final'),
            ('con_cliente', 'Con Cliente - Cliente al inicio')
        ],
        default='normal',
        verbose_name="Modo de Operación POS",
        help_text="Normal: Cliente opcional al final. Con Cliente: Selección obligatoria al inicio para aplicar precios especiales."
    )
    
    # Cierre directo (Cerrar y emitir DTE automáticamente)
    cierre_directo = models.BooleanField(
        default=False,
        verbose_name="Cierre directo (Cerrar y Emitir DTE)"
    )
    flujo_cierre_directo = models.CharField(
        max_length=20,
        choices=[
            ('rut_inicio', 'RUT al inicio'),
            ('rut_final', 'RUT al final'),
        ],
        default='rut_final',
        verbose_name="Flujo para cierre directo"
    )
    enviar_sii_directo = models.BooleanField(
        default=True,
        verbose_name="Enviar al SII automáticamente"
    )
    
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


class PrecioClienteArticulo(models.Model):
    """Modelo para gestionar precios especiales por cliente y artículo"""
    
    # Relaciones
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='precios_especiales', verbose_name="Cliente")
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, related_name='precios_clientes', verbose_name="Artículo")
    
    # Precio especial
    precio_especial = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Precio Especial",
        help_text="Precio personalizado para este cliente. Si no existe, se usa el precio general del artículo."
    )
    
    # Descuento adicional (opcional)
    descuento_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        blank=True,
        null=True,
        verbose_name="Descuento Adicional (%)",
        help_text="Descuento adicional sobre el precio especial (opcional)"
    )
    
    # Control
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_inicio = models.DateField(blank=True, null=True, verbose_name="Fecha Inicio Vigencia")
    fecha_fin = models.DateField(blank=True, null=True, verbose_name="Fecha Fin Vigencia")
    
    # Auditoría
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='precios_creados', verbose_name="Creado Por")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Precio Especial Cliente"
        verbose_name_plural = "Precios Especiales Clientes"
        ordering = ['cliente__nombre', 'articulo__nombre']
        unique_together = ['empresa', 'cliente', 'articulo']
        indexes = [
            models.Index(fields=['cliente', 'articulo', 'activo']),
            models.Index(fields=['empresa', 'activo']),
        ]
    
    def __str__(self):
        return f"{self.cliente.nombre} - {self.articulo.nombre}: ${self.precio_especial}"
    
    def get_precio_final(self):
        """Calcula el precio final aplicando descuento si existe"""
        if self.descuento_porcentaje and self.descuento_porcentaje > 0:
            descuento = self.precio_especial * (self.descuento_porcentaje / Decimal('100'))
            return self.precio_especial - descuento
        return self.precio_especial
    
    def get_precio_con_iva(self):
        """
        Retorna el precio especial (que ya incluye IVA e impuestos).
        El precio_especial se guarda CON todos los impuestos incluidos.
        """
        return self.get_precio_final()
    
    def get_precio_neto(self):
        """
        Calcula el precio NETO (sin IVA ni impuestos) desde el precio especial.
        El precio_especial incluye todos los impuestos, aquí los descontamos.
        """
        precio_con_impuestos = self.get_precio_final()
        
        # Obtener la categoría del artículo
        categoria = getattr(self.articulo, 'categoria', None)
        
        if not categoria:
            # Si no tiene categoría, descontar IVA estándar (19%)
            return precio_con_impuestos / Decimal('1.19')
        
        # Obtener porcentajes de impuestos
        iva_porcentaje = Decimal('0.00') if categoria.exenta_iva else Decimal('0.19')
        
        impuesto_especifico_porcentaje = Decimal('0.00')
        if categoria.impuesto_especifico:
            impuesto_especifico_porcentaje = categoria.impuesto_especifico.get_porcentaje_decimal()
        
        # Calcular precio neto
        # Precio con impuestos = Precio Neto × (1 + IVA + Imp.Esp)
        # Precio Neto = Precio con impuestos / (1 + IVA + Imp.Esp)
        factor_total = Decimal('1.00') + iva_porcentaje + impuesto_especifico_porcentaje
        precio_neto = precio_con_impuestos / factor_total
        
        return precio_neto
    
    def esta_vigente(self):
        """Verifica si el precio especial está vigente según las fechas"""
        if not self.activo:
            return False
        
        hoy = timezone.now().date()
        
        if self.fecha_inicio and hoy < self.fecha_inicio:
            return False
        
        if self.fecha_fin and hoy > self.fecha_fin:
            return False
        
        return True


class VentaReferencia(models.Model):
    """Modelo para referencias de documentos (Orden de Compra, HES, etc.)"""
    
    TIPO_REFERENCIA_CHOICES = [
        ('52', 'Guía de Despacho'),
        ('801', 'Orden de Compra'),
        ('802', 'Nota de Pedido'),
        ('803', 'Contrato'),
        ('804', 'Resolución'),
        ('805', 'Proceso ChileCompra'),
        ('806', 'Ficha ChileCompra'),
        ('807', 'DUS'),
        ('808', 'B/L (Conocimiento de embarque)'),
        ('809', 'AWB (Air Will Bill)'),
        ('810', 'MIC/DTA'),
        ('811', 'Carta de Porte'),
        ('812', 'Resolución del SNA donde califica Servicios de Exportación'),
        ('813', 'Pasaporte'),
        ('814', 'Certificado de Depósito Bolsa Prod. Chile'),
        ('815', 'Vale de Prenda Bolsa Prod. Chile'),
        ('HES', 'Hoja de Entrada de Servicios'),
        ('HEM', 'Hoja de Entrada de Materiales'),
    ]
    
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='referencias', verbose_name="Venta")
    tipo_referencia = models.CharField(max_length=10, choices=TIPO_REFERENCIA_CHOICES, verbose_name="Tipo de Referencia")
    folio_referencia = models.CharField(max_length=50, verbose_name="Folio/Número de Referencia")
    fecha_referencia = models.DateField(verbose_name="Fecha de Referencia")
    razon_referencia = models.TextField(blank=True, verbose_name="Razón de la Referencia")
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Referencia de Venta"
        verbose_name_plural = "Referencias de Ventas"
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.get_tipo_referencia_display()} - {self.folio_referencia}"


class NotaCredito(models.Model):
    """Modelo para Notas de Crédito"""
    
    TIPO_NC_CHOICES = [
        ('ANULA', 'Anula Documento Completo'),
        ('CORRIGE_MONTO', 'Corrige Monto'),
        ('CORRIGE_TEXTO', 'Corrige Texto'),
    ]
    
    TIPO_DOC_AFECTADO_CHOICES = [
        ('33', 'Factura Electrónica'),
        ('39', 'Boleta Electrónica'),
        ('52', 'Guía de Despacho Electrónica'),
        ('46', 'Factura de Compra Electrónica'),
    ]
    
    # Datos principales
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, verbose_name="Sucursal", null=True, blank=True)
    numero = models.CharField(max_length=20, verbose_name="N° Nota de Crédito", null=True, blank=True) # Se asigna al emitir DTE
    fecha = models.DateField(default=timezone.now, verbose_name="Fecha Emisión")
    
    # Cliente
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, verbose_name="Cliente")
    
    # Vendedor y bodega
    vendedor = models.ForeignKey(Vendedor, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Vendedor")
    bodega = models.ForeignKey('bodegas.Bodega', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Bodega")
    
    # Tipo de Nota de Crédito
    tipo_nc = models.CharField(
        max_length=20,
        choices=TIPO_NC_CHOICES,
        default='ANULA',
        verbose_name="Tipo de Nota de Crédito"
    )
    
    # Documento que afecta
    tipo_doc_afectado = models.CharField(
        max_length=2,
        choices=TIPO_DOC_AFECTADO_CHOICES,
        verbose_name="Tipo Documento Afectado"
    )
    numero_doc_afectado = models.CharField(max_length=20, verbose_name="N° Documento Afectado")
    fecha_doc_afectado = models.DateField(verbose_name="Fecha Doc. Afectado")
    
    # Motivo
    motivo = models.TextField(verbose_name="Motivo de la Nota de Crédito")
    
    # Montos
    subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Subtotal"
    )
    descuento = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Descuento"
    )
    iva = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="IVA"
    )
    total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Total"
    )
    
    # Estado
    estado = models.CharField(
        max_length=20,
        choices=[
            ('borrador', 'Borrador'),
            ('emitida', 'Emitida'),
            ('enviada_sii', 'Enviada al SII'),
            ('aceptada_sii', 'Aceptada por SII'),
            ('anulada', 'Anulada'),
        ],
        default='borrador',
        verbose_name="Estado"
    )
    
    # DTE asociado (si es electrónica)
    dte = models.ForeignKey(
        'facturacion_electronica.DocumentoTributarioElectronico',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="DTE Generado",
        related_name='notas_credito'
    )
    
    # Auditoría
    usuario_creacion = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='notas_credito_creadas',
        verbose_name="Usuario Creación"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha Creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Fecha Modificación")
    
    class Meta:
        verbose_name = "Nota de Crédito"
        verbose_name_plural = "Notas de Crédito"
        ordering = ['-fecha', '-numero']
    
    def __str__(self):
        return f"NC {self.numero} - {self.cliente.nombre}"
    
    def calcular_totales(self):
        """Calcula los totales de la nota de crédito"""
        items = self.items.all()
        subtotal_calculado = sum(item.total for item in items)
        self.subtotal = subtotal_calculado
        self.iva = self.subtotal * Decimal('0.19')
        self.total = self.subtotal + self.iva
        self.save(update_fields=['subtotal', 'iva', 'total'])


class NotaCreditoDetalle(models.Model):
    """Detalle de items de una Nota de Crédito"""
    
    nota_credito = models.ForeignKey(
        NotaCredito,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Nota de Crédito"
    )
    
    # Datos del artículo
    articulo = models.ForeignKey(
        Articulo,
        on_delete=models.PROTECT,
        verbose_name="Artículo"
    )
    codigo = models.CharField(max_length=50, verbose_name="Código")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción")
    
    # Cantidades y precios
    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Cantidad"
    )
    precio_unitario = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Precio Unitario"
    )
    descuento = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        verbose_name="% Descuento"
    )
    total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Total"
    )
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Detalle Nota de Crédito"
        verbose_name_plural = "Detalles Notas de Crédito"
        ordering = ['id']
    
    def __str__(self):
        return f"{self.codigo} - {self.cantidad} x {self.precio_unitario}"
    
    def save(self, *args, **kwargs):
        # Calcular total
        subtotal = self.cantidad * self.precio_unitario
        descuento_monto = subtotal * (self.descuento / Decimal('100'))
        self.total = subtotal - descuento_monto
        super().save(*args, **kwargs)
