from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from empresas.models import Empresa, Sucursal


class ImpuestoEspecifico(models.Model):
    """Impuestos específicos que se pueden aplicar a categorías"""
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    porcentaje = models.CharField(max_length=50, default='0.00', verbose_name="Porcentaje (%)")
    activa = models.BooleanField(default=True, verbose_name="Activa")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    
    class Meta:
        verbose_name = "Impuesto Específico"
        verbose_name_plural = "Impuestos Específicos"
        unique_together = ['empresa', 'nombre']
    
    def __str__(self):
        return f"{self.nombre} ({self.porcentaje}%)"
    
    def get_porcentaje_decimal(self):
        """Retorna el porcentaje como Decimal"""
        try:
            return Decimal(str(self.porcentaje).replace(',', '.'))
        except:
            return Decimal('0.00')


class CategoriaArticulo(models.Model):
    """Categorías para clasificar los artículos"""
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    
    # Configuración de impuestos por categoría
    exenta_iva = models.BooleanField(default=False, verbose_name="Exenta de IVA")
    impuesto_especifico = models.ForeignKey(
        ImpuestoEspecifico, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Impuesto Específico"
    )
    
    activa = models.BooleanField(default=True, verbose_name="Activa")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    
    class Meta:
        verbose_name = "Categoría de Artículo"
        verbose_name_plural = "Categorías de Artículos"
        unique_together = ['empresa', 'nombre']
    
    def __str__(self):
        return self.nombre
    
    def get_iva_porcentaje(self):
        """Retorna el porcentaje de IVA (0% si está exenta)"""
        if self.exenta_iva:
            return Decimal('0.00')
        return Decimal('19.00')  # IVA estándar en Chile
    
    def get_impuesto_especifico_porcentaje(self):
        """Retorna el porcentaje de impuesto específico"""
        if self.impuesto_especifico:
            return self.impuesto_especifico.get_porcentaje_decimal()
        return Decimal('0.00')


class UnidadMedida(models.Model):
    """Unidades de medida para los artículos"""
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    nombre = models.CharField(max_length=50, verbose_name="Nombre")
    simbolo = models.CharField(max_length=10, verbose_name="Símbolo")
    activa = models.BooleanField(default=True, verbose_name="Activa")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    
    class Meta:
        verbose_name = "Unidad de Medida"
        verbose_name_plural = "Unidades de Medida"
        unique_together = ['empresa', 'nombre']
    
    def __str__(self):
        return f"{self.nombre} ({self.simbolo})"


class Articulo(models.Model):
    """Modelo principal para los artículos"""
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    categoria = models.ForeignKey(CategoriaArticulo, on_delete=models.PROTECT, verbose_name="Categoría")
    unidad_medida = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT, verbose_name="Unidad de Medida")
    
    # Información básica
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código")
    codigo_barras = models.CharField(max_length=50, blank=True, null=True, unique=True, verbose_name="Código de Barras")
    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    logo = models.ImageField(upload_to='articulos/logos/', blank=True, null=True, verbose_name="Logo del Artículo")
    
    # Precios
    precio_costo = models.CharField(
        max_length=50, 
        default='0.00',
        verbose_name="Precio de Costo"
    )
    precio_venta = models.CharField(
        max_length=50, 
        default='0.00',
        verbose_name="Precio de Venta"
    )
    precio_final = models.CharField(
        max_length=50, 
        default='0.00',
        verbose_name="Precio Final"
    )
    
    # Margen de ganancia
    margen_porcentaje = models.CharField(
        max_length=50, 
        default='30.00',
        verbose_name="Margen de Ganancia (%)"
    )
    
    # Impuesto específico
    impuesto_especifico = models.CharField(
        max_length=50, 
        default='0.00',
        verbose_name="Impuesto Específico"
    )
    
    # Control de stock
    control_stock = models.BooleanField(default=True, verbose_name="Control de Stock")
    stock_minimo = models.CharField(
        max_length=50, 
        default='0.00',
        verbose_name="Stock Mínimo"
    )
    stock_maximo = models.CharField(
        max_length=50, 
        default='0.00',
        verbose_name="Stock Máximo"
    )
    
    # Tipo de artículo para producción
    TIPO_ARTICULO_CHOICES = [
        ('producto_venta', 'Producto de Venta'),
        ('insumo', 'Insumo'),
        ('ambos', 'Producto e Insumo'),
    ]
    tipo_articulo = models.CharField(
        max_length=20,
        choices=TIPO_ARTICULO_CHOICES,
        default='producto_venta',
        verbose_name="Tipo de Artículo"
    )
    
    # Estado
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")
    
    class Meta:
        verbose_name = "Artículo"
        verbose_name_plural = "Artículos"
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    def get_tipo_articulo_display(self):
        """Retorna el tipo de artículo formateado"""
        return dict(self.TIPO_ARTICULO_CHOICES).get(self.tipo_articulo, 'Desconocido')
    
    def es_producto_venta(self):
        """Retorna True si el artículo es un producto de venta"""
        return self.tipo_articulo in ['producto_venta', 'ambos']
    
    def es_insumo(self):
        """Retorna True si el artículo es un insumo"""
        return self.tipo_articulo in ['insumo', 'ambos']
    
    def calcular_precio_final(self):
        """Calcula el precio final con IVA de la categoría"""
        precio_venta = self._string_to_decimal(self.precio_venta)
        
        if precio_venta <= 0:
            return Decimal('0.00')
        
        # Obtener configuración de IVA de la categoría
        iva_porcentaje = self.categoria.get_iva_porcentaje()
        
        # Calcular IVA
        iva_monto = (precio_venta * iva_porcentaje) / Decimal('100.00')
        
        # Precio final = Precio venta + IVA
        precio_final_calculado = precio_venta + iva_monto
        self.precio_final = str(precio_final_calculado)
        
        return precio_final_calculado
    
    def calcular_precio_venta_desde_final(self):
        """Calcula el precio de venta desde el precio final considerando impuestos de la categoría"""
        precio_final = self._string_to_decimal(self.precio_final)
        
        if precio_final <= 0:
            return Decimal('0.00')
        
        # Obtener configuración de impuestos de la categoría
        iva_porcentaje = self.categoria.get_iva_porcentaje()
        
        # Calcular precio de venta descontando IVA
        if iva_porcentaje > 0:
            factor_iva = Decimal('100.00') / (Decimal('100.00') + iva_porcentaje)
            precio_venta_calculado = precio_final * factor_iva
            self.precio_venta = str(precio_venta_calculado)
        else:
            self.precio_venta = str(precio_final)
        
        return precio_final
    
    def calcular_precio_venta_desde_costo(self):
        """Calcula el precio de venta desde el costo y margen"""
        precio_costo = self._string_to_decimal(self.precio_costo)
        margen_porcentaje = self._string_to_decimal(self.margen_porcentaje)
        
        if precio_costo > 0:
            precio_venta_calculado = precio_costo * (1 + margen_porcentaje / 100)
            self.precio_venta = str(precio_venta_calculado)
            return precio_venta_calculado
        return Decimal('0.00')
    
    def save(self, *args, **kwargs):
        """Calcula automáticamente los precios al guardar"""
        # Convertir strings a decimales para cálculos
        try:
            precio_costo = self._string_to_decimal(self.precio_costo)
            margen_porcentaje = self._string_to_decimal(self.margen_porcentaje)
            precio_venta = self._string_to_decimal(self.precio_venta)
            
            # Si se modificó el precio de costo o margen, calcular precio de venta
            if precio_costo > 0 and margen_porcentaje > 0:
                precio_venta_calculado = precio_costo * (1 + margen_porcentaje / 100)
                self.precio_venta = str(precio_venta_calculado)
                precio_venta = precio_venta_calculado
            
            # Calcular precio final usando el precio de venta correcto
            if precio_venta > 0:
                precio_final_calculado = precio_venta * Decimal('1.19')
                self.precio_final = str(int(precio_final_calculado))
                
        except Exception:
            # Si hay error en los cálculos, continuar sin modificar
            pass
        
        super().save(*args, **kwargs)
    
    def _string_to_decimal(self, value):
        """Convierte string a Decimal manejando formato chileno"""
        if not value:
            return Decimal('0')
        
        try:
            # Convertir formato chileno a decimal
            value_str = str(value).replace('.', '').replace(',', '.')
            return Decimal(value_str)
        except:
            return Decimal('0')


class StockArticulo(models.Model):
    """Stock de artículos por sucursal"""
    
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, related_name='stock_articulos', verbose_name="Artículo")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, verbose_name="Sucursal")
    cantidad_disponible = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Cantidad Disponible"
    )
    cantidad_reservada = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Cantidad Reservada"
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")
    
    class Meta:
        verbose_name = "Stock de Artículo"
        verbose_name_plural = "Stocks de Artículos"
        unique_together = ['articulo', 'sucursal']
    
    def __str__(self):
        return f"{self.articulo.nombre} - {self.sucursal.nombre}: {self.cantidad_disponible}"
    
    @property
    def cantidad_total(self):
        """Cantidad total (disponible + reservada)"""
        return self.cantidad_disponible + self.cantidad_reservada