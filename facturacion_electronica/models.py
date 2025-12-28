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
    sucursal = models.ForeignKey(
        'empresas.Sucursal',
        on_delete=models.PROTECT,
        related_name='archivos_caf',
        verbose_name="Sucursal",
        help_text="Sucursal a la que pertenece este CAF"
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
    oculto = models.BooleanField(
        default=False,
        verbose_name="Oculto",
        help_text="Si está marcado, el CAF no se mostrará en listados principales"
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
        unique_together = [['empresa', 'sucursal', 'tipo_documento', 'folio_desde', 'folio_hasta']]
        indexes = [
            models.Index(fields=['empresa', 'sucursal', 'tipo_documento', 'estado']),
            models.Index(fields=['folio_desde', 'folio_hasta']),
            models.Index(fields=['sucursal', 'estado', 'oculto']),
        ]
    
    def __str__(self):
        sucursal_nombre = self.sucursal.nombre if self.sucursal else "Sin sucursal"
        return f"CAF {self.get_tipo_documento_display()} ({self.folio_desde}-{self.folio_hasta}) - {sucursal_nombre}"
    
    def validar_caf_unico(self):
        """
        Valida que el CAF no esté duplicado.
        
        Validaciones:
        1. El mismo contenido XML no puede cargarse dos veces (incluso en sucursales distintas)
        2. Los rangos de folios no pueden solaparse en la misma sucursal
        
        Returns:
            tuple: (es_valido: bool, mensaje_error: str)
        """
        import hashlib
        
        # 1. VALIDACIÓN: Mismo archivo CAF no puede cargarse dos veces
        # Generar hash del contenido del CAF (sin espacios ni saltos de línea para evitar diferencias triviales)
        contenido_limpio = ''.join(self.contenido_caf.split())
        hash_caf = hashlib.sha256(contenido_limpio.encode()).hexdigest()
        
        # Buscar otros CAFs con el mismo contenido
        cafs_duplicados = ArchivoCAF.objects.filter(
            empresa=self.empresa,
            tipo_documento=self.tipo_documento
        ).exclude(pk=self.pk)
        
        for caf_existente in cafs_duplicados:
            contenido_existente_limpio = ''.join(caf_existente.contenido_caf.split())
            hash_existente = hashlib.sha256(contenido_existente_limpio.encode()).hexdigest()
            
            if hash_caf == hash_existente:
                sucursal_existente = caf_existente.sucursal.nombre if caf_existente.sucursal else 'Sin sucursal'
                return (False, 
                    f"ESTE ARCHIVO CAF YA FUE CARGADO ANTERIORMENTE.\n\n"
                    f"Ya existe en:\n"
                    f"  - Sucursal: {sucursal_existente}\n"
                    f"  - Tipo: {caf_existente.get_tipo_documento_display()}\n"
                    f"  - Rango: {caf_existente.folio_desde}-{caf_existente.folio_hasta}\n"
                    f"  - Estado: {caf_existente.get_estado_display()}\n\n"
                    f"NO SE PUEDE CARGAR EL MISMO CAF EN MULTIPLES SUCURSALES.\n"
                    f"Cada sucursal debe tener sus propios CAFs con rangos exclusivos.")
        
        # 2. VALIDACIÓN: Rangos no pueden solaparse en la misma sucursal
        cafs_misma_sucursal = ArchivoCAF.objects.filter(
            empresa=self.empresa,
            sucursal=self.sucursal,
            tipo_documento=self.tipo_documento,
            estado__in=['activo', 'agotado']  # Solo verificar CAFs válidos
        ).exclude(pk=self.pk)
        
        for caf_existente in cafs_misma_sucursal:
            # Verificar si hay solapamiento de rangos
            # Solapamiento ocurre si:
            # - El inicio del nuevo CAF está dentro del rango existente, O
            # - El fin del nuevo CAF está dentro del rango existente, O
            # - El nuevo CAF contiene completamente al existente
            if (caf_existente.folio_desde <= self.folio_desde <= caf_existente.folio_hasta or
                caf_existente.folio_desde <= self.folio_hasta <= caf_existente.folio_hasta or
                (self.folio_desde <= caf_existente.folio_desde and self.folio_hasta >= caf_existente.folio_hasta)):
                
                return (False,
                    f"CONFLICTO DE RANGOS DE FOLIOS.\n\n"
                    f"El rango {self.folio_desde}-{self.folio_hasta} se solapa con un CAF existente:\n"
                    f"  - CAF ID: {caf_existente.id}\n"
                    f"  - Rango: {caf_existente.folio_desde}-{caf_existente.folio_hasta}\n"
                    f"  - Estado: {caf_existente.get_estado_display()}\n"
                    f"  - Sucursal: {caf_existente.sucursal.nombre}\n\n"
                    f"LOS RANGOS DE FOLIOS NO PUEDEN SOLAPARSE EN LA MISMA SUCURSAL.\n"
                    f"Solucion: Usar un rango diferente o anular el CAF anterior.")
        
        # 3. ADVERTENCIA: Rangos duplicados en sucursales distintas (permitido pero no recomendado)
        cafs_otras_sucursales = ArchivoCAF.objects.filter(
            empresa=self.empresa,
            tipo_documento=self.tipo_documento,
            folio_desde=self.folio_desde,
            folio_hasta=self.folio_hasta,
            estado__in=['activo', 'agotado']
        ).exclude(sucursal=self.sucursal).exclude(pk=self.pk)
        
        if cafs_otras_sucursales.exists():
            caf_otro = cafs_otras_sucursales.first()
            print(f"[ADVERTENCIA] El rango {self.folio_desde}-{self.folio_hasta} ya existe en otra sucursal ({caf_otro.sucursal.nombre})")
            print(f"             Esto es técnicamente permitido si son CAFs diferentes del SII, pero puede causar confusión.")
        
        return (True, "")
    
    def save(self, *args, **kwargs):
        """Override save para ejecutar validaciones antes de guardar"""
        # Ejecutar validaciones solo si es un CAF nuevo o si cambió el contenido
        if not self.pk or 'contenido_caf' in kwargs.get('update_fields', []):
            es_valido, mensaje_error = self.validar_caf_unico()
            if not es_valido:
                from django.core.exceptions import ValidationError
                raise ValidationError(mensaje_error)
        
        super().save(*args, **kwargs)
    
    def folios_disponibles(self):
        """Cantidad de folios disponibles calculada dinámicamente.
        Usa la diferencia entre folio_hasta y folio_actual para evitar falsos 0
        cuando folios_utilizados aún no refleja el consumo en curso."""
        return max(0, self.folio_hasta - self.folio_actual)
    
    def porcentaje_uso(self):
        """Retorna el porcentaje de uso del CAF"""
        if self.cantidad_folios == 0:
            return 0
        return (self.folios_utilizados / self.cantidad_folios) * 100
    
    # Propiedades cortas para templates
    @property
    def tipo_nombre(self):
        """Nombre corto del tipo de documento para templates"""
        return self.get_tipo_documento_display()
    
    @property
    def estado_nombre(self):
        """Nombre corto del estado para templates"""
        return self.get_estado_display()
    
    def esta_vigente(self):
        """
        Verifica si el CAF está vigente (dentro de los 6 meses desde la autorización)
        Los CAF del SII tienen vigencia de 6 meses desde la fecha de autorización
        """
        from datetime import date, timedelta
        
        if not self.fecha_autorizacion:
            return False
        
        fecha_vencimiento = self.fecha_autorizacion + timedelta(days=180)
        # Usar date.today() para comparar fechas 'naive' y evitar problemas de zona horaria
        return date.today() <= fecha_vencimiento
    
    def dias_para_vencer(self):
        """Retorna la cantidad de días que faltan para que venza el CAF"""
        from datetime import date, timedelta
        
        if not self.fecha_autorizacion:
            return 0
        
        fecha_vencimiento = self.fecha_autorizacion + timedelta(days=180)
        hoy = date.today() # Usar fecha local para evitar problemas de zona horaria
        
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
    
    @classmethod
    def obtener_caf_activo(cls, empresa, sucursal, tipo_documento):
        """
        Obtiene el CAF activo para una sucursal y tipo de documento específico.
        Retorna el CAF con folios disponibles, ordenado por folio_actual.
        """
        return cls.objects.filter(
            empresa=empresa,
            sucursal=sucursal,
            tipo_documento=tipo_documento,
            estado='activo',
            oculto=False
        ).order_by('folio_actual').first()
    
    @classmethod
    def ocultar_cafs_agotados(cls, empresa_id, sucursal_id=None):
        """
        Oculta todos los CAFs agotados o vencidos.
        Retorna la cantidad de CAFs ocultados.
        """
        filtro = {
            'empresa_id': empresa_id,
            'estado__in': ['agotado', 'vencido'],
            'oculto': False
        }
        if sucursal_id:
            filtro['sucursal_id'] = sucursal_id
        
        cantidad = cls.objects.filter(**filtro).update(oculto=True)
        return cantidad
    
    @classmethod
    def mostrar_cafs_ocultos(cls, empresa_id, sucursal_id=None):
        """
        Muestra todos los CAFs ocultos.
        Retorna la cantidad de CAFs mostrados.
        """
        filtro = {
            'empresa_id': empresa_id,
            'oculto': True
        }
        if sucursal_id:
            filtro['sucursal_id'] = sucursal_id
        
        cantidad = cls.objects.filter(**filtro).update(oculto=False)
        return cantidad
    
    @classmethod
    def eliminar_cafs_sin_uso(cls, empresa_id, sucursal_id=None):
        """
        Elimina CAFs que nunca fueron utilizados (folios_utilizados = 0)
        y que están agotados, vencidos o anulados.
        Retorna tupla (cantidad_eliminada, detalles)
        """
        filtro = {
            'empresa_id': empresa_id,
            'folios_utilizados': 0,
            'estado__in': ['agotado', 'vencido', 'anulado']
        }
        if sucursal_id:
            filtro['sucursal_id'] = sucursal_id
        
        return cls.objects.filter(**filtro).delete()


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
        ('enviando', 'Enviando al SII'),
        ('enviado', 'Enviado al SII'),
        ('aceptado', 'Aceptado por SII'),
        ('rechazado', 'Rechazado por SII'),
        ('pendiente', 'Pendiente de Envío'),
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
    orden_despacho = models.ManyToManyField(
        'ventas.Venta',
        related_name='dtes_despacho',
        verbose_name="Documentos de Despacho Asociados (Ventas/Guías)",
        blank=True
    )
    caf_utilizado = models.ForeignKey(
        ArchivoCAF,
        on_delete=models.PROTECT,
        related_name='dtes',
        verbose_name="CAF Utilizado"
    )
    vendedor = models.ForeignKey(
        'ventas.Vendedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dtes_vendedor',
        verbose_name="Vendedor Responsable"
    )
    vehiculo = models.ForeignKey(
        'pedidos.Vehiculo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dtes_vehiculo',
        verbose_name="Vehículo Asignado"
    )
    chofer = models.ForeignKey(
        'pedidos.Chofer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dtes_chofer',
        verbose_name="Chofer Asignado"
    )
    
    # IDENTIFICACIÓN DEL DOCUMENTO
    tipo_dte = models.CharField(
        max_length=10,
        choices=TIPO_DTE_CHOICES,
        verbose_name="Tipo DTE"
    )
    folio = models.IntegerField(verbose_name="Folio")
    fecha = models.DateField(verbose_name="Fecha", default=timezone.now)
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
