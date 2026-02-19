from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
from decimal import Decimal
from empresas.models import Empresa, Sucursal


class Cliente(models.Model):
    """Modelo para gestionar clientes del sistema"""
    
    TIPO_CLIENTE_CHOICES = [
        ('consumidor_final', 'Consumidor Final'),
        ('contribuyente', 'Contribuyente'),
        ('exento', 'Exento de IVA'),
        ('extranjero', 'Extranjero'),
    ]
    
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
        ('suspendido', 'Suspendido'),
        ('moroso', 'Moroso'),
    ]
    
    # Información básica
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    rut = models.CharField(
        max_length=12, 
        null=True,
        blank=True,
        verbose_name="RUT",
        help_text="Formato: 12.345.678-9 o 12345678-9"
    )
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Cliente")
    
    # Información tributaria
    tipo_cliente = models.CharField(max_length=20, choices=TIPO_CLIENTE_CHOICES, default='consumidor_final')
    giro = models.CharField(max_length=200, blank=True, verbose_name="Giro Comercial")
    
    # Información de contacto
    direccion = models.TextField(verbose_name="Dirección")
    comuna = models.CharField(max_length=100, verbose_name="Comuna")
    ciudad = models.CharField(max_length=100, verbose_name="Ciudad")
    region = models.CharField(max_length=100, blank=True, verbose_name="Región")
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    sitio_web = models.CharField(max_length=200, blank=True, null=True, verbose_name="Sitio Web", help_text="Formato: www.ejemplo.cl o https://www.ejemplo.cl")
    
    # Información comercial
    limite_credito = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        verbose_name="Límite de Crédito"
    )
    plazo_pago = models.IntegerField(default=30, verbose_name="Plazo de Pago (días)")
    descuento_porcentaje = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        verbose_name="Descuento por Defecto (%)"
    )
    
    # Estado
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activo')
    
    # Ruta de despacho asignada
    ruta = models.ForeignKey(
        'pedidos.Ruta',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clientes',
        verbose_name="Ruta de Despacho",
        help_text="Ruta asignada para el despacho de productos a este cliente"
    )
    
    # Vendedor asignado (Para centralización en preventa móvil)
    vendedor = models.ForeignKey(
        'ventas.Vendedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clientes_asignados',
        verbose_name="Vendedor Asignado",
        help_text="Vendedor responsable de este cliente"
    )
    
    # Información adicional
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    fecha_alta = models.DateField(default=timezone.now, verbose_name="Fecha de Alta")
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre']
        unique_together = ['empresa', 'rut']
    
    def __str__(self):
        return f"{self.get_rut_formateado()} - {self.nombre}"
    
    def get_rut_formateado(self):
        """Retorna el RUT formateado con puntos y guión"""
        if not self.rut:
            return "Sin RUT"
        
        # Limpiar el RUT (quitar puntos y guiones)
        rut_limpio = self.rut.replace('.', '').replace('-', '')
        
        if len(rut_limpio) < 8:
            return self.rut
        
        # Separar número y dígito verificador
        numero = rut_limpio[:-1]
        dv = rut_limpio[-1].upper()
        
        # Formatear con puntos
        if len(numero) == 7:
            # RUT de 7 dígitos: 1.234.567-8
            numero_formateado = f"{numero[0]}.{numero[1:4]}.{numero[4:7]}"
        elif len(numero) == 8:
            # RUT de 8 dígitos: 12.345.678-9
            numero_formateado = f"{numero[0:2]}.{numero[2:5]}.{numero[5:8]}"
        else:
            return self.rut
        
        return f"{numero_formateado}-{dv}"
    
    def get_direccion_completa(self):
        """Retorna la dirección completa formateada"""
        return f"{self.direccion}, {self.comuna}, {self.ciudad}, {self.region}"
    
    def get_sitio_web_formateado(self):
        """Retorna el sitio web formateado con protocolo si es necesario"""
        if not self.sitio_web:
            return ""
        
        sitio = self.sitio_web.strip()
        
        # Si ya tiene protocolo, devolverlo tal como está
        if sitio.startswith(('http://', 'https://')):
            return sitio
        
        # Si empieza con www, agregar https://
        if sitio.startswith('www.'):
            return f"https://{sitio}"
        
        # Si no tiene www ni protocolo, agregar ambos
        if not sitio.startswith(('http://', 'https://', 'www.')):
            return f"https://www.{sitio}"
        
        return sitio
    
    def get_saldo_actual(self):
        """Retorna el saldo actual de la cuenta corriente"""
        ultimo_movimiento = self.movimientos_cuenta.order_by('-fecha', '-id').first()
        if ultimo_movimiento:
            return ultimo_movimiento.saldo_nuevo
        return Decimal('0.00')
    
    def get_limite_disponible(self):
        """Retorna el límite de crédito disponible"""
        saldo_actual = self.get_saldo_actual()
        return self.limite_credito - saldo_actual
    
    def puede_vender_credito(self):
        """Verifica si se puede vender a crédito al cliente"""
        if self.estado != 'activo':
            return False
        
        saldo_actual = self.get_saldo_actual()
        return saldo_actual < self.limite_credito
    
    def get_estado_display_color(self):
        """Retorna el color CSS para el estado"""
        colores = {
            'activo': 'success',
            'inactivo': 'secondary',
            'suspendido': 'warning',
            'moroso': 'danger',
        }
        return colores.get(self.estado, 'secondary')


class ContactoCliente(models.Model):
    """Modelo para contactos adicionales del cliente"""
    
    TIPO_CONTACTO_CHOICES = [
        ('principal', 'Contacto Principal'),
        ('comercial', 'Contacto Comercial'),
        ('administrativo', 'Contacto Administrativo'),
        ('tecnico', 'Contacto Técnico'),
        ('otro', 'Otro'),
    ]
    
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='contactos')
    
    # Información del contacto
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Contacto")
    cargo = models.CharField(max_length=100, blank=True, verbose_name="Cargo")
    tipo_contacto = models.CharField(max_length=20, choices=TIPO_CONTACTO_CHOICES, default='otro')
    
    # Información de contacto
    telefono = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    celular = models.CharField(max_length=20, blank=True, verbose_name="Celular")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    
    # Información adicional
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    es_contacto_principal = models.BooleanField(default=False, verbose_name="Es Contacto Principal")
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Contacto de Cliente"
        verbose_name_plural = "Contactos de Clientes"
        ordering = ['cliente', 'tipo_contacto', 'nombre']
    
    def __str__(self):
        return f"{self.cliente.nombre} - {self.nombre}"
    
    def save(self, *args, **kwargs):
        """Si este contacto es principal, desmarcar los demás"""
        if self.es_contacto_principal:
            ContactoCliente.objects.filter(
                cliente=self.cliente, 
                es_contacto_principal=True
            ).exclude(pk=self.pk).update(es_contacto_principal=False)
        super().save(*args, **kwargs)


class CuentaCorrienteCliente(models.Model):
    """Modelo para gestionar la cuenta corriente de clientes"""
    
    TIPO_MOVIMIENTO_CHOICES = [
        ('venta', 'Venta'),
        ('pago', 'Pago'),
        ('nota_credito', 'Nota de Crédito'),
        ('nota_debito', 'Nota de Débito'),
        ('ajuste', 'Ajuste'),
        ('devolucion', 'Devolución'),
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='movimientos_cuenta')
    
    # Información del movimiento
    fecha = models.DateField(default=timezone.now, verbose_name="Fecha del Movimiento")
    tipo_movimiento = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO_CHOICES, verbose_name="Tipo de Movimiento")
    
    # Referencias (temporalmente comentadas)
    # venta = models.ForeignKey('ventas.Venta', on_delete=models.SET_NULL, null=True, blank=True)
    # devolucion = models.ForeignKey('ventas.Devolucion', on_delete=models.SET_NULL, null=True, blank=True)
    # documento_tributario = models.ForeignKey('documentos.DocumentoTributario', on_delete=models.SET_NULL, null=True, blank=True)
    
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
        verbose_name = "Movimiento de Cuenta Corriente de Cliente"
        verbose_name_plural = "Movimientos de Cuenta Corriente de Clientes"
        ordering = ['-fecha', '-id']
    
    def __str__(self):
        return f"{self.cliente.nombre} - {self.tipo_movimiento} - {self.monto}"
    
    def save(self, *args, **kwargs):
        """Calcula el saldo nuevo al guardar"""
        if not self.pk:  # Solo para nuevos registros
            # Obtener el último saldo del cliente
            ultimo_movimiento = CuentaCorrienteCliente.objects.filter(
                empresa=self.empresa,
                cliente=self.cliente
            ).order_by('-fecha', '-id').first()
            
            if ultimo_movimiento:
                self.saldo_anterior = ultimo_movimiento.saldo_nuevo
            else:
                self.saldo_anterior = Decimal('0.00')
            
            # Calcular saldo nuevo según el tipo de movimiento
            if self.tipo_movimiento in ['venta', 'nota_debito', 'ajuste']:
                self.saldo_nuevo = self.saldo_anterior + self.monto
            else:  # pago, nota_credito, devolucion
                self.saldo_nuevo = self.saldo_anterior - self.monto
        
        super().save(*args, **kwargs)
    
    def get_tipo_movimiento_display_color(self):
        """Retorna el color CSS para el tipo de movimiento"""
        colores = {
            'venta': 'danger',
            'pago': 'success',
            'nota_credito': 'info',
            'nota_debito': 'warning',
            'ajuste': 'secondary',
            'devolucion': 'info',
        }
        return colores.get(self.tipo_movimiento, 'secondary')


class HistorialPreciosCliente(models.Model):
    """Modelo para mantener historial de precios por cliente"""
    
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='historial_precios')
    # producto = models.ForeignKey('productos.Producto', on_delete=models.CASCADE)
    
    # Precios
    precio_anterior = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Precio Anterior")
    precio_nuevo = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Precio Nuevo")
    
    # Información del cambio
    fecha_cambio = models.DateTimeField(auto_now_add=True, verbose_name="Fecha del Cambio")
    motivo_cambio = models.TextField(blank=True, verbose_name="Motivo del Cambio")
    
    # Auditoría
    cambiado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Historial de Precios por Cliente"
        verbose_name_plural = "Historial de Precios por Cliente"
        ordering = ['-fecha_cambio']
    
    def __str__(self):
        return f"{self.cliente.nombre} - {self.producto.nombre} - {self.fecha_cambio}"
    
    def get_porcentaje_cambio(self):
        """Calcula el porcentaje de cambio en el precio"""
        if self.precio_anterior > 0:
            cambio = ((self.precio_nuevo - self.precio_anterior) / self.precio_anterior) * 100
            return round(cambio, 2)
        return Decimal('0.00')
    
    def get_tipo_cambio(self):
        """Retorna si el cambio fue aumento o disminución"""
        if self.precio_nuevo > self.precio_anterior:
            return 'aumento'
        elif self.precio_nuevo < self.precio_anterior:
            return 'disminucion'
        else:
            return 'sin_cambio'
