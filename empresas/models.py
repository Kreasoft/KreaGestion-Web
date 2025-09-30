from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone


class Empresa(models.Model):
    """Modelo para gestionar múltiples empresas en el sistema"""
    
    ESTADO_CHOICES = [
        ('activa', 'Activa'),
        ('inactiva', 'Inactiva'),
        ('suspendida', 'Suspendida'),
    ]
    
    nombre = models.CharField(max_length=200, verbose_name="Nombre de Fantasía")
    razon_social = models.CharField(max_length=200, verbose_name="Razón Social")
    rut = models.CharField(
        max_length=12, 
        verbose_name="RUT",
        validators=[
            RegexValidator(
                regex=r'^\d{1,2}\.\d{3}\.\d{3}-[\dkK]$',
                message='El RUT debe tener el formato XX.XXX.XXX-X'
            )
        ]
    )
    
    def clean_rut(self):
        """Limpia y formatea el RUT"""
        if self.rut:
            # Remover espacios y convertir a mayúscula
            rut = self.rut.strip().upper()
            
            # Si no tiene formato, agregarlo
            if '-' not in rut:
                # Separar número y dígito verificador
                if len(rut) > 1:
                    numero = rut[:-1]
                    dv = rut[-1]
                    
                    # Formatear número con puntos
                    if len(numero) > 3:
                        # Agregar puntos cada 3 dígitos desde la derecha
                        numero_formateado = ''
                        for i, digito in enumerate(reversed(numero)):
                            if i > 0 and i % 3 == 0:
                                numero_formateado = '.' + numero_formateado
                            numero_formateado = digito + numero_formateado
                        
                        self.rut = numero_formateado + '-' + dv
                    else:
                        self.rut = numero + '-' + dv
            
            return self.rut
        return self.rut
    
    def save(self, *args, **kwargs):
        """Formatea el RUT antes de guardar"""
        self.clean_rut()
        super().save(*args, **kwargs)
    giro = models.CharField(max_length=200, verbose_name="Giro Comercial")
    direccion = models.TextField(verbose_name="Dirección")
    comuna = models.CharField(max_length=100, verbose_name="Comuna")
    ciudad = models.CharField(max_length=100, verbose_name="Ciudad")
    region = models.CharField(max_length=100, verbose_name="Región")
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    email = models.EmailField(verbose_name="Email")
    sitio_web = models.URLField(blank=True, null=True, verbose_name="Sitio Web")
    
    # Configuración de la empresa
    logo = models.ImageField(upload_to='empresas/logos/', blank=True, null=True, verbose_name="Logo")
    
    # Configuración tributaria
    regimen_tributario = models.CharField(
        max_length=50,
        choices=[
            ('19', '19% IVA'),
            ('exento', 'Exento de IVA'),
            ('otro', 'Otro'),
        ],
        default='19',
        verbose_name="Régimen Tributario"
    )
    
    # Estado y auditoría
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activa')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ['nombre']
        unique_together = ['rut']
    
    def __str__(self):
        return self.nombre
    
    def get_rut_formateado(self):
        """Retorna el RUT formateado"""
        return self.rut
    
    def get_direccion_completa(self):
        """Retorna la dirección completa formateada"""
        return f"{self.direccion}, {self.comuna}, {self.ciudad}, {self.region}"


class Sucursal(models.Model):
    """Modelo para gestionar sucursales de cada empresa"""
    
    ESTADO_CHOICES = [
        ('activa', 'Activa'),
        ('inactiva', 'Inactiva'),
        ('en_construccion', 'En Construcción'),
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='sucursales')
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la Sucursal")
    codigo = models.CharField(max_length=20, verbose_name="Código de Sucursal")
    direccion = models.TextField(verbose_name="Dirección")
    comuna = models.CharField(max_length=100, verbose_name="Comuna")
    ciudad = models.CharField(max_length=100, verbose_name="Ciudad")
    region = models.CharField(max_length=100, verbose_name="Región")
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    
    # Configuración de la sucursal
    es_principal = models.BooleanField(default=False, verbose_name="Es Sucursal Principal")
    horario_apertura = models.TimeField(verbose_name="Hora de Apertura")
    horario_cierre = models.TimeField(verbose_name="Hora de Cierre")
    
    # Responsable de la sucursal
    gerente = models.CharField(max_length=200, blank=True, null=True, verbose_name="Gerente")
    telefono_gerente = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono del Gerente")
    
    # Estado y auditoría
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activa')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Sucursal"
        verbose_name_plural = "Sucursales"
        ordering = ['empresa', 'nombre']
        unique_together = ['empresa', 'codigo']
    
    def __str__(self):
        return f"{self.empresa.nombre} - {self.nombre}"
    
    def save(self, *args, **kwargs):
        """Si esta sucursal es principal, desmarcar las demás"""
        if self.es_principal:
            Sucursal.objects.filter(
                empresa=self.empresa, 
                es_principal=True
            ).exclude(pk=self.pk).update(es_principal=False)
        super().save(*args, **kwargs)
    
    def get_direccion_completa(self):
        """Retorna la dirección completa formateada"""
        return f"{self.direccion}, {self.comuna}, {self.ciudad}, {self.region}"


class ConfiguracionEmpresa(models.Model):
    """Configuraciones específicas por empresa"""
    
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name='configuracion')
    
    # Configuración de ajustes
    prefijo_ajustes = models.CharField(max_length=10, default='Aju', verbose_name="Prefijo Ajustes")
    siguiente_ajuste = models.IntegerField(default=1, verbose_name="Siguiente Número Ajuste")
    formato_ajustes = models.CharField(max_length=20, default='{prefijo}-{000}', verbose_name="Formato Ajustes")
    
    # Configuración de impresión
    imprimir_logo = models.BooleanField(default=True, verbose_name="Imprimir Logo en Documentos")
    pie_pagina_documentos = models.TextField(blank=True, verbose_name="Pie de Página en Documentos")
    
    # Configuración de notificaciones
    alerta_stock_minimo = models.BooleanField(default=True, verbose_name="Alertas de Stock Mínimo")
    notificar_vencimientos = models.BooleanField(default=True, verbose_name="Notificar Vencimientos")
    
    # Configuración de respaldo
    respaldo_automatico = models.BooleanField(default=True, verbose_name="Respaldo Automático")
    frecuencia_respaldo = models.CharField(
        max_length=20,
        choices=[
            ('diario', 'Diario'),
            ('semanal', 'Semanal'),
            ('mensual', 'Mensual'),
        ],
        default='diario',
        verbose_name="Frecuencia de Respaldo"
    )
    
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuración de Empresa"
        verbose_name_plural = "Configuraciones de Empresas"
    
    def __str__(self):
        return f"Configuración de {self.empresa.nombre}"
    
    def generar_numero_ajuste(self):
        """Genera el siguiente número de ajuste"""
        numero = self.siguiente_ajuste
        self.siguiente_ajuste += 1
        self.save()
        
        # Formatear el número según el formato configurado
        formato = self.formato_ajustes
        numero_formateado = formato.format(
            prefijo=self.prefijo_ajustes,
            numero=numero
        ).replace('{000}', f"{numero:03d}")
        
        return numero_formateado
