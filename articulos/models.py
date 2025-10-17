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
    
    # Configuración de producción
    TIPO_PRODUCCION_CHOICES = [
        ('textil', 'Textil'),
        ('carnico', 'Cárnico'),
        ('panaderia', 'Panadería'),
        ('quimico', 'Químico'),
        ('otro', 'Otro'),
    ]
    tipo_produccion = models.CharField(
        max_length=20,
        choices=TIPO_PRODUCCION_CHOICES,
        null=True,
        blank=True,
        verbose_name="Tipo de Producción",
        help_text="Industria a la que pertenece este producto"
    )
    
    # Unidad de medida para producción
    UNIDAD_PRODUCCION_CHOICES = [
        ('unidad', 'Unidades'),
        ('kg', 'Kilogramos'),
        ('gramos', 'Gramos'),
        ('litros', 'Litros'),
        ('ml', 'Mililitros'),
        ('metros', 'Metros'),
        ('cm', 'Centímetros'),
    ]
    unidad_produccion = models.CharField(
        max_length=20,
        choices=UNIDAD_PRODUCCION_CHOICES,
        default='unidad',
        verbose_name="Unidad de Producción",
        help_text="Unidad en la que se produce este artículo"
    )
    
    # Configuración específica por industria
    requiere_lote = models.BooleanField(
        default=False,
        verbose_name="Requiere Número de Lote",
        help_text="Marcar si el producto requiere control de lotes"
    )
    
    tiene_vencimiento = models.BooleanField(
        default=False,
        verbose_name="Tiene Fecha de Vencimiento",
        help_text="Marcar si el producto tiene fecha de vencimiento"
    )
    
    dias_vencimiento = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Días hasta Vencimiento",
        help_text="Días de vida útil del producto desde su producción"
    )
    
    tiene_variantes = models.BooleanField(
        default=False,
        verbose_name="Tiene Variantes",
        help_text="Marcar si el producto tiene variantes (tallas, colores, etc.)"
    )
    
    temperatura_almacenamiento = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Temperatura de Almacenamiento (°C)",
        help_text="Temperatura requerida para almacenar el producto"
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


class KitOferta(models.Model):
    """Kits de ofertas - combos de artículos con precio especial"""
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        verbose_name="Empresa"
    )
    codigo = models.CharField(
        max_length=50,
        verbose_name="Código del Kit"
    )
    nombre = models.CharField(
        max_length=200,
        verbose_name="Nombre del Kit"
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción"
    )
    imagen = models.ImageField(
        upload_to='kits/',
        blank=True,
        null=True,
        verbose_name="Imagen del Kit"
    )
    precio_kit = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Precio del Kit",
        help_text="Precio especial del kit completo"
    )
    descuento_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Descuento %",
        help_text="Porcentaje de descuento aplicado"
    )
    fecha_inicio = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Inicio",
        help_text="Fecha desde la cual el kit está disponible"
    )
    fecha_fin = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Fin",
        help_text="Fecha hasta la cual el kit está disponible"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    destacado = models.BooleanField(
        default=False,
        verbose_name="Destacado",
        help_text="Mostrar el kit en posición destacada"
    )
    stock_disponible = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Stock Disponible",
        help_text="Cantidad de kits disponibles"
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
        verbose_name = "Kit de Oferta"
        verbose_name_plural = "Kits de Ofertas"
        unique_together = ['empresa', 'codigo']
        ordering = ['-destacado', '-fecha_creacion']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    @property
    def precio_total_items(self):
        """Calcula el precio total de los items individuales"""
        total = Decimal('0.00')
        for item in self.items.all():
            # Convertir precio_final string a Decimal
            precio_final = Decimal(item.articulo.precio_final.replace(',', '')) if item.articulo.precio_final else Decimal('0.00')
            total += precio_final * item.cantidad
        return int(total)
    
    @property
    def ahorro(self):
        """Calcula el ahorro del kit vs precio individual"""
        return self.precio_total_items - self.precio_kit
    
    @property
    def ahorro_porcentaje(self):
        """Calcula el porcentaje de ahorro"""
        if self.precio_total_items > 0:
            return ((self.precio_total_items - self.precio_kit) / self.precio_total_items) * 100
        return 0
    
    @property
    def esta_vigente(self):
        """Verifica si el kit está dentro del período de vigencia"""
        hoy = timezone.now().date()
        if self.fecha_inicio and hoy < self.fecha_inicio:
            return False
        if self.fecha_fin and hoy > self.fecha_fin:
            return False
        return True
    
    @property
    def esta_disponible(self):
        """Verifica si el kit está disponible para venta"""
        return self.activo and self.esta_vigente and self.stock_disponible > 0


class KitOfertaItem(models.Model):
    """Items que componen un kit de oferta"""
    
    kit = models.ForeignKey(
        KitOferta,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Kit de Oferta"
    )
    articulo = models.ForeignKey(
        Articulo,
        on_delete=models.CASCADE,
        verbose_name="Artículo"
    )
    cantidad = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Cantidad"
    )
    orden = models.IntegerField(
        default=0,
        verbose_name="Orden",
        help_text="Orden de visualización del item"
    )
    observaciones = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Observaciones"
    )
    
    class Meta:
        verbose_name = "Item de Kit"
        verbose_name_plural = "Items de Kit"
        ordering = ['orden', 'id']
        unique_together = ['kit', 'articulo']
    
    def __str__(self):
        return f"{self.kit.codigo} - {self.articulo.codigo} x{self.cantidad}"
    
    @property
    def subtotal(self):
        """Calcula el subtotal del item"""
        precio_final = Decimal(self.articulo.precio_final.replace(',', '')) if self.articulo.precio_final else Decimal('0.00')
        return int(precio_final * self.cantidad)


# ==================== MODELOS DE PRODUCCIÓN ====================

class RecetaProduccion(models.Model):
    """Receta o fórmula para producir un artículo"""
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    codigo = models.CharField(max_length=50, verbose_name="Código")
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la Receta")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    
    # Producto que se va a producir
    producto_final = models.ForeignKey(
        Articulo,
        on_delete=models.PROTECT,
        related_name='recetas',
        verbose_name="Producto Final",
        limit_choices_to={'tipo_articulo__in': ['producto_venta', 'ambos']}
    )
    
    # Cantidad que produce esta receta
    cantidad_producir = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Cantidad a Producir",
        help_text="Cantidad que produce esta receta"
    )
    
    # Merma estimada
    merma_estimada = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Merma Estimada (%)",
        help_text="Porcentaje de merma estimado en el proceso"
    )
    
    # Tiempo de producción
    tiempo_estimado = models.IntegerField(
        verbose_name="Tiempo Estimado (minutos)",
        help_text="Tiempo estimado de producción en minutos"
    )
    
    # Campos específicos por industria
    temperatura_proceso = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Temperatura de Proceso (°C)",
        help_text="Temperatura requerida para el proceso (cárnico/químico)"
    )
    
    # Estado
    activo = models.BooleanField(default=True, verbose_name="Activa")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")
    
    class Meta:
        verbose_name = "Receta de Producción"
        verbose_name_plural = "Recetas de Producción"
        ordering = ['codigo']
        unique_together = ['empresa', 'codigo']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    @property
    def tipo_industria(self):
        """Retorna el tipo de industria del producto final"""
        return self.producto_final.tipo_produccion
    
    @property
    def unidad_medida(self):
        """Retorna la unidad de medida del producto final"""
        return self.producto_final.get_unidad_produccion_display()
    
    @property
    def costo_total_insumos(self):
        """Calcula el costo total de los insumos"""
        total = Decimal('0.00')
        for item in self.insumos.all():
            total += item.costo_total
        return total
    
    @property
    def costo_unitario(self):
        """Calcula el costo unitario del producto final"""
        if self.cantidad_producir > 0:
            return self.costo_total_insumos / self.cantidad_producir
        return Decimal('0.00')


class InsumoReceta(models.Model):
    """Insumos necesarios para una receta de producción"""
    
    receta = models.ForeignKey(
        RecetaProduccion,
        on_delete=models.CASCADE,
        related_name='insumos',
        verbose_name="Receta"
    )
    
    articulo = models.ForeignKey(
        Articulo,
        on_delete=models.PROTECT,
        verbose_name="Insumo",
        limit_choices_to={'tipo_articulo__in': ['insumo', 'ambos']}
    )
    
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Cantidad Necesaria"
    )
    
    orden = models.IntegerField(
        default=0,
        verbose_name="Orden",
        help_text="Orden en el que se agrega el insumo"
    )
    
    notas = models.TextField(
        blank=True,
        verbose_name="Notas",
        help_text="Notas sobre este insumo en la receta"
    )
    
    class Meta:
        verbose_name = "Insumo de Receta"
        verbose_name_plural = "Insumos de Receta"
        ordering = ['orden', 'id']
        unique_together = ['receta', 'articulo']
    
    def __str__(self):
        return f"{self.receta.codigo} - {self.articulo.codigo} x{self.cantidad}"
    
    @property
    def costo_unitario(self):
        """Retorna el costo unitario del insumo"""
        try:
            return Decimal(self.articulo.precio_costo.replace(',', '.'))
        except:
            return Decimal('0.00')
    
    @property
    def costo_total(self):
        """Calcula el costo total del insumo"""
        return self.costo_unitario * self.cantidad


class OrdenProduccion(models.Model):
    """Orden de producción para fabricar productos"""
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_proceso', 'En Proceso'),
        ('terminada', 'Terminada'),
        ('cancelada', 'Cancelada'),
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Empresa")
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, verbose_name="Sucursal")
    
    numero_orden = models.CharField(max_length=50, verbose_name="Número de Orden")
    receta = models.ForeignKey(
        RecetaProduccion,
        on_delete=models.PROTECT,
        verbose_name="Receta"
    )
    
    # Cantidades
    cantidad_planificada = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Cantidad Planificada"
    )
    
    cantidad_producida = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Cantidad Producida"
    )
    
    merma_real = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Merma Real"
    )
    
    # Fechas
    fecha_planificada = models.DateField(verbose_name="Fecha Planificada")
    fecha_inicio = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Inicio")
    fecha_fin = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Fin")
    
    # Estado
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name="Estado"
    )
    
    # Responsable
    responsable = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Responsable"
    )
    
    # Observaciones
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    
    # Campos específicos por industria
    lote_produccion = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Lote de Producción",
        help_text="Número de lote para trazabilidad (cárnico)"
    )
    
    fecha_vencimiento = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Vencimiento",
        help_text="Fecha de vencimiento del lote producido (cárnico)"
    )
    
    temperatura_proceso = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Temperatura de Proceso (°C)"
    )
    
    # Auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")
    
    class Meta:
        verbose_name = "Orden de Producción"
        verbose_name_plural = "Órdenes de Producción"
        ordering = ['-fecha_planificada', '-numero_orden']
        unique_together = ['empresa', 'numero_orden']
    
    def __str__(self):
        return f"OP-{self.numero_orden} - {self.receta.producto_final.nombre}"
    
    @property
    def porcentaje_completado(self):
        """Calcula el porcentaje de producción completado"""
        if self.cantidad_planificada > 0:
            return (self.cantidad_producida / self.cantidad_planificada) * 100
        return Decimal('0.00')
    
    @property
    def costo_total(self):
        """Calcula el costo total de la orden"""
        factor = self.cantidad_planificada / self.receta.cantidad_producir
        return self.receta.costo_total_insumos * factor