from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from empresas.models import Empresa
from decimal import Decimal


class ConfiguracionAlertaFolios(models.Model):
    """Configuración de alertas de folios por tipo de documento"""
    
    TIPO_DOCUMENTO_CHOICES = [
        ('33', 'Factura Electrónica'),
        ('34', 'Factura Exenta Electrónica'),
        ('39', 'Boleta Electrónica'),
        ('41', 'Boleta Exenta Electrónica'),
        ('52', 'Guía de Despacho Electrónica'),
        ('56', 'Nota de Débito Electrónica'),
        ('61', 'Nota de Crédito Electrónica'),
    ]
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='alertas_folios',
        verbose_name="Empresa"
    )
    tipo_documento = models.CharField(
        max_length=10,
        choices=TIPO_DOCUMENTO_CHOICES,
        verbose_name="Tipo de Documento"
    )
    folios_minimos = models.IntegerField(
        default=20,
        verbose_name="Folios Mínimos para Alerta",
        help_text="Cantidad de folios restantes para activar alerta"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Alerta Activa"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuración de Alerta de Folios"
        verbose_name_plural = "Configuraciones de Alertas de Folios"
        unique_together = ['empresa', 'tipo_documento']
        ordering = ['tipo_documento']
    
    def __str__(self):
        return f"{self.empresa.nombre} - {self.get_tipo_documento_display()} ({self.folios_minimos} folios)"


class ArchivoCAF(models.Model):
    """Archivo CAF del SII para rangos de folios autorizados"""
    
    TIPO_DOCUMENTO_CHOICES = [
        ('33', 'Factura Electrónica'),
        ('34', 'Factura Exenta Electrónica'),
        ('39', 'Boleta Electrónica'),
        ('41', 'Boleta Exenta Electrónica'),
        ('52', 'Guía de Despacho Electrónica'),
        ('56', 'Nota de Débito Electrónica'),
        ('61', 'Nota de Crédito Electrónica'),
    ]
    
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('agotado', 'Agotado'),
        ('vencido', 'Vencido'),
        ('anulado', 'Anulado'),
    ]
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='archivos_caf',
        verbose_name="Empresa"
    )
    tipo_documento = models.CharField(
        max_length=10,
        choices=TIPO_DOCUMENTO_CHOICES,
        verbose_name="Tipo de Documento"
    )
    
    # RANGO DE FOLIOS
    folio_desde = models.IntegerField(verbose_name="Folio Desde")
    folio_hasta = models.IntegerField(verbose_name="Folio Hasta")
    cantidad_folios = models.IntegerField(verbose_name="Cantidad de Folios")
    
    # ARCHIVO CAF
    archivo_xml = models.FileField(
        upload_to='caf/',
        verbose_name="Archivo XML del CAF"
    )
    contenido_caf = models.TextField(
        verbose_name="Contenido XML del CAF"
    )
    
    # DATOS DEL CAF
    fecha_autorizacion = models.DateField(verbose_name="Fecha de Autorización")
    firma_electronica = models.TextField(verbose_name="Firma Electrónica (FRMA)")
    
    # CONTROL DE USO
    folios_utilizados = models.IntegerField(
        default=0,
        verbose_name="Folios Utilizados"
    )
    folio_actual = models.IntegerField(verbose_name="Folio Actual")
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='activo',
        verbose_name="Estado"
    )
    
    # FECHAS
    fecha_carga = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Carga"
    )
    fecha_agotamiento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Agotamiento"
    )
    usuario_carga = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Usuario que Cargó"
    )
    
    class Meta:
        verbose_name = "Archivo CAF"
        verbose_name_plural = "Archivos CAF"
        ordering = ['-fecha_carga']
        unique_together = [['empresa', 'tipo_documento', 'folio_desde', 'folio_hasta']]
        indexes = [
            models.Index(fields=['empresa', 'tipo_documento', 'estado']),
            models.Index(fields=['folio_desde', 'folio_hasta']),
        ]
    
    def __str__(self):
        return f"CAF {self.get_tipo_documento_display()} ({self.folio_desde}-{self.folio_hasta})"
    
    def folios_disponibles(self):
        """Retorna la cantidad de folios disponibles"""
        return self.cantidad_folios - self.folios_utilizados
    
    def porcentaje_uso(self):
        """Retorna el porcentaje de uso del CAF"""
        if self.cantidad_folios == 0:
            return 0
        return (self.folios_utilizados / self.cantidad_folios) * 100
    
    def esta_vigente(self):
        """
        Verifica si el CAF está vigente (dentro de los 6 meses desde la autorización)
        Los CAF del SII tienen vigencia de 6 meses desde la fecha de autorización
        """
        from datetime import timedelta
        from django.utils import timezone
        
        if not self.fecha_autorizacion:
            return False
        
        fecha_vencimiento = self.fecha_autorizacion + timedelta(days=180)  # 6 meses = 180 días
        hoy = timezone.now().date()
        
        return hoy <= fecha_vencimiento
    
    def dias_para_vencer(self):
        """Retorna la cantidad de días que faltan para que venza el CAF"""
        from datetime import timedelta
        from django.utils import timezone
        
        if not self.fecha_autorizacion:
            return 0
        
        fecha_vencimiento = self.fecha_autorizacion + timedelta(days=180)
        hoy = timezone.now().date()
        
        if hoy > fecha_vencimiento:
            return 0  # Ya venció
        
        return (fecha_vencimiento - hoy).days
    
    def fecha_vencimiento(self):
        """Retorna la fecha de vencimiento del CAF"""
        from datetime import timedelta
        
        if not self.fecha_autorizacion:
            return None
        
        return self.fecha_autorizacion + timedelta(days=180)
    
    def verificar_vencimiento(self):
        """
        Verifica si el CAF ha vencido y actualiza su estado automáticamente
        Retorna True si está vigente, False si venció
        """
        if not self.esta_vigente() and self.estado == 'activo':
            self.estado = 'vencido'
            self.save()
            return False
        return True
    
    def obtener_siguiente_folio(self):
        """Obtiene el siguiente folio disponible y actualiza el contador"""
        if self.estado != 'activo':
            raise ValueError(f"CAF no está activo (Estado: {self.estado})")
        
        if self.folios_utilizados >= self.cantidad_folios:
            self.estado = 'agotado'
            self.fecha_agotamiento = timezone.now()
            self.save()
            raise ValueError("CAF agotado")
        
        siguiente = self.folio_actual + 1
        
        if siguiente > self.folio_hasta:
            raise ValueError("Folio fuera de rango")
        
        self.folio_actual = siguiente
        self.folios_utilizados += 1
        
        if self.folios_utilizados >= self.cantidad_folios:
            self.estado = 'agotado'
            self.fecha_agotamiento = timezone.now()
        
        self.save()
        return siguiente
    
    def resetear_folios(self):
        """Resetea el CAF para reutilizar los folios (SOLO PARA PRUEBAS)"""
        self.folio_actual = self.folio_desde - 1
        self.folios_utilizados = 0
        self.estado = 'activo'
        self.fecha_agotamiento = None
        self.save()
        return True


class DocumentoTributarioElectronico(models.Model):
    """Registro de todos los DTE emitidos"""
    
    TIPO_DTE_CHOICES = [
        ('33', 'Factura Electrónica'),
        ('34', 'Factura Exenta Electrónica'),
        ('39', 'Boleta Electrónica'),
        ('41', 'Boleta Exenta Electrónica'),
        ('52', 'Guía de Despacho Electrónica'),
        ('56', 'Nota de Débito Electrónica'),
        ('61', 'Nota de Crédito Electrónica'),
    ]
    
    ESTADO_CHOICES = [
        ('generado', 'Generado'),
        ('firmado', 'Firmado'),
        ('enviado', 'Enviado al SII'),
        ('aceptado', 'Aceptado por SII'),
        ('rechazado', 'Rechazado por SII'),
        ('anulado', 'Anulado'),
    ]
    
    # Tipos de traslado para Guías de Despacho (SII)
    TIPO_TRASLADO_CHOICES = [
        ('1', 'Venta'),
        ('2', 'Venta por efectuar (anticipada)'),
        ('3', 'Consignación'),
        ('4', 'Devolución'),
        ('5', 'Traslado interno'),
        ('6', 'Transformación de productos'),
        ('7', 'Entrega gratuita'),
        ('8', 'Otros'),
    ]
    
    # RELACIONES
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name='dtes',
        verbose_name="Empresa"
    )
    venta = models.OneToOneField(
        'ventas.Venta',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='dte',
        verbose_name="Venta Asociada"
    )
    caf_utilizado = models.ForeignKey(
        ArchivoCAF,
        on_delete=models.PROTECT,
        related_name='dtes',
        verbose_name="CAF Utilizado"
    )
    
    # IDENTIFICACIÓN DEL DOCUMENTO
    tipo_dte = models.CharField(
        max_length=10,
        choices=TIPO_DTE_CHOICES,
        verbose_name="Tipo DTE"
    )
    folio = models.IntegerField(verbose_name="Folio")
    fecha_emision = models.DateField(verbose_name="Fecha de Emisión")
    
    # EMISOR
    rut_emisor = models.CharField(max_length=12, verbose_name="RUT Emisor", default='')
    razon_social_emisor = models.CharField(max_length=200, verbose_name="Razón Social Emisor", default='')
    giro_emisor = models.CharField(max_length=200, blank=True, verbose_name="Giro Emisor")
    direccion_emisor = models.CharField(max_length=200, blank=True, verbose_name="Dirección Emisor")
    comuna_emisor = models.CharField(max_length=100, blank=True, verbose_name="Comuna Emisor")
    
    # RECEPTOR
    rut_receptor = models.CharField(max_length=12, verbose_name="RUT Receptor")
    razon_social_receptor = models.CharField(max_length=200, verbose_name="Razón Social Receptor")
    giro_receptor = models.CharField(max_length=200, blank=True, verbose_name="Giro Receptor")
    direccion_receptor = models.CharField(max_length=200, blank=True, verbose_name="Dirección Receptor")
    comuna_receptor = models.CharField(max_length=100, blank=True, verbose_name="Comuna Receptor")
    ciudad_receptor = models.CharField(max_length=100, blank=True, verbose_name="Ciudad Receptor")
    
    # MONTOS
    monto_neto = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Monto Neto")
    monto_exento = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Monto Exento")
    monto_iva = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Monto IVA")
    monto_total = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Monto Total")
    
    # XML Y FIRMA
    xml_dte = models.TextField(blank=True, verbose_name="XML del DTE")
    xml_firmado = models.TextField(blank=True, verbose_name="XML Firmado")
    timbre_electronico = models.TextField(blank=True, verbose_name="Timbre Electrónico (TED)")

    # TIMBRE PDF417
    timbre_pdf417 = models.ImageField(
        upload_to='dte/timbres/',
        blank=True,
        null=True,
        verbose_name="Timbre PDF417"
    )
    
    # ESTADO SII
    estado_sii = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='generado',
        verbose_name="Estado SII"
    )
    track_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Track ID SII"
    )
    fecha_envio_sii = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha Envío al SII"
    )
    fecha_respuesta_sii = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha Respuesta SII"
    )
    glosa_sii = models.TextField(
        blank=True,
        verbose_name="Respuesta del SII"
    )
    respuesta_sii = models.TextField(
        blank=True,
        verbose_name="Respuesta Completa del SII"
    )
    error_envio = models.TextField(
        blank=True,
        verbose_name="Error en Envío"
    )
    fecha_consulta_estado = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha Última Consulta Estado"
    )
    datos_pdf417 = models.TextField(
        blank=True,
        verbose_name="Datos para PDF417"
    )
    
    # TIPO DE TRASLADO (Solo para Guías de Despacho - Tipo 52)
    tipo_traslado = models.CharField(
        max_length=2,
        choices=TIPO_TRASLADO_CHOICES,
        blank=True,
        null=True,
        verbose_name="Tipo de Traslado",
        help_text="Motivo de emisión de la guía (solo para tipo 52)"
    )
    
    # PDF
    pdf_documento = models.FileField(
        upload_to='dte_pdf/',
        null=True,
        blank=True,
        verbose_name="PDF del Documento"
    )
    
    # REFERENCIAS (Para NC, ND)
    documento_referencia = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_relacionados',
        verbose_name="Documento de Referencia"
    )
    
    # AUDITORÍA
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    usuario_creacion = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Usuario Creación"
    )
    
    class Meta:
        verbose_name = "Documento Tributario Electrónico"
        verbose_name_plural = "Documentos Tributarios Electrónicos"
        ordering = ['-fecha_emision', '-folio']
        unique_together = [['empresa', 'tipo_dte', 'folio']]
        indexes = [
            models.Index(fields=['empresa', 'tipo_dte', 'folio']),
            models.Index(fields=['estado_sii']),
            models.Index(fields=['fecha_emision']),
            models.Index(fields=['rut_receptor']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_dte_display()} Folio {self.folio}"


class EnvioDTE(models.Model):
    """Control de envíos masivos de DTE al SII"""
    
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('enviando', 'Enviando'),
        ('enviado', 'Enviado'),
        ('aceptado', 'Aceptado'),
        ('rechazado', 'Rechazado'),
        ('error', 'Error'),
    ]
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name='envios_dte',
        verbose_name="Empresa"
    )
    
    # SET DE DOCUMENTOS
    documentos = models.ManyToManyField(
        DocumentoTributarioElectronico,
        related_name='envios',
        verbose_name="Documentos"
    )
    cantidad_documentos = models.IntegerField(verbose_name="Cantidad de Documentos")
    
    # ENVÍO
    xml_envio = models.TextField(verbose_name="XML del Envío (SetDTE)")
    fecha_envio = models.DateTimeField(verbose_name="Fecha de Envío")
    track_id = models.CharField(max_length=50, blank=True, verbose_name="Track ID")
    
    # RESPUESTA
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name="Estado"
    )
    xml_respuesta = models.TextField(blank=True, verbose_name="XML de Respuesta")
    fecha_respuesta = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Respuesta")
    glosa_respuesta = models.TextField(blank=True, verbose_name="Glosa de Respuesta")
    
    # AUDITORÍA
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    
    class Meta:
        verbose_name = "Envío de DTE"
        verbose_name_plural = "Envíos de DTE"
        ordering = ['-fecha_envio']
    
    def __str__(self):
        return f"Envío {self.id} - {self.cantidad_documentos} documentos"


class AcuseRecibo(models.Model):
    """Acuses de recibo de clientes"""
    
    TIPO_ACUSE_CHOICES = [
        ('comercial', 'Acuse Comercial'),
        ('recibo', 'Acuse de Recibo'),
        ('reclamo', 'Reclamo'),
        ('aceptacion', 'Aceptación Contenido'),
    ]
    
    dte = models.ForeignKey(
        DocumentoTributarioElectronico,
        on_delete=models.CASCADE,
        related_name='acuses',
        verbose_name="DTE"
    )
    tipo_acuse = models.CharField(
        max_length=50,
        choices=TIPO_ACUSE_CHOICES,
        verbose_name="Tipo de Acuse"
    )
    xml_acuse = models.TextField(verbose_name="XML del Acuse")
    fecha_recepcion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Recepción")
    procesado = models.BooleanField(default=False, verbose_name="Procesado")
    
    class Meta:
        verbose_name = "Acuse de Recibo"
        verbose_name_plural = "Acuses de Recibo"
        ordering = ['-fecha_recepcion']
    
    def __str__(self):
        return f"{self.get_tipo_acuse_display()} - DTE {self.dte.folio}"
