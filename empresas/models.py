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
        """Formatea el RUT antes de guardar y crea sucursal principal si es nueva"""
        self.clean_rut()
        es_nueva = self.pk is None
        super().save(*args, **kwargs)
        
        # Si es una empresa nueva, crear sucursal principal automáticamente
        if es_nueva:
            self._crear_sucursal_principal()
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
    
    # Configuración de producción
    TIPO_INDUSTRIA_CHOICES = [
        ('textil', 'Textil y Confección'),
        ('carnico', 'Cárnico y Alimenticio'),
        ('panaderia', 'Panadería y Pastelería'),
        ('quimico', 'Químico y Farmacéutico'),
        ('otro', 'Otro'),
    ]
    tipo_industria = models.CharField(
        max_length=20,
        choices=TIPO_INDUSTRIA_CHOICES,
        blank=True,
        null=True,
        verbose_name="Tipo de Industria",
        help_text="Define el tipo de industria para adaptar formularios de producción"
    )
    
    # === FACTURACIÓN ELECTRÓNICA ===
    facturacion_electronica = models.BooleanField(
        default=False,
        verbose_name="Facturación Electrónica Activa"
    )
    ambiente_sii = models.CharField(
        max_length=20,
        choices=[
            ('certificacion', 'Certificación (Pruebas)'),
            ('produccion', 'Producción'),
        ],
        default='certificacion',
        verbose_name="Ambiente SII"
    )
    modo_reutilizacion_folios = models.BooleanField(
        default=False,
        verbose_name="Modo Reutilización de Folios",
        help_text="Permite reutilizar folios para pruebas (solo en certificación)"
    )
    
    # Certificado Digital
    certificado_digital = models.FileField(
        upload_to='empresas/certificados/',
        blank=True,
        null=True,
        verbose_name="Certificado Digital (.p12/.pfx)"
    )
    password_certificado = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Contraseña del Certificado"
    )
    
    # Datos SII (pueden diferir de los comerciales)
    razon_social_sii = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Razón Social SII"
    )
    giro_sii = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Giro SII"
    )
    codigo_actividad_economica = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Código Actividad Económica"
    )
    direccion_casa_matriz = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Dirección Casa Matriz"
    )
    comuna_casa_matriz = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Comuna Casa Matriz"
    )
    ciudad_casa_matriz = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Ciudad Casa Matriz"
    )
    oficina_sii = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Oficina SII",
        help_text="Oficina regional del SII donde está registrada la empresa"
    )

    # Resoluciones SII
    resolucion_fecha = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha Resolución SII"
    )
    resolucion_numero = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Número Resolución SII"
    )
    
    # Correos Electrónicos
    email_intercambio = models.EmailField(
        blank=True,
        verbose_name="Email para Intercambio (Acuses)"
    )
    email_contacto_sii = models.EmailField(
        blank=True,
        verbose_name="Email de Contacto SII"
    )
    
    # Configuración de Alertas CAF
    alerta_folios_minimos = models.IntegerField(
        default=10,
        verbose_name="Folios Mínimos para Alerta",
        help_text="Cantidad de folios restantes para comenzar a alertar por documento"
    )
    
    # CONFIGURACIÓN DE IMPRESORAS POR TIPO DE DOCUMENTO
    TIPO_IMPRESORA_CHOICES = [
        ('laser', 'Impresora Láser/Inyección (A4)'),
        ('termica', 'Impresora Térmica (80mm)'),
    ]
    
    # Documentos Electrónicos (DTE)
    impresora_factura = models.CharField(
        max_length=10,
        choices=TIPO_IMPRESORA_CHOICES,
        default='laser',
        verbose_name="Impresora para Facturas Electrónicas",
        help_text="Tipo de impresora a usar para imprimir facturas electrónicas"
    )
    impresora_boleta = models.CharField(
        max_length=10,
        choices=TIPO_IMPRESORA_CHOICES,
        default='laser',
        verbose_name="Impresora para Boletas Electrónicas",
        help_text="Tipo de impresora a usar para imprimir boletas electrónicas"
    )
    impresora_guia = models.CharField(
        max_length=10,
        choices=TIPO_IMPRESORA_CHOICES,
        default='laser',
        verbose_name="Impresora para Guías de Despacho",
        help_text="Tipo de impresora a usar para imprimir guías de despacho"
    )
    impresora_nota_credito = models.CharField(
        max_length=10,
        choices=TIPO_IMPRESORA_CHOICES,
        default='laser',
        verbose_name="Impresora para Notas de Crédito",
        help_text="Tipo de impresora a usar para imprimir notas de crédito"
    )
    impresora_nota_debito = models.CharField(
        max_length=10,
        choices=TIPO_IMPRESORA_CHOICES,
        default='laser',
        verbose_name="Impresora para Notas de Débito",
        help_text="Tipo de impresora a usar para imprimir notas de débito"
    )
    
    # Documentos Internos
    impresora_vale = models.CharField(
        max_length=10,
        choices=TIPO_IMPRESORA_CHOICES,
        default='termica',
        verbose_name="Impresora para Vales/Tickets",
        help_text="Tipo de impresora a usar para imprimir vales y tickets de venta"
    )
    impresora_cotizacion = models.CharField(
        max_length=10,
        choices=TIPO_IMPRESORA_CHOICES,
        default='laser',
        verbose_name="Impresora para Cotizaciones",
        help_text="Tipo de impresora a usar para imprimir cotizaciones"
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
    
    # === MÉTODOS HELPER PARA FACTURACIÓN ELECTRÓNICA ===
    def get_razon_social_dte(self):
        """Retorna la razón social para DTEs (usa la SII si existe, sino la normal)"""
        return self.razon_social_sii if self.razon_social_sii else self.razon_social
    
    def get_giro_dte(self):
        """Retorna el giro para DTEs (usa el SII si existe, sino el normal)"""
        return self.giro_sii if self.giro_sii else self.giro
    
    def get_direccion_dte(self):
        """Retorna la dirección para DTEs (usa casa matriz si existe, sino la normal)"""
        return self.direccion_casa_matriz if self.direccion_casa_matriz else self.direccion
    
    def get_comuna_dte(self):
        """Retorna la comuna para DTEs (usa casa matriz si existe, sino la normal)"""
        return self.comuna_casa_matriz if self.comuna_casa_matriz else self.comuna
    
    def get_ciudad_dte(self):
        """Retorna la ciudad para DTEs (usa casa matriz si existe, sino la normal)"""
        return self.ciudad_casa_matriz if self.ciudad_casa_matriz else self.ciudad
    
    def get_email_dte(self):
        """Retorna el email para DTEs (usa intercambio si existe, sino el normal)"""
        return self.email_intercambio if self.email_intercambio else self.email
    
    def _crear_sucursal_principal(self):
        """Crea automáticamente la sucursal principal y bodega principal"""
        from inventario.models import Bodega
        
        # Crear sucursal principal
        sucursal = Sucursal.objects.create(
            empresa=self,
            codigo='001',
            nombre='Casa Matriz',
            direccion=self.direccion,
            comuna=self.comuna,
            ciudad=self.ciudad,
            region=self.region,
            telefono=self.telefono,
            email=self.email,
            es_principal=True,
            estado='activa'
        )
        
        # Crear bodega principal para la sucursal
        Bodega.objects.create(
            empresa=self,
            sucursal=sucursal,
            nombre='Bodega Principal',
            codigo='BOD-001',
            descripcion='Bodega principal de la casa matriz',
            direccion=self.direccion,
            es_principal=True,
            activo=True
        )
        
        return sucursal


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
    
    # Configuración de órdenes de compra
    prefijo_orden_compra = models.CharField(max_length=10, default='OC', verbose_name="Prefijo Órdenes de Compra")
    siguiente_orden_compra = models.IntegerField(default=1, verbose_name="Siguiente Número Orden de Compra")
    formato_orden_compra = models.CharField(max_length=20, default='{prefijo}-{000}', verbose_name="Formato Órdenes de Compra")
    
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
        # Formato esperado: Aju-{000} donde {000} será reemplazado por el número con ceros
        numero_formateado = f"{self.prefijo_ajustes}-{numero:06d}"
        
        return numero_formateado
    
    def generar_numero_orden_compra(self):
        """Genera el siguiente número de orden de compra"""
        numero = self.siguiente_orden_compra
        self.siguiente_orden_compra += 1
        self.save()
        
        # Formatear el número según el formato configurado
        # Formato esperado: OC-{000} donde {000} será reemplazado por el número con ceros
        numero_formateado = f"{self.prefijo_orden_compra}-{numero:06d}"
        
        return numero_formateado
