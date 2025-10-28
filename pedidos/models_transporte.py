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
    
    # Información básica
    codigo = models.CharField(
        max_length=20,
        verbose_name="Código",
        default='CH001'
    )
    
    nombre = models.CharField(
        max_length=200,
        verbose_name="Nombre Completo"
    )
    
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
        ordering = ['codigo']
        unique_together = ['empresa', 'codigo']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Vehiculo(models.Model):
    """
    Modelo para gestionar vehículos de transporte
    """
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        verbose_name="Empresa",
        related_name='vehiculos'
    )
    
    # Información básica
    patente = models.CharField(
        max_length=10,
        verbose_name="Patente",
        help_text="Ejemplo: ABCD12"
    )
    
    descripcion = models.CharField(
        max_length=200,
        verbose_name="Descripción",
        help_text="Ej: Camión Toyota Hilux 2020",
        default='Sin descripción'
    )
    
    capacidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Capacidad (kg)",
        help_text="Capacidad de carga en kilogramos"
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
        verbose_name = "Vehículo"
        verbose_name_plural = "Vehículos"
        ordering = ['patente']
        unique_together = ['empresa', 'patente']
    
    def __str__(self):
        return f"{self.patente} - {self.descripcion}"



