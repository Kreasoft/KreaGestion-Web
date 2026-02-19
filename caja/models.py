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
        # Obtener todos los movimientos de venta
        movimientos_venta = self.movimientos.filter(tipo='venta').select_related('forma_pago', 'venta')
        
        # Obtener movimientos de devolución (notas de crédito, devoluciones que restan dinero)
        movimientos_devolucion = self.movimientos.filter(tipo='devolucion').select_related('forma_pago', 'venta')
        
        print(f"[CALCULAR_TOTALES] Total movimientos de venta: {movimientos_venta.count()}")
        print(f"[CALCULAR_TOTALES] Total movimientos de devolución: {movimientos_devolucion.count()}")
        
        # Inicializar totales
        self.total_ventas_efectivo = Decimal('0.00')
        self.total_ventas_tarjeta = Decimal('0.00')
        self.total_ventas_transferencia = Decimal('0.00')
        self.total_ventas_cheque = Decimal('0.00')
        self.total_ventas_credito = Decimal('0.00')
        
        # Clasificar cada movimiento por forma de pago
        # Solo incluir: boletas, facturas, vales internos, notas de crédito y débito
        # Excluir: tickets facturables, guías y cotizaciones
        documentos_permitidos = ['boleta', 'factura', 'vale']
        documentos_excluidos = ['ticket', 'guia', 'cotizacion']
        
        # Procesar movimientos de VENTA (suman dinero)
        for movimiento in movimientos_venta:
            # Excluir tickets facturables, guías y cotizaciones
            if movimiento.venta and movimiento.venta.tipo_documento in documentos_excluidos:
                print(f"[CALCULAR_TOTALES] Movimiento {movimiento.id} excluido: {movimiento.venta.tipo_documento}")
                continue
            
            # Solo incluir boletas y facturas (las notas de crédito/débito se manejan por DTE)
            if movimiento.venta and movimiento.venta.tipo_documento not in documentos_permitidos:
                print(f"[CALCULAR_TOTALES] Movimiento {movimiento.id} excluido (tipo no permitido): {movimiento.venta.tipo_documento}")
                continue
                
            if not movimiento.forma_pago:
                print(f"[CALCULAR_TOTALES] Movimiento {movimiento.id} sin forma de pago - saltando")
                continue
                
            forma_pago = movimiento.forma_pago
            monto = movimiento.monto
            
            print(f"[CALCULAR_TOTALES] Movimiento VENTA {movimiento.id}: {forma_pago.nombre} (codigo: {forma_pago.codigo}), monto: ${monto}, es_cuenta_corriente: {forma_pago.es_cuenta_corriente}, requiere_cheque: {forma_pago.requiere_cheque}")
            
            # Prioridad: primero verificar campos booleanos específicos
            if forma_pago.es_cuenta_corriente:
                self.total_ventas_credito += monto
                print(f"  -> Clasificado como CRÉDITO: ${monto}")
            elif forma_pago.requiere_cheque:
                self.total_ventas_cheque += monto
                print(f"  -> Clasificado como CHEQUE: ${monto}")
            else:
                # Luego verificar por nombre o código
                nombre_lower = forma_pago.nombre.lower()
                codigo_lower = forma_pago.codigo.lower() if forma_pago.codigo else ''
                
                if 'efectivo' in nombre_lower or codigo_lower in ['ef', 'efectivo', 'cash']:
                    self.total_ventas_efectivo += monto
                    print(f"  -> Clasificado como EFECTIVO: ${monto}")
                elif 'tarjeta' in nombre_lower or 'card' in nombre_lower or codigo_lower in ['tc', 'td', 'tarjeta', 'tr', 'cr']:
                    self.total_ventas_tarjeta += monto
                    print(f"  -> Clasificado como TARJETA: ${monto}")
                elif 'transferencia' in nombre_lower or 'transfer' in nombre_lower or codigo_lower in ['tr', 'transferencia', 'tf']:
                    self.total_ventas_transferencia += monto
                    print(f"  -> Clasificado como TRANSFERENCIA: ${monto}")
                else:
                    # Por defecto, si no se identifica, se considera efectivo
                    self.total_ventas_efectivo += monto
                    print(f"  -> Clasificado como EFECTIVO (por defecto): ${monto}")
        
        # Procesar movimientos de DEVOLUCIÓN (restan dinero - notas de crédito, devoluciones)
        for movimiento in movimientos_devolucion:
            if not movimiento.forma_pago:
                print(f"[CALCULAR_TOTALES] Movimiento DEVOLUCIÓN {movimiento.id} sin forma de pago - saltando")
                continue
            
            forma_pago = movimiento.forma_pago
            monto = movimiento.monto  # Este monto se RESTA del total
            
            print(f"[CALCULAR_TOTALES] Movimiento DEVOLUCIÓN {movimiento.id}: {forma_pago.nombre} (codigo: {forma_pago.codigo}), monto a restar: ${monto}")
            
            # Restar el monto de la forma de pago correspondiente
            if forma_pago.es_cuenta_corriente:
                self.total_ventas_credito -= monto
                print(f"  -> Restado de CRÉDITO: -${monto}")
            elif forma_pago.requiere_cheque:
                self.total_ventas_cheque -= monto
                print(f"  -> Restado de CHEQUE: -${monto}")
            else:
                nombre_lower = forma_pago.nombre.lower()
                codigo_lower = forma_pago.codigo.lower() if forma_pago.codigo else ''
                
                if 'efectivo' in nombre_lower or codigo_lower in ['ef', 'efectivo', 'cash']:
                    self.total_ventas_efectivo -= monto
                    print(f"  -> Restado de EFECTIVO: -${monto}")
                elif 'tarjeta' in nombre_lower or 'card' in nombre_lower or codigo_lower in ['tc', 'td', 'tarjeta', 'tr', 'cr']:
                    self.total_ventas_tarjeta -= monto
                    print(f"  -> Restado de TARJETA: -${monto}")
                elif 'transferencia' in nombre_lower or 'transfer' in nombre_lower or codigo_lower in ['tr', 'transferencia', 'tf']:
                    self.total_ventas_transferencia -= monto
                    print(f"  -> Restado de TRANSFERENCIA: -${monto}")
                else:
                    # Por defecto, se resta del efectivo
                    self.total_ventas_efectivo -= monto
                    print(f"  -> Restado de EFECTIVO (por defecto): -${monto}")
        
        print(f"[CALCULAR_TOTALES] Totales finales:")
        print(f"  Efectivo: ${self.total_ventas_efectivo}")
        print(f"  Tarjeta: ${self.total_ventas_tarjeta}")
        print(f"  Transferencia: ${self.total_ventas_transferencia}")
        print(f"  Cheque: ${self.total_ventas_cheque}")
        print(f"  Crédito: ${self.total_ventas_credito}")
        
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
