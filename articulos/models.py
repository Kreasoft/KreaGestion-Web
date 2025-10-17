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
        """Retorna el porcentaje como Decimal (dividido por 100)"""
        try:
            return Decimal(str(self.porcentaje).replace(',', '.')) / Decimal('100')
        except:
            return Decimal('0.00')


class CategoriaArticulo(models.Model):
    """Categorías para clasificar los artículos"""
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    codigo = models.CharField(max_length=50, blank=True, verbose_name="Código")
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
        unique_together = ['empresa', 'codigo']
    
    def __str__(self):
        # Mostrar código y nombre si existe código, sino solo nombre
        if self.codigo:
            return f"{self.codigo} - {self.nombre}"
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
    codigo = models.CharField(max_length=50, verbose_name="Código")
    codigo_barras = models.CharField(max_length=50, blank=True, null=True, verbose_name="Código de Barras")
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
        blank=True,
        null=True,
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
        unique_together = [
            ('empresa', 'codigo'),
            ('empresa', 'codigo_barras'),
        ]
    
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
        """Calcula el precio final con IVA e impuesto específico de la categoría"""
        precio_venta = self._string_to_decimal(self.precio_venta)
        
        if precio_venta <= 0:
            return Decimal('0.00')
        
        # Obtener configuración de IVA de la categoría
        iva_porcentaje = self.categoria.get_iva_porcentaje()
        
        # Calcular IVA
        iva_monto = (precio_venta * iva_porcentaje) / Decimal('100.00')
        
        # Obtener impuesto específico de la categoría
        impuesto_especifico_decimal = Decimal('0.00')
        if self.categoria and self.categoria.impuesto_especifico:
            impuesto_especifico_decimal = self.categoria.impuesto_especifico.get_porcentaje_decimal()
        
        # Calcular impuesto específico
        impuesto_especifico_monto = precio_venta * impuesto_especifico_decimal
        
        # Precio final = Precio venta + IVA + Impuesto Específico
        precio_final_calculado = precio_venta + iva_monto + impuesto_especifico_monto
        self.precio_final = str(precio_final_calculado)
        
        return precio_final_calculado
    
    def calcular_precio_venta_desde_final(self):
        """Calcula el precio de venta desde el precio final considerando IVA e impuesto específico de la categoría"""
        precio_final = self._string_to_decimal(self.precio_final)
        
        if precio_final <= 0:
            return Decimal('0.00')
        
        # Obtener configuración de impuestos de la categoría
        iva_porcentaje = self.categoria.get_iva_porcentaje()
        
        # Obtener impuesto específico de la categoría
        impuesto_especifico_decimal = Decimal('0.00')
        if self.categoria and self.categoria.impuesto_especifico:
            impuesto_especifico_decimal = self.categoria.impuesto_especifico.get_porcentaje_decimal()
        
        # Calcular precio de venta descontando IVA e impuesto específico
        # Precio Final = Precio Venta * (1 + IVA% + Imp.Esp%)
        # Precio Venta = Precio Final / (1 + IVA% + Imp.Esp%)
        factor_total = Decimal('1.00') + (iva_porcentaje / Decimal('100.00')) + impuesto_especifico_decimal
        precio_venta_calculado = precio_final / factor_total
        self.precio_venta = str(precio_venta_calculado)
        
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
        """Guarda el artículo sin cálculos automáticos"""
        # Los precios se manejan manualmente en el formulario
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
    
    @property
    def stock_actual(self):
        """Retorna el stock actual del artículo (suma de todas las bodegas)"""
        try:
            from inventario.models import Stock
            # Obtener el stock total de todas las bodegas
            stocks = Stock.objects.filter(articulo=self, empresa=self.empresa)
            total_stock = sum(float(stock.cantidad) for stock in stocks)
            return int(total_stock)
        except Exception as e:
            print(f"DEBUG - Error calculando stock para artículo {self.id}: {e}")
            return 0
    
    @property
    def stock_disponible(self):
        """Alias de stock_actual para compatibilidad"""
        return self.stock_actual


class ListaPrecio(models.Model):
    """Listas de precios para artículos"""
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la Lista")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    activa = models.BooleanField(default=True, verbose_name="Activa")
    es_predeterminada = models.BooleanField(default=False, verbose_name="Lista Predeterminada")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")
    
    class Meta:
        verbose_name = "Lista de Precios"
        verbose_name_plural = "Listas de Precios"
        unique_together = ['empresa', 'nombre']
        ordering = ['-es_predeterminada', 'nombre']
    
    def __str__(self):
        return f"{self.nombre}{' (Predeterminada)' if self.es_predeterminada else ''}"
    
    def save(self, *args, **kwargs):
        # Si se marca como predeterminada, desmarcar las demás
        if self.es_predeterminada:
            ListaPrecio.objects.filter(empresa=self.empresa, es_predeterminada=True).exclude(pk=self.pk).update(es_predeterminada=False)
        super().save(*args, **kwargs)


class PrecioArticulo(models.Model):
    """Precios de artículos en diferentes listas"""
    
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, related_name='precios', verbose_name="Artículo")
    lista_precio = models.ForeignKey(ListaPrecio, on_delete=models.CASCADE, related_name='precios', verbose_name="Lista de Precios")
    precio = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Precio"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")
    
    class Meta:
        verbose_name = "Precio de Artículo"
        verbose_name_plural = "Precios de Artículos"
        unique_together = ['articulo', 'lista_precio']
        ordering = ['lista_precio', 'articulo']
    
    def __str__(self):
        return f"{self.articulo.nombre} - {self.lista_precio.nombre}: ${self.precio}"


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


class HomologacionCodigo(models.Model):
    """Códigos alternativos de artículos según proveedor"""
    
    articulo = models.ForeignKey(
        'Articulo',
        on_delete=models.CASCADE,
        related_name='homologaciones',
        verbose_name="Artículo"
    )
    proveedor = models.ForeignKey(
        'proveedores.Proveedor',
        on_delete=models.CASCADE,
        verbose_name="Proveedor"
    )
    codigo_proveedor = models.CharField(
        max_length=100,
        verbose_name="Código del Proveedor"
    )
    descripcion_proveedor = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Descripción del Proveedor"
    )
    precio_compra = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Precio de Compra",
        help_text="Último precio de compra a este proveedor"
    )
    es_principal = models.BooleanField(
        default=False,
        verbose_name="Proveedor Principal"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name="Observaciones"
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
        verbose_name = "Homologación de Código"
        verbose_name_plural = "Homologaciones de Códigos"
        unique_together = ['articulo', 'proveedor', 'codigo_proveedor']
        ordering = ['-es_principal', 'proveedor__nombre']
    
    def __str__(self):
        return f"{self.articulo.codigo} → {self.proveedor.nombre}: {self.codigo_proveedor}"