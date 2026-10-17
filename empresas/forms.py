from django import forms
from django.core.exceptions import ValidationError
from .models import Empresa, Sucursal, ConfiguracionEmpresa


class EmpresaForm(forms.ModelForm):
    # Hacer password_certificado opcional y no requerido
    password_certificado = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='Solo completar si desea cambiar la contraseña'
    )
    smtp_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Dejar en blanco para mantener la actual',
            'autocomplete': 'new-password',
        }),
        help_text='Gmail: contraseña de aplicación. Vacío = no cambiar.',
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer campos opcionales que pueden tener valores por defecto
        self.fields['giro'].required = False
        self.fields['sitio_web'].required = False
        for campo in ('smtp_host', 'smtp_puerto', 'smtp_usuario', 'smtp_password', 'smtp_usar_tls'):
            if campo in self.fields:
                self.fields[campo].required = False
        
        # Establecer valores por defecto para campos opcionales cuando es creación
        if not self.instance.pk:  # Si es creación (no tiene pk)
            # Valores por defecto para campos con opciones
            if 'regimen_tributario' not in self.data:  # Solo si no viene en POST
                self.fields['regimen_tributario'].initial = '19'
            if 'ambiente_sii' not in self.data:
                self.fields['ambiente_sii'].initial = 'certificacion'
            if 'estado' not in self.data:
                self.fields['estado'].initial = 'activa'
            # Valores por defecto para campos numéricos
            if 'max_descuento_lineal' not in self.data:
                self.fields['max_descuento_lineal'].initial = 0
            if 'max_descuento_total' not in self.data:
                self.fields['max_descuento_total'].initial = 0
            if 'alerta_folios_minimos' not in self.data:
                self.fields['alerta_folios_minimos'].initial = 10
        elif self.instance.pk and not (self.instance.smtp_usuario or '').strip():
            self.fields['smtp_usuario'].initial = self.instance.email or ''
    
    def clean_codigo_actividad_economica(self):
        from facturacion_electronica.validacion_envio import normalizar_acteco
        valor = (self.cleaned_data.get('codigo_actividad_economica') or '').strip()
        if not valor:
            fe_activa = self.cleaned_data.get('facturacion_electronica')
            if fe_activa is None:
                fe_activa = getattr(self.instance, 'facturacion_electronica', False)
            if fe_activa:
                raise ValidationError(
                    'El código de actividad económica (Acteco) es obligatorio. El SII no acepta 0.'
                )
            return ''
        normalizado = normalizar_acteco(valor)
        if not normalizado:
            raise ValidationError('El Acteco debe ser un número mayor a 0 (código SII, ej. 620200).')
        return normalizado

    def clean_regimen_tributario(self):
        """Corregir valores inválidos de regimen_tributario"""
        valor = self.cleaned_data.get('regimen_tributario')
        if valor:
            # Mapear valores comunes incorrectos a valores válidos
            mapeo_correcciones = {
                'general': '19',
                'General': '19',
                'GENERAL': '19',
                'iva': '19',
                'IVA': '19',
                '19%': '19',
                '19 por ciento': '19',
            }
            valor_lower = str(valor).lower()
            if valor_lower in mapeo_correcciones:
                return mapeo_correcciones[valor_lower]
        return valor
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.instance.pk:
            original = Empresa.objects.get(pk=self.instance.pk)
            if not self.cleaned_data.get('password_certificado'):
                instance.password_certificado = original.password_certificado
            if 'smtp_usuario' not in self.data:
                instance.smtp_host = original.smtp_host
                instance.smtp_puerto = original.smtp_puerto
                instance.smtp_usuario = original.smtp_usuario
                instance.smtp_password = original.smtp_password
                instance.smtp_usar_tls = original.smtp_usar_tls
            elif not self.cleaned_data.get('smtp_password'):
                instance.smtp_password = original.smtp_password
        if commit:
            instance.save()
        return instance
    
    class Meta:
        model = Empresa
        fields = [
            'nombre', 'razon_social', 'rut', 'giro',
            'direccion', 'comuna', 'ciudad', 'region',
            'telefono', 'email', 'smtp_host', 'smtp_puerto', 'smtp_usuario', 'smtp_password',
            'smtp_usar_tls', 'sitio_web', 'logo',
            'regimen_tributario', 'tipo_industria', 'usa_produccion', 'usa_sistema_despacho',
            'max_descuento_lineal', 'max_descuento_total',
            'max_items_factura', 'max_items_boleta', 'max_items_guia',
            'max_items_cotizacion', 'max_items_nota_venta', 'max_items_vale',
            'facturacion_electronica',
            'ambiente_sii', 'modo_reutilizacion_folios', 'password_certificado',
            'razon_social_sii', 'giro_sii', 'codigo_actividad_economica',
            'direccion_casa_matriz', 'comuna_casa_matriz', 'ciudad_casa_matriz',
            'oficina_sii', 'email_intercambio', 'email_contacto_sii',
            'alerta_folios_minimos', 'impresora_factura', 'impresora_boleta',
            'impresora_guia', 'impresora_nota_credito', 'impresora_nota_debito',
            'impresora_vale', 'impresora_cotizacion', 'estado'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'rut': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'giro': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'required': True}),
            'comuna': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'ciudad': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'region': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'required': True}),
            'smtp_host': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'smtp.gmail.com'}),
            'smtp_puerto': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'smtp_usuario': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'tucorreo@gmail.com'}),
            'smtp_usar_tls': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sitio_web': forms.URLInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'regimen_tributario': forms.Select(attrs={'class': 'form-select'}),
            'tipo_industria': forms.Select(attrs={'class': 'form-select'}),
            'usa_produccion': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'usa_sistema_despacho': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_descuento_lineal': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'max_descuento_total': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'max_items_factura': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100}),
            'max_items_boleta': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100}),
            'max_items_guia': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100}),
            'max_items_cotizacion': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100}),
            'max_items_nota_venta': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100}),
            'max_items_vale': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100}),
            'facturacion_electronica': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ambiente_sii': forms.Select(attrs={'class': 'form-select'}),
            'modo_reutilizacion_folios': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'password_certificado': forms.PasswordInput(attrs={'class': 'form-control'}),
            'razon_social_sii': forms.TextInput(attrs={'class': 'form-control'}),
            'giro_sii': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_actividad_economica': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion_casa_matriz': forms.TextInput(attrs={'class': 'form-control'}),
            'comuna_casa_matriz': forms.TextInput(attrs={'class': 'form-control'}),
            'ciudad_casa_matriz': forms.TextInput(attrs={'class': 'form-control'}),
            'oficina_sii': forms.TextInput(attrs={'class': 'form-control'}),
            'email_intercambio': forms.EmailInput(attrs={'class': 'form-control'}),
            'email_contacto_sii': forms.EmailInput(attrs={'class': 'form-control'}),
            'alerta_folios_minimos': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'impresora_factura': forms.Select(attrs={'class': 'form-select'}),
            'impresora_boleta': forms.Select(attrs={'class': 'form-select'}),
            'impresora_guia': forms.Select(attrs={'class': 'form-select'}),
            'impresora_nota_credito': forms.Select(attrs={'class': 'form-select'}),
            'impresora_nota_debito': forms.Select(attrs={'class': 'form-select'}),
            'impresora_vale': forms.Select(attrs={'class': 'form-select'}),
            'impresora_cotizacion': forms.Select(attrs={'class': 'form-select'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
        }


class ConfiguracionesGeneralesForm(forms.ModelForm):
    """Formulario solo para configuraciones generales (NO incluye FE)"""
    class Meta:
        model = Empresa
        fields = [
            'usa_produccion', 'usa_sistema_despacho',
            'tipo_industria', 'max_descuento_lineal', 'max_descuento_total',
            'max_items_factura', 'max_items_boleta', 'max_items_guia',
            'max_items_cotizacion', 'max_items_nota_venta', 'max_items_vale'
        ]
        widgets = {
            'usa_produccion': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'usa_sistema_despacho': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tipo_industria': forms.Select(attrs={'class': 'form-select'}),
            'max_descuento_lineal': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'max_descuento_total': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'max_items_factura': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100}),
            'max_items_boleta': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100}),
            'max_items_guia': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100}),
            'max_items_cotizacion': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100}),
            'max_items_nota_venta': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100}),
            'max_items_vale': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100}),
        }


class FacturacionElectronicaForm(forms.ModelForm):
    """Formulario para configurar Facturación Electrónica"""
    
    # Hacer password_certificado opcional
    password_certificado = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Dejar en blanco para mantener la actual'
        }),
        label='Contraseña del Certificado',
        help_text='Solo completar si desea cambiar la contraseña'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Asegurar compatibilidad con formatos de fecha habituales
        for campo in ('resolucion_fecha', 'resolucion_fecha_certificacion', 'resolucion_fecha_produccion'):
            if campo in self.fields:
                self.fields[campo].input_formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d']
    
    def clean_codigo_actividad_economica(self):
        from facturacion_electronica.validacion_envio import normalizar_acteco
        valor = (self.cleaned_data.get('codigo_actividad_economica') or '').strip()
        if not valor:
            return ''
        normalizado = normalizar_acteco(valor)
        if not normalizado:
            raise ValidationError('El Acteco debe ser un número mayor a 0 (código SII, ej. 620200).')
        return normalizado

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not self.cleaned_data.get('password_certificado') and self.instance.pk:
            original = Empresa.objects.get(pk=self.instance.pk)
            instance.password_certificado = original.password_certificado

        # Sincronizar campos de resolución según ambiente
        if instance.ambiente_sii == 'produccion':
            if instance.resolucion_numero_produccion is not None:
                instance.resolucion_numero = instance.resolucion_numero_produccion
            if instance.resolucion_fecha_produccion is not None:
                instance.resolucion_fecha = instance.resolucion_fecha_produccion
        else:  # certificacion
            if instance.resolucion_numero_certificacion is not None:
                instance.resolucion_numero = instance.resolucion_numero_certificacion
            if instance.resolucion_fecha_certificacion is not None:
                instance.resolucion_fecha = instance.resolucion_fecha_certificacion

        if commit:
            instance.save()
        return instance
    
    class Meta:
        model = Empresa
        fields = [
            'facturacion_electronica',
            'ambiente_sii',
            'certificado_digital',
            'password_certificado',
            'razon_social_sii',
            'giro_sii',
            'codigo_actividad_economica',
            'direccion_casa_matriz',
            'comuna_casa_matriz',
            'ciudad_casa_matriz',
            'oficina_sii',
            'resolucion_fecha',
            'resolucion_numero',
            'resolucion_numero_certificacion',
            'resolucion_fecha_certificacion',
            'resolucion_numero_produccion',
            'resolucion_fecha_produccion',
            'email_intercambio',
            'email_contacto_sii',
        ]
        widgets = {
            'facturacion_electronica': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ambiente_sii': forms.Select(attrs={'class': 'form-select'}),
            'certificado_digital': forms.FileInput(attrs={'class': 'form-control', 'accept': '.p12,.pfx'}),
            # password_certificado se define arriba como campo personalizado
            'razon_social_sii': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Razón social registrada en SII'}),
            'giro_sii': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Giro registrado en SII'}),
            'codigo_actividad_economica': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 620200'}),
            'direccion_casa_matriz': forms.TextInput(attrs={'class': 'form-control'}),
            'comuna_casa_matriz': forms.TextInput(attrs={'class': 'form-control'}),
            'ciudad_casa_matriz': forms.TextInput(attrs={'class': 'form-control'}),
            'oficina_sii': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Santiago Oriente'}),
            'resolucion_fecha': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                format='%Y-%m-%d'
            ),
            'resolucion_numero': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Número de resolución'}),
            'resolucion_numero_certificacion': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'resolucion_fecha_certificacion': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                format='%Y-%m-%d'
            ),
            'resolucion_numero_produccion': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 80'}),
            'resolucion_fecha_produccion': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                format='%Y-%m-%d'
            ),
            'email_intercambio': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email para recibir acuses'}),
            'email_contacto_sii': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email registrado en SII'}),
        }
        labels = {
            'resolucion_numero_certificacion': 'N° Resolución Certificación',
            'resolucion_fecha_certificacion': 'Fecha Resolución Certificación',
            'resolucion_numero_produccion': 'N° Resolución Producción',
            'resolucion_fecha_produccion': 'Fecha Resolución Producción',
        }

    def clean(self):
        cleaned = super().clean()
        # Solo validar si se está activando facturación electrónica
        facturacion_electronica = cleaned.get('facturacion_electronica', False)
        
        if facturacion_electronica:
            acteco = (cleaned.get('codigo_actividad_economica') or '').strip()
            if not acteco:
                self.add_error(
                    'codigo_actividad_economica',
                    'El código de actividad económica (Acteco) es obligatorio cuando la Facturación Electrónica está activada. Ingrese su código SII (ej. 620200).'
                )

            # Determinar si se subió un nuevo certificado o se escribió una nueva contraseña
            has_new_file = bool(self.files and self.files.get('certificado_digital'))
            new_password_val = (cleaned.get('password_certificado') or '').strip()
            has_new_password = bool(new_password_val)
            es_nuevo = not self.instance.pk if self.instance else True

            cert_file = self.files.get('certificado_digital') if has_new_file else (self.instance.certificado_digital if self.instance and self.instance.pk else None)
            password = new_password_val if has_new_password else (self.instance.password_certificado if self.instance and self.instance.pk else '')
            
            # Si es una empresa nueva (sin pk) y se activa FE, requerir certificado
            if es_nuevo and not cert_file:
                self.add_error(
                    'certificado_digital',
                    'Debe adjuntar un certificado digital (.p12/.pfx) para activar Facturación Electrónica.'
                )
            
            # Solo validar la desencriptación del certificado si el usuario subió un nuevo archivo o ingresó una nueva contraseña
            if (has_new_file or has_new_password) and cert_file:
                try:
                    from facturacion_electronica.firma_electronica import FirmadorDTE
                    import tempfile
                    import os
                    
                    # Si es un archivo subido recientemente (InMemoryUploadedFile o TemporaryUploadedFile)
                    if hasattr(cert_file, 'temporary_file_path'):
                        cert_path = cert_file.temporary_file_path()
                        FirmadorDTE(cert_path, password or '')
                    elif hasattr(cert_file, 'path'):
                        cert_path = cert_file.path
                        FirmadorDTE(cert_path, password or '')
                    elif hasattr(cert_file, 'read'):
                        cert_content = cert_file.read()
                        cert_file.seek(0)
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pfx') as tmp_file:
                            tmp_file.write(cert_content)
                            tmp_path = tmp_file.name
                        try:
                            FirmadorDTE(tmp_path, password or '')
                        finally:
                            if os.path.exists(tmp_path):
                                os.unlink(tmp_path)
                    else:
                        cert_path = str(cert_file)
                        FirmadorDTE(cert_path, password or '')
                    
                except ValueError as e:
                    self.add_error(
                        'certificado_digital',
                        f'Certificado digital inválido o contraseña incorrecta: {e}'
                    )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f'Error al validar certificado (no bloqueante): {e}')
        
        return cleaned


class ConfiguracionEmpresaForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Establecer valores por defecto cuando es creación
        if not self.instance.pk:  # Si es creación (no tiene pk)
            # Valores por defecto para campos de texto
            if 'prefijo_ajustes' not in self.data:
                self.fields['prefijo_ajustes'].initial = 'AJU'
            if 'formato_ajustes' not in self.data:
                # Formato más corto que quepa en 20 caracteres
                self.fields['formato_ajustes'].initial = '{prefijo}-{000}'
            if 'prefijo_orden_compra' not in self.data:
                self.fields['prefijo_orden_compra'].initial = 'OC'
            if 'formato_orden_compra' not in self.data:
                # Formato más corto que quepa en 20 caracteres
                self.fields['formato_orden_compra'].initial = '{prefijo}-{000}'
            # Valores por defecto para campos numéricos
            if 'siguiente_ajuste' not in self.data:
                self.fields['siguiente_ajuste'].initial = 1
            if 'siguiente_orden_compra' not in self.data:
                self.fields['siguiente_orden_compra'].initial = 1
            # Valores por defecto para campos de selección
            if 'frecuencia_respaldo' not in self.data:
                self.fields['frecuencia_respaldo'].initial = 'diario'
    
    class Meta:
        model = ConfiguracionEmpresa
        fields = [
            'prefijo_ajustes',
            'siguiente_ajuste',
            'formato_ajustes',
            'prefijo_orden_compra',
            'siguiente_orden_compra',
            'formato_orden_compra',
            'imprimir_logo',
            'pie_pagina_documentos',
            'alerta_stock_minimo',
            'notificar_vencimientos',
            'respaldo_automatico',
            'frecuencia_respaldo',
        ]
        widgets = {
            'prefijo_ajustes': forms.TextInput(attrs={'class': 'form-control'}),
            'siguiente_ajuste': forms.NumberInput(attrs={'class': 'form-control'}),
            'formato_ajustes': forms.TextInput(attrs={'class': 'form-control'}),
            'prefijo_orden_compra': forms.TextInput(attrs={'class': 'form-control'}),
            'siguiente_orden_compra': forms.NumberInput(attrs={'class': 'form-control'}),
            'formato_orden_compra': forms.TextInput(attrs={'class': 'form-control'}),
            'imprimir_logo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'pie_pagina_documentos': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'alerta_stock_minimo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notificar_vencimientos': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'respaldo_automatico': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'frecuencia_respaldo': forms.Select(attrs={'class': 'form-select'}),
        }


class SucursalForm(forms.ModelForm):
    class Meta:
        model = Sucursal
        fields = [
            'nombre', 'codigo', 'direccion', 'comuna', 'ciudad', 'region',
            'telefono', 'email', 'es_principal', 'horario_apertura', 'horario_cierre',
            'gerente', 'telefono_gerente', 'estado'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'comuna': forms.TextInput(attrs={'class': 'form-control'}),
            'ciudad': forms.TextInput(attrs={'class': 'form-control'}),
            'region': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'es_principal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'horario_apertura': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'horario_cierre': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'gerente': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono_gerente': forms.TextInput(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
        }

