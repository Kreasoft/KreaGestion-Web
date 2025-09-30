from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
from decimal import Decimal
from empresas.models import Empresa


class Proveedor(models.Model):
    """Modelo para gestionar proveedores del sistema"""
    
    TIPO_PROVEEDOR_CHOICES = [
        ('productos', 'Productos'),
        ('servicios', 'Servicios'),
        ('ambos', 'Productos y Servicios'),
    ]
    
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
        ('suspendido', 'Suspendido'),
        ('bloqueado', 'Bloqueado'),
    ]
    
    # Información básica
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Proveedor")
    razon_social = models.CharField(max_length=200, blank=True, verbose_name="Razón Social")
    
    # Información tributaria
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
    giro = models.CharField(max_length=200, verbose_name="Giro Comercial")
    
    # Clasificación
    tipo_proveedor = models.CharField(max_length=20, choices=TIPO_PROVEEDOR_CHOICES, default='productos')
    categoria_principal = models.CharField(max_length=100, blank=True, verbose_name="Categoría Principal")
    
    # Información de contacto
    direccion = models.TextField(verbose_name="Dirección")
    comuna = models.CharField(max_length=100, verbose_name="Comuna")
    ciudad = models.CharField(max_length=100, verbose_name="Ciudad")
    region = models.CharField(max_length=100, verbose_name="Región")
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    sitio_web = models.URLField(blank=True, null=True, verbose_name="Sitio Web")
    
    # Información comercial
    plazo_entrega = models.CharField(max_length=100, blank=True, verbose_name="Plazo de Entrega")
    condiciones_pago = models.CharField(max_length=200, blank=True, verbose_name="Condiciones de Pago")
    descuento_porcentaje = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        verbose_name="Descuento por Defecto (%)"
    )
    
    # Calificación del proveedor
    calificacion = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        default=3,
        verbose_name="Calificación (1-5)"
    )
    observaciones_calidad = models.TextField(blank=True, verbose_name="Observaciones de Calidad")
    
    # Estado
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activo')
    
    # Información adicional
    observaciones = models.TextField(blank=True, verbose_name="Observaciones Generales")
    fecha_alta = models.DateField(default=timezone.now, verbose_name="Fecha de Alta")
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
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
    
    def get_estado_display_color(self):
        """Retorna el color CSS para el estado"""
        colores = {
            'activo': 'success',
            'inactivo': 'secondary',
            'suspendido': 'warning',
            'bloqueado': 'danger',
        }
        return colores.get(self.estado, 'secondary')
    
    def get_calificacion_estrellas(self):
        """Retorna las estrellas de calificación en HTML"""
        estrellas = "★" * self.calificacion + "☆" * (5 - self.calificacion)
        return estrellas


class ContactoProveedor(models.Model):
    """Modelo para contactos adicionales del proveedor"""
    
    TIPO_CONTACTO_CHOICES = [
        ('principal', 'Contacto Principal'),
        ('comercial', 'Contacto Comercial'),
        ('administrativo', 'Contacto Administrativo'),
        ('tecnico', 'Contacto Técnico'),
        ('facturacion', 'Facturación'),
        ('otro', 'Otro'),
    ]
    
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name='contactos')
    
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
        verbose_name = "Contacto de Proveedor"
        verbose_name_plural = "Contactos de Proveedores"
        ordering = ['proveedor', 'tipo_contacto', 'nombre']
    
    def __str__(self):
        return f"{self.proveedor.nombre} - {self.nombre}"
    
    def save(self, *args, **kwargs):
        """Si este contacto es principal, desmarcar los demás"""
        if self.es_contacto_principal:
            ContactoProveedor.objects.filter(
                proveedor=self.proveedor, 
                es_contacto_principal=True
            ).exclude(pk=self.pk).update(es_contacto_principal=False)
        super().save(*args, **kwargs)


class CategoriaProveedor(models.Model):
    """Modelo para categorías de productos/servicios que ofrece el proveedor"""
    
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name='categorias')
    # categoria = models.ForeignKey('productos.CategoriaProducto', on_delete=models.CASCADE)
    
    # Información de la categoría
    es_categoria_principal = models.BooleanField(default=False, verbose_name="Es Categoría Principal")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    
    # Condiciones específicas
    plazo_entrega_categoria = models.CharField(max_length=100, blank=True, verbose_name="Plazo de Entrega")
    descuento_categoria = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        verbose_name="Descuento Específico (%)"
    )
    
    # Estado
    activa = models.BooleanField(default=True, verbose_name="Categoría Activa")
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Categoría de Proveedor"
        verbose_name_plural = "Categorías de Proveedores"
        # unique_together = ['proveedor', 'categoria']
        ordering = ['proveedor']
    
    def __str__(self):
        return f"{self.proveedor.nombre} - Categoría"
    
    def save(self, *args, **kwargs):
        """Si esta categoría es principal, desmarcar las demás"""
        if self.es_categoria_principal:
            CategoriaProveedor.objects.filter(
                proveedor=self.proveedor, 
                es_categoria_principal=True
            ).exclude(pk=self.pk).update(es_categoria_principal=False)
        super().save(*args, **kwargs)


class HistorialPreciosProveedor(models.Model):
    """Modelo para mantener historial de precios de productos del proveedor"""
    
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name='historial_precios')
    # producto = models.ForeignKey('productos.Producto', on_delete=models.CASCADE)
    
    # Precios
    precio_anterior = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Precio Anterior")
    precio_nuevo = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Precio Nuevo")
    
    # Información del cambio
    fecha_cambio = models.DateTimeField(auto_now_add=True, verbose_name="Fecha del Cambio")
    motivo_cambio = models.TextField(blank=True, verbose_name="Motivo del Cambio")
    
    # Referencias
    orden_compra = models.ForeignKey('compras.OrdenCompra', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Auditoría
    cambiado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Historial de Precios del Proveedor"
        verbose_name_plural = "Historial de Precios de Proveedores"
        ordering = ['-fecha_cambio']
    
    def __str__(self):
        return f"{self.proveedor.nombre} - {self.producto.nombre} - {self.fecha_cambio}"
    
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


class EvaluacionProveedor(models.Model):
    """Modelo para evaluaciones periódicas de proveedores"""
    
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name='evaluaciones')
    
    # Información de la evaluación
    fecha_evaluacion = models.DateField(default=timezone.now, verbose_name="Fecha de Evaluación")
    periodo_evaluado = models.CharField(max_length=50, verbose_name="Período Evaluado")
    
    # Criterios de evaluación (1-5)
    calidad_productos = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        verbose_name="Calidad de Productos"
    )
    cumplimiento_plazos = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        verbose_name="Cumplimiento de Plazos"
    )
    atencion_cliente = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        verbose_name="Atención al Cliente"
    )
    precios_competitivos = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        verbose_name="Precios Competitivos"
    )
    resolucion_problemas = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        verbose_name="Resolución de Problemas"
    )
    
    # Calificación general
    calificacion_general = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        verbose_name="Calificación General"
    )
    
    # Comentarios
    fortalezas = models.TextField(blank=True, verbose_name="Fortalezas")
    areas_mejora = models.TextField(blank=True, verbose_name="Áreas de Mejora")
    comentarios_generales = models.TextField(blank=True, verbose_name="Comentarios Generales")
    
    # Recomendaciones
    recomendacion = models.CharField(
        max_length=20,
        choices=[
            ('mantener', 'Mantener Relación'),
            ('mejorar', 'Necesita Mejorar'),
            ('revisar', 'Revisar Relación'),
            ('terminar', 'Terminar Relación'),
        ],
        default='mantener',
        verbose_name="Recomendación"
    )
    
    # Auditoría
    evaluado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Evaluación de Proveedor"
        verbose_name_plural = "Evaluaciones de Proveedores"
        ordering = ['-fecha_evaluacion']
    
    def __str__(self):
        return f"{self.proveedor.nombre} - {self.periodo_evaluado}"
    
    def save(self, *args, **kwargs):
        """Calcula la calificación general al guardar"""
        suma = (
            self.calidad_productos + 
            self.cumplimiento_plazos + 
            self.atencion_cliente + 
            self.precios_competitivos + 
            self.resolucion_problemas
        )
        self.calificacion_general = round(suma / 5, 2)
        super().save(*args, **kwargs)
    
    def get_calificacion_general_color(self):
        """Retorna el color CSS para la calificación general"""
        if self.calificacion_general >= 4.5:
            return 'success'
        elif self.calificacion_general >= 3.5:
            return 'info'
        elif self.calificacion_general >= 2.5:
            return 'warning'
        else:
            return 'danger'
