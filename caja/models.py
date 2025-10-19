from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from empresas.models import Empresa, Sucursal
from ventas.models import Venta, EstacionTrabajo, FormaPago
from clientes.models import Cliente
from bodegas.models import Bodega


class Caja(models.Model):
    """Modelo para gestionar cajas (puntos de cobro)"""
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, verbose_name="Sucursal")
    estacion_trabajo = models.ForeignKey(EstacionTrabajo, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Estación de Trabajo")
    bodega = models.ForeignKey(Bodega, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Bodega", help_text="Bodega desde donde se descontará el stock")
    
    numero = models.CharField(max_length=10, verbose_name="Número de Caja")
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Caja")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    
    activo = models.BooleanField(default=True, verbose_name="Activo")
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Caja"
        verbose_name_plural = "Cajas"
        ordering = ['numero']
        unique_together = ['empresa', 'numero']
    
    def __str__(self):
        return f"Caja {self.numero} - {self.nombre}"
    
    def tiene_apertura_activa(self):
        """Verifica si la caja tiene una apertura activa"""
        return self.aperturascaja.filter(estado='abierta').exists()
    
    def get_apertura_activa(self):
        """Retorna la apertura activa si existe"""
        return self.aperturascaja.filter(estado='abierta').first()


class AperturaCaja(models.Model):
    """Modelo para gestionar aperturas y cierres de caja"""
    
    ESTADO_CHOICES = [
        ('abierta', 'Abierta'),
        ('cerrada', 'Cerrada'),
    ]
    
    caja = models.ForeignKey(Caja, on_delete=models.CASCADE, related_name='aperturascaja', verbose_name="Caja")
    usuario_apertura = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='aperturas_caja', verbose_name="Usuario Apertura")
    usuario_cierre = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cierres_caja', verbose_name="Usuario Cierre")
    
    fecha_apertura = models.DateTimeField(default=timezone.now, verbose_name="Fecha Apertura")
    fecha_cierre = models.DateTimeField(null=True, blank=True, verbose_name="Fecha Cierre")
    
    monto_inicial = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))], verbose_name="Monto Inicial")
    monto_final = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))], verbose_name="Monto Final")
    
    # Totales por tipo de movimiento
    total_ventas_efectivo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Total Ventas Efectivo")
    total_ventas_tarjeta = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Total Ventas Tarjeta")
    total_ventas_transferencia = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Total Ventas Transferencia")
    total_ventas_cheque = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Total Ventas Cheque")
    total_ventas_credito = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Total Ventas Crédito")
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='abierta', verbose_name="Estado")
    observaciones_apertura = models.TextField(blank=True, verbose_name="Observaciones Apertura")
    observaciones_cierre = models.TextField(blank=True, verbose_name="Observaciones Cierre")
    
    class Meta:
        verbose_name = "Apertura de Caja"
        verbose_name_plural = "Aperturas de Caja"
        ordering = ['-fecha_apertura']
    
    def __str__(self):
        return f"Apertura {self.caja.nombre} - {self.fecha_apertura.strftime('%d/%m/%Y %H:%M')}"
    
    def calcular_totales(self):
        """Calcula los totales de la apertura"""
        movimientos = self.movimientos.filter(tipo='venta')
        
        self.total_ventas_efectivo = sum(m.monto for m in movimientos.filter(forma_pago__nombre__icontains='efectivo'))
        self.total_ventas_tarjeta = sum(m.monto for m in movimientos.filter(forma_pago__nombre__icontains='tarjeta'))
        self.total_ventas_transferencia = sum(m.monto for m in movimientos.filter(forma_pago__nombre__icontains='transferencia'))
        self.total_ventas_cheque = sum(m.monto for m in movimientos.filter(forma_pago__requiere_cheque=True))
        self.total_ventas_credito = sum(m.monto for m in movimientos.filter(forma_pago__es_cuenta_corriente=True))
        
        total_efectivo_caja = self.monto_inicial + self.total_ventas_efectivo
        self.monto_final = total_efectivo_caja
        
        self.save()
    
    def cerrar_caja(self, usuario, monto_contado, observaciones=''):
        """Cierra la caja"""
        self.usuario_cierre = usuario
        self.fecha_cierre = timezone.now()
        self.estado = 'cerrada'
        self.observaciones_cierre = observaciones
        
        # Calcular totales
        self.calcular_totales()
        
        # Registrar diferencia si existe
        diferencia = monto_contado - self.monto_final
        if diferencia != 0:
            self.observaciones_cierre += f"\n\nDiferencia de caja: ${diferencia}"
        
        self.save()


class MovimientoCaja(models.Model):
    """Modelo para registrar todos los movimientos de caja"""
    
    TIPO_MOVIMIENTO_CHOICES = [
        ('venta', 'Venta'),
        ('devolucion', 'Devolución'),
        ('retiro', 'Retiro'),
        ('ingreso', 'Ingreso'),
    ]
    
    apertura_caja = models.ForeignKey(AperturaCaja, on_delete=models.CASCADE, related_name='movimientos', verbose_name="Apertura de Caja")
    venta = models.ForeignKey(Venta, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Venta")
    
    tipo = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO_CHOICES, verbose_name="Tipo de Movimiento")
    fecha = models.DateTimeField(default=timezone.now, verbose_name="Fecha")
    
    forma_pago = models.ForeignKey(FormaPago, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Forma de Pago")
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], verbose_name="Monto")
    
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Usuario")
    
    # Para cheques
    numero_cheque = models.CharField(max_length=50, blank=True, verbose_name="Número de Cheque")
    banco = models.CharField(max_length=100, blank=True, verbose_name="Banco")
    fecha_cheque = models.DateField(null=True, blank=True, verbose_name="Fecha del Cheque")
    
    class Meta:
        verbose_name = "Movimiento de Caja"
        verbose_name_plural = "Movimientos de Caja"
        ordering = ['-fecha']
    
    def __str__(self):
        return f"{self.get_tipo_display()} - ${self.monto} - {self.fecha.strftime('%d/%m/%Y %H:%M')}"


class VentaProcesada(models.Model):
    """Modelo para registrar ventas procesadas por caja (para trazabilidad)"""
    
    venta_preventa = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='venta_preventa', verbose_name="Preventa (Ticket)")
    venta_final = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='venta_final', verbose_name="Venta Final (Documento Tributario)")
    
    apertura_caja = models.ForeignKey(AperturaCaja, on_delete=models.CASCADE, verbose_name="Apertura de Caja")
    movimiento_caja = models.ForeignKey(MovimientoCaja, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Movimiento de Caja")
    
    fecha_proceso = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Proceso")
    usuario_proceso = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Usuario que Procesó")
    
    # Información del pago
    monto_recibido = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Monto Recibido")
    monto_cambio = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Monto de Cambio")
    
    # Flags de proceso
    stock_descontado = models.BooleanField(default=False, verbose_name="Stock Descontado")
    cuenta_corriente_actualizada = models.BooleanField(default=False, verbose_name="Cuenta Corriente Actualizada")

    # Facturación Electrónica
    dte_generado = models.ForeignKey(
        'facturacion_electronica.DocumentoTributarioElectronico',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="DTE Generado"
    )

    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    
    class Meta:
        verbose_name = "Venta Procesada"
        verbose_name_plural = "Ventas Procesadas"
        ordering = ['-fecha_proceso']
    
    def __str__(self):
        return f"Ticket #{self.venta_preventa.numero_venta} → {self.venta_final.get_tipo_documento_display()} #{self.venta_final.numero_venta}"
