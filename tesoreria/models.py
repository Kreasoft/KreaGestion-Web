from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from empresas.models import Empresa
from proveedores.models import Proveedor
from clientes.models import Cliente
from documentos.models import DocumentoCompra


class CuentaCorrienteProveedor(models.Model):
    """Modelo para gestionar la cuenta corriente de proveedores"""
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa", related_name="cuentas_corrientes_proveedores")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, verbose_name="Proveedor", related_name="cuentas_corrientes")
    
    # Saldos
    saldo_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Saldo Total")
    saldo_pendiente = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Saldo Pendiente")
    saldo_vencido = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Saldo Vencido")
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Modificación")
    
    class Meta:
        verbose_name = "Cuenta Corriente Proveedor"
        verbose_name_plural = "Cuentas Corrientes Proveedores"
        unique_together = ['empresa', 'proveedor']
        ordering = ['proveedor__nombre']
    
    def __str__(self):
        return f"CC {self.proveedor.nombre} - {self.empresa.nombre}"
    
    def calcular_saldos(self):
        """Calcula los saldos basado en los documentos"""
        documentos = self.documentos.all()
        
        self.saldo_total = sum(doc.saldo_pendiente for doc in documentos)
        self.saldo_pendiente = sum(doc.saldo_pendiente for doc in documentos if doc.estado_pago == 'credito')
        self.saldo_vencido = sum(doc.saldo_pendiente for doc in documentos if doc.estado_pago == 'vencida')
        
        self.save()


class MovimientoCuentaCorriente(models.Model):
    """Modelo para registrar movimientos en la cuenta corriente"""
    
    TIPO_MOVIMIENTO_CHOICES = [
        ('debe', 'Debe'),
        ('haber', 'Haber'),
    ]
    
    ESTADO_MOVIMIENTO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('confirmado', 'Confirmado'),
        ('anulado', 'Anulado'),
    ]
    
    cuenta_corriente = models.ForeignKey(CuentaCorrienteProveedor, on_delete=models.CASCADE, 
                                       related_name='movimientos', verbose_name="Cuenta Corriente")
    documento_compra = models.ForeignKey(DocumentoCompra, on_delete=models.CASCADE, 
                                       blank=True, null=True, verbose_name="Documento de Compra", related_name="movimientos_cuenta_corriente")
    
    # Información del movimiento
    tipo_movimiento = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO_CHOICES, verbose_name="Tipo de Movimiento")
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name="Monto")
    saldo_anterior = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Saldo Anterior")
    saldo_nuevo = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Saldo Nuevo")
    
    # Estado y observaciones
    estado = models.CharField(max_length=20, choices=ESTADO_MOVIMIENTO_CHOICES, default='confirmado', verbose_name="Estado")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    
    # Auditoría
    fecha_movimiento = models.DateTimeField(default=timezone.now, verbose_name="Fecha del Movimiento")
    registrado_por = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Registrado por")
    
    class Meta:
        verbose_name = "Movimiento de Cuenta Corriente"
        verbose_name_plural = "Movimientos de Cuenta Corriente"
        ordering = ['-fecha_movimiento']
    
    def __str__(self):
        return f"{self.get_tipo_movimiento_display()} - {self.monto} - {self.fecha_movimiento.strftime('%d/%m/%Y')}"


class CuentaCorrienteCliente(models.Model):
    """Modelo para gestionar la cuenta corriente de clientes"""

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa", related_name="cuentas_corrientes_clientes")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente", related_name="cuentas_corrientes")

    # Saldos
    saldo_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Saldo Total")
    saldo_pendiente = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Saldo Pendiente")
    saldo_vencido = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Saldo Vencido")

    # Límites y condiciones
    limite_credito = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Límite de Crédito")
    dias_credito = models.IntegerField(default=30, verbose_name="Días de Crédito")

    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Modificación")

    class Meta:
        verbose_name = "Cuenta Corriente Cliente"
        verbose_name_plural = "Cuentas Corrientes Clientes"
        unique_together = ['empresa', 'cliente']
        ordering = ['cliente__nombre']

    def __str__(self):
        return f"CC {self.cliente.nombre} - {self.empresa.nombre}"

    def calcular_saldos(self):
        """Calcula los saldos basado en las ventas a crédito"""
        from ventas.models import Venta
        ventas_credito = Venta.objects.filter(
            empresa=self.empresa,
            cliente=self.cliente,
            estado='confirmada'
        ).exclude(total=0)

        self.saldo_total = sum(venta.total for venta in ventas_credito)
        self.saldo_pendiente = sum(venta.total for venta in ventas_credito if venta.estado_pago == 'pendiente')
        self.saldo_vencido = sum(venta.total for venta in ventas_credito if venta.estado_pago == 'vencida')

        self.save()

    def tiene_credito_disponible(self, monto_solicitado):
        """Verifica si el cliente tiene crédito disponible"""
        credito_utilizado = self.saldo_pendiente + self.saldo_vencido
        credito_disponible = self.limite_credito - credito_utilizado
        return credito_disponible >= monto_solicitado


class MovimientoCuentaCorrienteCliente(models.Model):
    """Modelo para registrar movimientos en la cuenta corriente de clientes"""

    TIPO_MOVIMIENTO_CHOICES = [
        ('debe', 'Debe'),  # Cliente debe pagar (venta a crédito)
        ('haber', 'Haber'),  # Cliente pagó (pago recibido)
    ]

    ESTADO_MOVIMIENTO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('confirmado', 'Confirmado'),
        ('anulado', 'Anulado'),
    ]

    cuenta_corriente = models.ForeignKey(CuentaCorrienteCliente, on_delete=models.CASCADE,
                                       related_name='movimientos', verbose_name="Cuenta Corriente")
    venta = models.ForeignKey('ventas.Venta', on_delete=models.CASCADE,
                             blank=True, null=True, verbose_name="Venta", related_name="movimientos_cuenta_corriente")

    # Información del movimiento
    tipo_movimiento = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO_CHOICES, verbose_name="Tipo de Movimiento")
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name="Monto")
    saldo_anterior = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Saldo Anterior")
    saldo_nuevo = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Saldo Nuevo")

    # Estado y observaciones
    estado = models.CharField(max_length=20, choices=ESTADO_MOVIMIENTO_CHOICES, default='confirmado', verbose_name="Estado")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    # Auditoría
    fecha_movimiento = models.DateTimeField(default=timezone.now, verbose_name="Fecha del Movimiento")
    registrado_por = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Registrado por")

    class Meta:
        verbose_name = "Movimiento de Cuenta Corriente de Cliente"
        verbose_name_plural = "Movimientos de Cuenta Corriente de Clientes"
        ordering = ['-fecha_movimiento']

    def __str__(self):
        return f"{self.get_tipo_movimiento_display()} - {self.monto} - {self.fecha_movimiento.strftime('%d/%m/%Y')}"


class DocumentoCliente(models.Model):
    """Modelo para gestionar documentos de clientes en cuenta corriente"""
    
    TIPO_DOCUMENTO_CHOICES = [
        ('factura', 'Factura'),
        ('boleta', 'Boleta'),
        ('nota_credito', 'Nota de Crédito'),
        ('nota_debito', 'Nota de Débito'),
    ]
    
    ESTADO_PAGO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('parcial', 'Parcial'),
        ('pagado', 'Pagado'),
        ('vencido', 'Vencido'),
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, verbose_name="Cliente", related_name="documentos_cuenta_corriente")
    
    # Información del documento
    tipo_documento = models.CharField(max_length=20, choices=TIPO_DOCUMENTO_CHOICES, verbose_name="Tipo de Documento")
    numero_documento = models.CharField(max_length=50, verbose_name="Número de Documento")
    fecha_emision = models.DateField(verbose_name="Fecha de Emisión")
    fecha_vencimiento = models.DateField(blank=True, null=True, verbose_name="Fecha de Vencimiento")
    
    # Montos
    total = models.IntegerField(default=0, verbose_name="Total")
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Monto Pagado")
    saldo_pendiente = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Saldo Pendiente")
    
    # Estado
    estado_pago = models.CharField(max_length=20, choices=ESTADO_PAGO_CHOICES, default='pendiente', verbose_name="Estado de Pago")
    
    # Información adicional
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    
    # Auditoría
    creado_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documentos_cliente_creados', verbose_name="Creado por")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Modificación")
    
    class Meta:
        verbose_name = "Documento de Cliente"
        verbose_name_plural = "Documentos de Clientes"
        unique_together = ['empresa', 'numero_documento', 'tipo_documento']
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.get_tipo_documento_display()} {self.numero_documento} - {self.cliente.nombre}"


class PagoDocumentoCliente(models.Model):
    """Modelo para registrar pagos de documentos de clientes"""
    
    documento = models.ForeignKey(DocumentoCliente, on_delete=models.CASCADE, related_name='pagos', verbose_name="Documento")
    fecha_pago = models.DateTimeField(default=timezone.now, verbose_name="Fecha de Pago")
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name="Monto")
    forma_pago = models.CharField(max_length=100, verbose_name="Forma de Pago")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    
    # Auditoría
    registrado_por = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Registrado por")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    
    class Meta:
        verbose_name = "Pago de Documento de Cliente"
        verbose_name_plural = "Pagos de Documentos de Clientes"
        ordering = ['-fecha_pago']
    
    def __str__(self):
        return f"Pago {self.documento.numero_documento} - ${self.monto} - {self.fecha_pago.strftime('%d/%m/%Y')}"