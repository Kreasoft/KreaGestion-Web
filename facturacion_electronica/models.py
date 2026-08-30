from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from empresas.models import Empresa
from decimal import Decimal
import unicodedata
from facturacion_electronica.ind_traslado import IND_TRASLADO_CHOICES, TIPO_DESPACHO_SII_CHOICES
from facturacion_electronica.clasificacion_sii import (
    contiene_codigo_estado,
    es_dte_no_recibido_sii,
    es_espera_reintento_sii,
    es_falso_rechazo_sii,
    es_glosa_envio_procesado,
    evidencia_rechazo_tributario,
    extraer_segundos_espera,
    extraer_track_id,
    mensaje_espera_reintento,
    texto_sii_de,
)


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
    AMBIENTE_CHOICES = [
        ('certificacion', 'Certificación'),
        ('produccion', 'Producción'),
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
    ambiente = models.CharField(
        max_length=20,
        choices=AMBIENTE_CHOICES,
        default='certificacion',
        verbose_name="Ambiente SII"
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
    fecha_vencimiento = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="Fecha de Vencimiento",
        help_text="Fecha en que vence el CAF (por defecto 6 meses desde autorización)"
    )
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
        unique_together = [['empresa', 'sucursal', 'tipo_documento', 'ambiente', 'folio_desde', 'folio_hasta']]
        indexes = [
            models.Index(fields=['empresa', 'sucursal', 'tipo_documento', 'ambiente', 'estado']),
            models.Index(fields=['folio_desde', 'folio_hasta']),
            models.Index(fields=['sucursal', 'estado', 'oculto']),
        ]
    
    def __str__(self):
        sucursal_nombre = self.sucursal.nombre if self.sucursal else "Sin sucursal"
        return f"CAF {self.get_tipo_documento_display()} [{self.get_ambiente_display()}] ({self.folio_desde}-{self.folio_hasta}) - {sucursal_nombre}"
    
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
            tipo_documento=self.tipo_documento,
            ambiente=self.ambiente,
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
            ambiente=self.ambiente,
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
            ambiente=self.ambiente,
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
        from datetime import timedelta
        
        # 1. Calcular fecha de vencimiento por defecto si no existe
        if self.fecha_autorizacion and not self.fecha_vencimiento:
            self.fecha_vencimiento = self.fecha_autorizacion + timedelta(days=180)

        if not self.ambiente and self.empresa_id:
            self.ambiente = getattr(self.empresa, 'ambiente_sii', 'certificacion') or 'certificacion'

        # 2. Ejecutar validaciones solo si es un CAF nuevo o si cambió el contenido
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

    @property
    def observacion_historial(self):
        """Observación visible para el historial de CAFs."""
        if self.estado == 'vencido':
            if self.fecha_vencimiento:
                return f"Vencido el {self.fecha_vencimiento.strftime('%d-%m-%Y')}"
            return "Vencido"
        if self.estado == 'agotado':
            if self.fecha_agotamiento:
                return f"Agotado el {self.fecha_agotamiento.strftime('%d-%m-%Y %H:%M')}"
            return "CAF agotado"
        if self.oculto:
            return "Movido manualmente a historial"
        if self.estado == 'anulado':
            return "CAF anulado"
        return "-"
    
    def esta_vigente(self):
        """
        Verifica si el CAF está vigente usando el campo fecha_vencimiento
        """
        from datetime import date
        
        if not self.fecha_vencimiento:
            return False
        
        # Usar date.today() para comparar fechas 'naive' y evitar problemas de zona horaria
        return date.today() <= self.fecha_vencimiento
    
    def dias_para_vencer(self):
        """Retorna la cantidad de días que faltan para que venza el CAF"""
        from datetime import date
        
        if not self.fecha_vencimiento:
            return 0
        
        hoy = date.today()
        
        if hoy > self.fecha_vencimiento:
            return 0  # Ya venció
        
        return (self.fecha_vencimiento - hoy).days
    
    def get_fecha_vencimiento(self):
        """Retorna la fecha de vencimiento del CAF (alias para el campo)"""
        return self.fecha_vencimiento
    
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
        """Obtiene el siguiente folio disponible y actualiza el contador
        
        VALIDACIÓN CRÍTICA: Verifica que el folio esté dentro del rango autorizado
        """
        if self.estado != 'activo':
            raise ValueError(f"CAF no está activo (Estado: {self.estado})")
        
        if self.folios_utilizados >= self.cantidad_folios:
            self.estado = 'agotado'
            self.save()
            raise ValueError("No hay más folios disponibles en este CAF")
        
        # VALIDACIÓN CRÍTICA: Verificar que el próximo folio esté en el rango autorizado
        proximo_folio = self.folio_actual + 1
        
        if proximo_folio < self.folio_desde:
            raise ValueError(
                f"CRÍTICO: Folio {proximo_folio} es menor que el inicio del rango "
                f"[{self.folio_desde}-{self.folio_hasta}] para CAF ID {self.id}. "
                f"El CAF puede estar corrupto. Contacte al administrador."
            )
        
        if proximo_folio > self.folio_hasta:
            # El CAF está agotado
            self.estado = 'agotado'
            self.save()
            raise ValueError(
                f"No hay más folios disponibles. El próximo folio ({proximo_folio}) "
                f"excede el rango autorizado [{self.folio_desde}-{self.folio_hasta}]"
            )
        
        # Todo OK: incrementar y guardar
        self.folio_actual = proximo_folio
        self.folios_utilizados += 1
        
        # Verificar si se agotó
        if self.folios_utilizados >= self.cantidad_folios:
            self.estado = 'agotado'
            self.fecha_agotamiento = timezone.now()
        
        self.save()
        
        # Log para auditoría
        print(f"[CAF {self.id}] Folio {proximo_folio} asignado. "
              f"Rango: [{self.folio_desde}-{self.folio_hasta}], "
              f"Utilizados: {self.folios_utilizados}/{self.cantidad_folios}")
        
        return proximo_folio
    
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
            ambiente=getattr(empresa, 'ambiente_sii', 'certificacion'),
            estado='activo',
            oculto=False
        ).order_by('folio_actual').first()

    @classmethod
    def sincronizar_cafs_vencidos(cls, empresa_id):
        """
        Marca como vencidos los CAFs activos cuya fecha de vencimiento ya expiró.
        """
        from datetime import date
        hoy = date.today()
        return cls.objects.filter(
            empresa_id=empresa_id,
            estado='activo',
            fecha_vencimiento__isnull=False,
            fecha_vencimiento__lt=hoy,
        ).update(estado='vencido')
    
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
        ('aceptado_reparos', 'Aceptado con reparos'),
        ('rechazado', 'Rechazado por SII'),
        ('pendiente', 'Pendiente de Envío'),
        ('error_envio', 'Pendiente de reenvío'),
        ('anulado', 'Anulado'),
    ]
    
    # Tipos de traslado para Guías de Despacho (IndTraslado SII)
    TIPO_TRASLADO_CHOICES = IND_TRASLADO_CHOICES
    
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
        verbose_name="Observación de envío"
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

    # Campos de transporte para Guías de Despacho (Opcionales)
    patente_transporte = models.CharField(
        max_length=10, 
        blank=True, 
        null=True, 
        verbose_name="Patente Vehículo"
    )
    rut_transportista = models.CharField(
        max_length=12, 
        blank=True, 
        null=True,
        verbose_name="RUT Transportista"
    )
    nombre_chofer = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        verbose_name="Nombre Chofer"
    )
    tipo_despacho_sii = models.CharField(
        max_length=1,
        choices=TIPO_DESPACHO_SII_CHOICES,
        blank=True,
        null=True,
        verbose_name="Tipo de Despacho SII",
        help_text="TipoDespacho 1/2/3. Distinto de IndTraslado.",
    )
    patente_carro = models.CharField(
        max_length=8,
        blank=True,
        null=True,
        verbose_name="Patente carro o remolque",
    )
    fecha_salida = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de salida",
    )
    hora_salida = models.TimeField(
        blank=True,
        null=True,
        verbose_name="Hora de salida",
    )
    fecha_llegada = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de llegada",
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
    
    def save(self, *args, **kwargs):
        """
        Override save para validar que el folio esté dentro del rango del CAF asignado.
        Esta validación es CRÍTICA para prevenir la asignación de folios inválidos.
        """
        from django.core.exceptions import ValidationError
        
        # Validar solo si hay un CAF asignado
        if self.caf_utilizado:
            # Verificar que el folio esté dentro del rango autorizado del CAF
            if not (self.caf_utilizado.folio_desde <= self.folio <= self.caf_utilizado.folio_hasta):
                raise ValidationError(
                    f"FOLIO INVALIDO: El folio {self.folio} NO está dentro del rango autorizado "
                    f"del CAF (rango: {self.caf_utilizado.folio_desde}-{self.caf_utilizado.folio_hasta}). "
                    f"Este DTE NO puede ser enviado al SII. "
                    f"CAF ID: {self.caf_utilizado.id}, "
                    f"Tipo DTE: {self.get_tipo_dte_display()}, "
                    f"Empresa: {self.empresa.nombre}"
                )
            
            # Validar que el CAF sea del mismo tipo de documento
            if self.caf_utilizado.tipo_documento != self.tipo_dte:
                raise ValidationError(
                    f"TIPO DTE INCORRECTO: El CAF es para tipo '{self.caf_utilizado.get_tipo_documento_display()}' "
                    f"pero el DTE es tipo '{self.get_tipo_dte_display()}'. "
                    f"CAF ID: {self.caf_utilizado.id}"
                )
            
            # Validar que el CAF pertenezca a la misma empresa
            if self.caf_utilizado.empresa_id != self.empresa_id:
                raise ValidationError(
                    f"EMPRESA INCORRECTA: El CAF pertenece a '{self.caf_utilizado.empresa.nombre}' "
                    f"pero el DTE es para '{self.empresa.nombre}'"
                )
            
            print(f"[VALIDACION DTE] Folio {self.folio} validado correctamente con CAF ID {self.caf_utilizado.id} "
                  f"(rango: {self.caf_utilizado.folio_desde}-{self.caf_utilizado.folio_hasta})")
        
        # Llamar al save() original
        super().save(*args, **kwargs)
    
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

    @staticmethod
    def _normalizar_estado_texto(valor):
        texto = unicodedata.normalize('NFKD', str(valor or ''))
        texto = ''.join(ch for ch in texto if not unicodedata.combining(ch))
        return texto.upper().strip()

    def _campo_sii_cargado(self, nombre):
        """Lee glosa/error/respuesta sin forzar un fetch de campos deferred."""
        try:
            if nombre in (self.get_deferred_fields() or ()):
                return ''
        except Exception:
            pass
        try:
            return getattr(self, nombre, '') or ''
        except Exception:
            return ''

    def _texto_respuesta_sii(self):
        """Clasifica con glosa + error. respuesta_sii solo si ya está cargada."""
        return texto_sii_de(
            self._campo_sii_cargado('glosa_sii'),
            self._campo_sii_cargado('error_envio'),
            self._campo_sii_cargado('respuesta_sii'),
        )

    def en_espera_reintento_sii(self):
        return es_espera_reintento_sii(self._texto_respuesta_sii())

    def segundos_restantes_espera_sii(self):
        if not self.en_espera_reintento_sii():
            return 0
        segundos = extraer_segundos_espera(self._texto_respuesta_sii()) or 900
        inicio = self.fecha_consulta_estado or self.fecha_respuesta_sii or self.fecha_envio_sii
        if not inicio:
            return segundos
        restante = int((inicio + timedelta(seconds=segundos) - timezone.now()).total_seconds())
        return max(0, restante)

    @property
    def tiene_track_sii(self):
        if str(self.track_id or '').strip():
            return True
        return bool(extraer_track_id(self._texto_respuesta_sii()))

    def track_id_efectivo(self):
        return str(self.track_id or extraer_track_id(self._texto_respuesta_sii()) or '').strip()

    def get_mensaje_espera_reintento(self):
        track = self.track_id_efectivo()
        restante = self.segundos_restantes_espera_sii() or extraer_segundos_espera(self._texto_respuesta_sii()) or 900
        return mensaje_espera_reintento(restante, track)

    def _es_falso_rechazo_persistido(self):
        return es_falso_rechazo_sii(
            self._texto_respuesta_sii(),
            estado_sii=self.estado_sii,
            track_id=self.track_id,
        )

    def corregir_falso_rechazo_espera(self):
        """Si el SII solo pidió esperar o confirmó recepción, no es rechazo ni reenvío."""
        if not self._es_falso_rechazo_persistido():
            return False
        campos = {}
        if str(self.estado_sii or '').strip().lower() in {'rechazado', 'error_envio', 'error'}:
            self.estado_sii = 'enviado'
            campos['estado_sii'] = 'enviado'
        track = extraer_track_id(self._texto_respuesta_sii())
        if track and not str(self.track_id or '').strip():
            self.track_id = track
            campos['track_id'] = track
        if not campos:
            return False
        if self.pk:
            type(self).objects.filter(pk=self.pk).update(**campos)
        return True

    def get_estado_sii_real(self):
        try:
            return self._calcular_estado_sii_real()
        except Exception:
            estado = str(self.estado_sii or '').strip().lower()
            if estado == 'rechazado' and str(self.track_id or '').strip():
                return 'enviado'
            return estado or 'pendiente'

    def _calcular_estado_sii_real(self):
        texto = self._texto_respuesta_sii()
        if es_espera_reintento_sii(texto) or self._es_falso_rechazo_persistido():
            return 'enviado'

        estado_actual = str(self.estado_sii or '').strip().lower()
        glosa = self._normalizar_estado_texto(self._campo_sii_cargado('glosa_sii'))
        error = self._normalizar_estado_texto(self._campo_sii_cargado('error_envio'))
        texto_sii = f'{glosa} {error}'.strip()

        # Nunca Rechazada sin RCH/RSC o la palabra RECHAZADO.
        if evidencia_rechazo_tributario(texto_sii, texto):
            return 'rechazado'
        if estado_actual == 'rechazado':
            return 'enviado' if str(self.track_id or '').strip() else 'pendiente'

        if estado_actual in {'aceptado', 'anulado', 'aceptado_reparos'}:
            return estado_actual

        if es_glosa_envio_procesado(texto_sii, texto):
            return 'enviado'

        if any(token in glosa for token in ['ACEPTADO CON REPAROS', 'ACEPTADA CON REPAROS']) or contiene_codigo_estado(glosa, ('RPR', 'RPC', 'RLV')):
            return 'aceptado_reparos'
        if any(token in glosa for token in ['ACEPTADO', 'ACEPTADA']) or contiene_codigo_estado(glosa, ('EOK', 'DOK', 'SOK')):
            return 'aceptado'

        if estado_actual in {'error', 'error_envio'}:
            return 'error_envio'

        if not str(self.track_id or '').strip():
            return estado_actual or 'pendiente'

        # El XML de recepción (RECEPCIONDTE) no implica aceptación:
        # no inferir Aceptada por substrings tipo REC/OK/CRT.
        return estado_actual or 'enviado'

    def get_estado_sii_real_display(self):
        estado = self.get_estado_sii_real()
        etiquetas = {
            'aceptado': 'Aceptada',
            'aceptado_reparos': 'Aceptada con reparos',
            'rechazado': 'Rechazada',
            'error_envio': 'Pendiente de reenvío',
            'enviado': 'Pendiente SII',
            'enviando': 'Pendiente SII',
            'generado': 'Pendiente SII',
            'firmado': 'Pendiente SII',
            'pendiente': 'Pendiente SII',
            'anulado': 'Anulado',
        }
        return etiquetas.get(estado, 'Pendiente SII' if self.track_id else (self.get_estado_sii_display() or estado or '-'))

    def get_estado_sii_real_badge_style(self):
        estado = self.get_estado_sii_real()
        estilos = {
            'aceptado': 'background: rgba(72, 187, 120, 0.15); color: #2F855A; border: 1px solid rgba(72, 187, 120, 0.28);',
            'aceptado_reparos': 'background: rgba(236, 201, 75, 0.22); color: #744210; border: 1px solid rgba(236, 201, 75, 0.32);',
            'rechazado': 'background: rgba(229, 62, 62, 0.15); color: #C53030; border: 1px solid rgba(229, 62, 62, 0.26);',
            'error_envio': 'background: rgba(196, 154, 82, 0.18); color: #6F5B44; border: 1px solid rgba(196, 154, 82, 0.35);',
            'enviado': 'background: rgba(236, 201, 75, 0.22); color: #744210; border: 1px solid rgba(236, 201, 75, 0.32);',
            'enviando': 'background: rgba(236, 201, 75, 0.22); color: #744210; border: 1px solid rgba(236, 201, 75, 0.32);',
            'pendiente': 'background: rgba(236, 201, 75, 0.22); color: #744210; border: 1px solid rgba(236, 201, 75, 0.32);',
            'generado': 'background: rgba(236, 201, 75, 0.22); color: #744210; border: 1px solid rgba(236, 201, 75, 0.32);',
            'firmado': 'background: rgba(236, 201, 75, 0.22); color: #744210; border: 1px solid rgba(236, 201, 75, 0.32);',
            'anulado': 'background: #E2E8F0; color: #4A5568; border: 1px solid #CBD5E0;',
        }
        return estilos.get(estado, 'background: #E2E8F0; color: #4A5568; border: 1px solid #CBD5E0;')

    @property
    def get_estado_sii_real_es_final(self):
        return self.get_estado_sii_real() in {'aceptado', 'aceptado_reparos', 'rechazado', 'anulado'}

    @property
    def puede_enviarse_al_sii(self):
        if self.tiene_track_sii:
            return False
        if self.en_espera_reintento_sii() or self._es_falso_rechazo_persistido():
            return False
        estado = str(self.estado_sii or '').strip().lower()
        if estado in {'aceptado', 'aceptado_reparos', 'rechazado', 'anulado'}:
            return False
        return True

    @classmethod
    def corregir_falsos_rechazos_masivo(cls, empresa=None):
        """Pasa a enviado los DTE con falso rechazo (espera 900s / Envio Procesado / glosa vacía + track)."""
        qs = cls.objects.filter(estado_sii__in=['rechazado', 'error_envio', 'error'])
        if empresa is not None:
            qs = qs.filter(empresa=empresa)
        qs = qs.only('id', 'estado_sii', 'glosa_sii', 'error_envio', 'track_id', 'respuesta_sii')
        corregidos = []
        for documento in qs.iterator():
            if documento.corregir_falso_rechazo_espera():
                corregidos.append(documento.pk)
        return corregidos

    @property
    def puede_emitir_documento_tributario(self):
        return self.get_estado_sii_real() not in {'rechazado', 'anulado'}

    @property
    def es_error_envio(self):
        return self.get_estado_sii_real() == 'error_envio'

    @property
    def esta_rechazado_por_sii(self):
        return self.get_estado_sii_real() == 'rechazado'

    def get_mensaje_no_emitible(self):
        estado = self.get_estado_sii_real()
        if estado == 'rechazado':
            return (
                'Este documento fue rechazado por el SII y no puede emitirse '
                'ni imprimirse como documento tributario valido. Corrige el '
                'documento origen y emite uno nuevo.'
            )
        if estado == 'anulado':
            return (
                'Este documento esta anulado y no puede emitirse ni imprimirse '
                'como documento tributario valido.'
            )
        return 'Este documento no puede emitirse ni imprimirse como documento tributario valido.'

    def requiere_consulta_estado_sii(self):
        if not self.tiene_track_sii:
            return False
        return self.get_estado_sii_real() != 'anulado'

    @property
    def permite_reenvio_xml_corregido(self):
        """Excepción: hay Track pero el SII no registró el DTE. Mismo folio, XML nuevo."""
        if not self.tiene_track_sii:
            return False
        if self.get_estado_sii_real() in {'aceptado', 'aceptado_reparos', 'anulado'}:
            return False
        from facturacion_electronica.validacion_envio import xml_tiene_acteco_invalido
        if es_dte_no_recibido_sii(self._texto_respuesta_sii()):
            return True
        xml = (self.xml_firmado or '') or (getattr(self, 'xml_dte', None) or '')
        return xml_tiene_acteco_invalido(xml)

    def requiere_refresco_estado_sii(self):
        if not self.tiene_track_sii:
            return False
        return self.get_estado_sii_real() not in {'aceptado', 'aceptado_reparos', 'anulado'}

    @classmethod
    def refrescar_estados_visibles(cls, documentos, limit=50):
        pendientes = []
        for documento in documentos:
            if isinstance(documento, cls) and documento.requiere_refresco_estado_sii():
                pendientes.append(documento)
                if len(pendientes) >= limit:
                    break

        if not pendientes:
            return documentos

        from facturacion_electronica.dte_service import DTEService

        servicios = {}
        for documento in pendientes:
            try:
                servicio = servicios.get(documento.empresa_id)
                if servicio is None:
                    servicio = DTEService(documento.empresa)
                    servicios[documento.empresa_id] = servicio
                servicio.consultar_estado_dte(documento)
            except Exception:
                continue

        return documentos

    def get_tipo_slug(self):
        """Retorna un slug simplificado (factura, boleta, guia, etc.)"""
        if self.tipo_dte in ['33', '34']:
            return 'factura'
        if self.tipo_dte in ['39', '41']:
            return 'boleta'
        if self.tipo_dte == '52':
            return 'guia'
        if self.tipo_dte == '61':
            return 'notacredito'
        if self.tipo_dte == '56':
            return 'notadebito'
        return 'ticket'


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
