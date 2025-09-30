from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from empresas.models import Empresa
from proveedores.models import Proveedor
from articulos.models import Articulo
from bodegas.models import Bodega


class DocumentoCompra(models.Model):
    """Modelo para gestionar documentos de compra (facturas, guías, etc.)"""
    
    TIPO_DOCUMENTO_CHOICES = [
        ('factura', 'Factura'),
        ('guia_despacho', 'Guía de Despacho'),
        ('nota_credito', 'Nota de Crédito'),
        ('nota_debito', 'Nota de Débito'),
        ('boleta', 'Boleta'),
        ('factura_exenta', 'Factura Exenta'),
        ('recibo', 'Recibo'),
    ]
    
    ESTADO_DOCUMENTO_CHOICES = [
        ('borrador', 'Borrador'),
        ('pendiente', 'Pendiente'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
        ('anulado', 'Anulado'),
    ]
    
    ESTADO_PAGO_CHOICES = [
        ('pagada', 'Pagada'),
        ('credito', 'Crédito'),
        ('parcial', 'Pago Parcial'),
        ('vencida', 'Vencida'),
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, verbose_name="Proveedor")
    bodega = models.ForeignKey(Bodega, on_delete=models.CASCADE, verbose_name="Bodega")
    
    # Información del documento
    tipo_documento = models.CharField(max_length=20, choices=TIPO_DOCUMENTO_CHOICES, verbose_name="Tipo de Documento")
    numero_documento = models.CharField(max_length=50, verbose_name="Número de Documento")
    fecha_emision = models.DateField(verbose_name="Fecha de Emisión")
    fecha_vencimiento = models.DateField(blank=True, null=True, verbose_name="Fecha de Vencimiento")
    
    # Estados
    estado_documento = models.CharField(max_length=20, choices=ESTADO_DOCUMENTO_CHOICES, default='borrador', verbose_name="Estado del Documento")
    estado_pago = models.CharField(max_length=20, choices=ESTADO_PAGO_CHOICES, default='credito', verbose_name="Estado de Pago")
    
    # Totales
    subtotal = models.IntegerField(default=0, verbose_name="Subtotal")
    descuentos_totales = models.IntegerField(default=0, verbose_name="Descuentos Totales")
    impuestos_totales = models.IntegerField(default=0, verbose_name="Impuestos Totales")
    total_documento = models.IntegerField(default=0, verbose_name="Total Documento")
    
    # Información adicional
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    archivo_documento = models.FileField(upload_to='documentos_compra/', blank=True, null=True, verbose_name="Archivo del Documento")
    
    # Auditoría
    creado_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documentos_compra_creados', verbose_name="Creado por")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Modificación")
    
    # Campos para cuentas corrientes
    en_cuenta_corriente = models.BooleanField(default=False, verbose_name="En Cuenta Corriente")
    fecha_registro_cc = models.DateTimeField(blank=True, null=True, verbose_name="Fecha Registro CC")
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Monto Pagado")
    saldo_pendiente = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Saldo Pendiente")
    
    class Meta:
        verbose_name = "Documento de Compra"
        verbose_name_plural = "Documentos de Compra"
        unique_together = ['empresa', 'numero_documento', 'tipo_documento']
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.get_tipo_documento_display()} {self.numero_documento} - {self.proveedor.nombre}"
    
    def calcular_totales(self):
        """Calcula los totales del documento basado en sus items"""
        items = self.items.all()
        
        self.subtotal = sum(item.get_subtotal() for item in items)
        self.descuentos_totales = sum(item.get_descuento_monto() for item in items)
        self.impuestos_totales = sum(item.get_impuesto_monto() for item in items)
        self.total_documento = self.subtotal - self.descuentos_totales + self.impuestos_totales
        
        # Actualizar saldo pendiente
        self.saldo_pendiente = self.total_documento - self.monto_pagado
        
        # Actualizar estado de pago
        if self.monto_pagado >= self.total_documento:
            self.estado_pago = 'pagada'
        elif self.monto_pagado > 0:
            self.estado_pago = 'parcial'
        elif self.fecha_vencimiento and self.fecha_vencimiento < timezone.now().date():
            self.estado_pago = 'vencida'
        else:
            self.estado_pago = 'credito'
        
        self.save()
    
    def puede_editar(self):
        """Verifica si el documento puede ser editado"""
        return self.estado_documento in ['borrador', 'pendiente']
    
    def puede_aprobar(self):
        """Verifica si el documento puede ser aprobado"""
        return self.estado_documento == 'pendiente'
    
    def debe_ir_a_cuenta_corriente(self):
        """Verifica si el documento debe ir a cuenta corriente"""
        return self.estado_pago in ['credito', 'parcial'] and self.estado_documento == 'aprobado'
    
    def registrar_en_cuenta_corriente(self):
        """Registra el documento en cuenta corriente"""
        if self.debe_ir_a_cuenta_corriente() and not self.en_cuenta_corriente:
            # Aquí se integraría con el módulo de tesorería
            # Por ahora solo marcamos el flag
            self.en_cuenta_corriente = True
            self.fecha_registro_cc = timezone.now()
            self.save()
            return True
        return False


class ItemDocumentoCompra(models.Model):
    """Items individuales de un documento de compra"""
    
    documento_compra = models.ForeignKey(DocumentoCompra, on_delete=models.CASCADE, related_name='items', verbose_name="Documento de Compra")
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, verbose_name="Artículo")
    
    # Información del item
    cantidad = models.IntegerField(default=1, validators=[MinValueValidator(1)], verbose_name="Cantidad")
    precio_unitario = models.IntegerField(validators=[MinValueValidator(0)], verbose_name="Precio Unitario")
    
    # Descuentos e impuestos
    descuento_porcentaje = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="Descuento (%)")
    impuesto_porcentaje = models.IntegerField(default=19, validators=[MinValueValidator(0)], verbose_name="Impuesto (%)")
    
    # Totales del item
    subtotal = models.IntegerField(default=0, verbose_name="Subtotal")
    descuento_monto = models.IntegerField(default=0, verbose_name="Descuento Monto")
    impuesto_monto = models.IntegerField(default=0, verbose_name="Impuesto Monto")
    total_item = models.IntegerField(default=0, verbose_name="Total Item")
    
    class Meta:
        verbose_name = "Item de Documento de Compra"
        verbose_name_plural = "Items de Documentos de Compra"
        ordering = ['id']
    
    def __str__(self):
        return f"{self.articulo.nombre} - {self.cantidad}"
    
    def save(self, *args, **kwargs):
        """Calcula automáticamente los totales al guardar"""
        self.subtotal = self.cantidad * self.precio_unitario
        self.descuento_monto = round(self.subtotal * (self.descuento_porcentaje / 100))
        self.impuesto_monto = round((self.subtotal - self.descuento_monto) * (self.impuesto_porcentaje / 100))
        self.total_item = self.subtotal - self.descuento_monto + self.impuesto_monto
        super().save(*args, **kwargs)
    
    def get_subtotal(self):
        """Retorna el subtotal del item"""
        return self.cantidad * self.precio_unitario
    
    def get_descuento_monto(self):
        """Retorna el monto del descuento"""
        return round(self.subtotal * (self.descuento_porcentaje / 100))
    
    def get_impuesto_monto(self):
        """Retorna el monto del impuesto"""
        return round((self.subtotal - self.get_descuento_monto()) * (self.impuesto_porcentaje / 100))
    
    def get_total(self):
        """Retorna el total del item"""
        return self.get_subtotal() - self.get_descuento_monto() + self.get_impuesto_monto()


class HistorialPagoDocumento(models.Model):
    """Historial de pagos de un documento"""
    
    documento_compra = models.ForeignKey(DocumentoCompra, on_delete=models.CASCADE, related_name='historial_pagos', verbose_name="Documento de Compra")
    fecha_pago = models.DateTimeField(default=timezone.now, verbose_name="Fecha de Pago")
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name="Monto Pagado")
    metodo_pago = models.CharField(max_length=50, verbose_name="Método de Pago")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    registrado_por = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Registrado por")
    
    class Meta:
        verbose_name = "Historial de Pago"
        verbose_name_plural = "Historial de Pagos"
        ordering = ['-fecha_pago']
    
    def __str__(self):
        return f"Pago {self.monto_pagado} - {self.fecha_pago.strftime('%d/%m/%Y')}"