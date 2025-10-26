"""
Modelos para gestionar Choferes y Vehículos
"""
from django.db import models
from django.core.validators import RegexValidator
from empresas.models import Empresa


class Chofer(models.Model):
    """
    Modelo para gestionar choferes/conductores
    """
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        verbose_name="Empresa",
        related_name='choferes'
    )
    
    # Información personal
    rut = models.CharField(
        max_length=12,
        verbose_name="RUT",
        validators=[
            RegexValidator(
                regex=r'^\d{1,8}-[\dkK]$',
                message='Formato de RUT inválido. Ejemplo: 12345678-9'
            )
        ]
    )
    
    nombre = models.CharField(
        max_length=200,
        verbose_name="Nombre Completo"
    )
    
    telefono = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Teléfono"
    )
    
    email = models.EmailField(
        blank=True,
        verbose_name="Email"
    )
    
    # Licencia de conducir
    licencia_clase = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Clase de Licencia",
        help_text="A1, A2, B, C, D, E, etc."
    )
    
    licencia_numero = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Número de Licencia"
    )
    
    licencia_vencimiento = models.DateField(
        blank=True,
        null=True,
        verbose_name="Vencimiento de Licencia"
    )
    
    # Estado
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    
    # Auditoría
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    
    fecha_modificacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Modificación"
    )
    
    class Meta:
        verbose_name = "Chofer"
        verbose_name_plural = "Choferes"
        ordering = ['nombre']
        unique_together = ['empresa', 'rut']
    
    def __str__(self):
        return f"{self.nombre} ({self.rut})"


class Vehiculo(models.Model):
    """
    Modelo para gestionar vehículos de transporte
    """
    
    TIPO_VEHICULO_CHOICES = [
        ('camion', 'Camión'),
        ('camioneta', 'Camioneta'),
        ('furgon', 'Furgón'),
        ('auto', 'Automóvil'),
        ('moto', 'Motocicleta'),
        ('otro', 'Otro'),
    ]
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        verbose_name="Empresa",
        related_name='vehiculos'
    )
    
    # Identificación del vehículo
    patente = models.CharField(
        max_length=10,
        verbose_name="Patente",
        help_text="Ejemplo: ABCD12"
    )
    
    tipo_vehiculo = models.CharField(
        max_length=20,
        choices=TIPO_VEHICULO_CHOICES,
        default='camioneta',
        verbose_name="Tipo de Vehículo"
    )
    
    marca = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Marca"
    )
    
    modelo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Modelo"
    )
    
    año = models.IntegerField(
        blank=True,
        null=True,
        verbose_name="Año"
    )
    
    # Capacidad
    capacidad_carga = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Capacidad de Carga (kg)"
    )
    
    capacidad_volumen = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Capacidad de Volumen (m³)"
    )
    
    # Información adicional
    color = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Color"
    )
    
    numero_motor = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Número de Motor"
    )
    
    numero_chasis = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Número de Chasis"
    )
    
    # Documentación
    revision_tecnica_vencimiento = models.DateField(
        blank=True,
        null=True,
        verbose_name="Vencimiento Revisión Técnica"
    )
    
    permiso_circulacion_vencimiento = models.DateField(
        blank=True,
        null=True,
        verbose_name="Vencimiento Permiso de Circulación"
    )
    
    seguro_vencimiento = models.DateField(
        blank=True,
        null=True,
        verbose_name="Vencimiento Seguro"
    )
    
    # Estado
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    
    observaciones = models.TextField(
        blank=True,
        verbose_name="Observaciones"
    )
    
    # Auditoría
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    
    fecha_modificacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Modificación"
    )
    
    class Meta:
        verbose_name = "Vehículo"
        verbose_name_plural = "Vehículos"
        ordering = ['patente']
        unique_together = ['empresa', 'patente']
    
    def __str__(self):
        if self.marca and self.modelo:
            return f"{self.patente} - {self.marca} {self.modelo}"
        return f"{self.patente}"
    
    def get_descripcion_completa(self):
        """Retorna descripción completa del vehículo"""
        partes = [self.patente]
        if self.marca:
            partes.append(self.marca)
        if self.modelo:
            partes.append(self.modelo)
        if self.año:
            partes.append(str(self.año))
        return ' - '.join(partes)


