"""
Modelos para gestionar Rutas y Hojas de Ruta
Las rutas son configuraciones maestras que se asignan a clientes.
Las hojas de ruta se generan automáticamente al emitir facturas.
"""
from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal

from empresas.models import Empresa
from facturacion_electronica.models import DocumentoTributarioElectronico


class Ruta(models.Model):
    """
    Modelo para gestionar rutas maestras de despacho
    Las rutas se asignan a clientes y se usan para agrupar facturas en hojas de ruta
    """
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        verbose_name="Empresa",
        related_name='rutas'
    )
    
    codigo = models.CharField(
        max_length=20,
        verbose_name="Código de Ruta",
        help_text="Ejemplo: RUTA-01, NORTE-01, etc."
    )
    
    nombre = models.CharField(
        max_length=200,
        verbose_name="Nombre de la Ruta",
        help_text="Ejemplo: Ruta Norte, Ruta Centro, Ruta Sur"
    )
    
    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción",
        help_text="Descripción detallada de la ruta, zonas que cubre, etc."
    )
    
    # Información de la ruta - Ruta diaria por móvil
    vehiculo = models.ForeignKey(
        'pedidos.Vehiculo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rutas',
        verbose_name="Vehículo",
        help_text="Vehículo asignado a esta ruta"
    )
    
    chofer = models.ForeignKey(
        'pedidos.Chofer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rutas_como_chofer',
        verbose_name="Chofer",
        help_text="Chofer asignado a esta ruta",
        limit_choices_to={'tipo': 'chofer', 'activo': True}
    )
    
    acompanante = models.ForeignKey(
        'pedidos.Chofer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rutas_como_acompanante',
        verbose_name="Acompañante",
        help_text="Acompañante asignado a esta ruta (opcional)",
        limit_choices_to={'tipo': 'acompanante', 'activo': True}
    )
    
    # Información de la ruta
    dias_visita = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Días de Visita",
        help_text="Ejemplo: Lunes, Miércoles, Viernes"
    )
    
    orden_visita = models.IntegerField(
        default=0,
        verbose_name="Orden de Visita",
        help_text="Orden en que se visita esta ruta (1, 2, 3...)"
    )
    
    # Estado
    activo = models.BooleanField(
        default=True,
        verbose_name="Activa"
    )
    
    # Auditoría
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rutas_creadas',
        verbose_name="Creado por"
    )
    
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    
    fecha_modificacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Modificación"
    )
    
    class Meta:
        verbose_name = "Ruta"
        verbose_name_plural = "Rutas"
        ordering = ['orden_visita', 'codigo']
        unique_together = ['empresa', 'codigo']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    def get_clientes_count(self):
        """Retorna la cantidad de clientes asignados a esta ruta"""
        return self.clientes.count()


class HojaRuta(models.Model):
    """
    Modelo para gestionar hojas de ruta
    Se generan automáticamente al emitir facturas y agrupan facturas por:
    - Ruta del cliente
    - Vehículo
    - Chofer
    - Fecha
    """
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_ruta', 'En Ruta'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        verbose_name="Empresa",
        related_name='hojas_ruta'
    )
    
    ruta = models.ForeignKey(
        Ruta,
        on_delete=models.CASCADE,
        verbose_name="Ruta",
        related_name='hojas_ruta'
    )
    
    numero_ruta = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Número de Hoja de Ruta",
        help_text="Auto-generado: HR-YYYYMMDD-RUTA-XXX"
    )
    
    fecha = models.DateField(
        default=timezone.now,
        verbose_name="Fecha de Ruta"
    )
    
    # Información de transporte
    vehiculo = models.ForeignKey(
        'pedidos.Vehiculo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hojas_ruta',
        verbose_name="Vehículo"
    )
    
    chofer = models.ForeignKey(
        'pedidos.Chofer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hojas_ruta',
        verbose_name="Chofer"
    )
    
    acompanante = models.ForeignKey(
        'pedidos.Chofer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hojas_ruta_como_acompanante',
        verbose_name="Acompañante",
        help_text="Acompañante asignado a esta hoja de ruta",
        limit_choices_to={'tipo': 'acompanante', 'activo': True}
    )
    
    ayudante = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Ayudante",
        help_text="Nombre del ayudante si aplica (campo adicional)"
    )
    
    # Facturas asociadas (DTEs)
    facturas = models.ManyToManyField(
        DocumentoTributarioElectronico,
        related_name='hojas_ruta',
        verbose_name="Facturas",
        help_text="Facturas incluidas en esta hoja de ruta"
    )
    
    # Estado
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name="Estado"
    )
    
    # Información adicional
    observaciones = models.TextField(
        blank=True,
        verbose_name="Observaciones"
    )
    
    hora_salida = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Hora de Salida"
    )
    
    hora_llegada = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Hora de Llegada"
    )
    
    kilometraje_salida = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Kilometraje de Salida"
    )
    
    kilometraje_llegada = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Kilometraje de Llegada"
    )
    
    # Auditoría
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hojas_ruta_creadas',
        verbose_name="Creado por"
    )
    
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    
    fecha_modificacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Modificación"
    )
    
    class Meta:
        verbose_name = "Hoja de Ruta"
        verbose_name_plural = "Hojas de Ruta"
        ordering = ['-fecha', '-numero_ruta']
        unique_together = ['empresa', 'numero_ruta']
    
    def __str__(self):
        return f"{self.numero_ruta} - {self.ruta.nombre} - {self.fecha}"
    
    def generar_numero_ruta(self):
        """Genera número único de hoja de ruta"""
        if not self.numero_ruta:
            fecha_str = self.fecha.strftime('%Y%m%d')
            ruta_codigo = self.ruta.codigo.replace('-', '').upper()
            
            # Contar hojas de ruta del día para esta ruta
            hoy = timezone.now().date()
            count = HojaRuta.objects.filter(
                empresa=self.empresa,
                ruta=self.ruta,
                fecha=hoy
            ).count()
            
            numero = f"HR-{fecha_str}-{ruta_codigo}-{count + 1:03d}"
            return numero
        return self.numero_ruta
    
    def save(self, *args, **kwargs):
        """Genera número de ruta automáticamente si no existe"""
        if not self.numero_ruta:
            self.numero_ruta = self.generar_numero_ruta()
        super().save(*args, **kwargs)
    
    def get_total_facturas(self):
        """Retorna el total de facturas en esta hoja de ruta"""
        return self.facturas.count()
    
    def get_monto_total(self):
        """Retorna el monto total de todas las facturas"""
        return self.facturas.aggregate(
            total=Sum('monto_total')
        )['total'] or Decimal('0.00')
    
    def get_clientes_count(self):
        """Retorna la cantidad de clientes únicos en las facturas"""
        return self.facturas.values('rut_receptor').distinct().count()

