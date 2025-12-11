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
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Si no se proporcionó password, mantener el existente
        if not self.cleaned_data.get('password_certificado'):
            if self.instance.pk:  # Si es edición
                # Recuperar el password anterior de la BD
                original = Empresa.objects.get(pk=self.instance.pk)
                instance.password_certificado = original.password_certificado
        if commit:
            instance.save()
        return instance
    
    class Meta:
        model = Empresa
        fields = [
            'nombre', 'razon_social', 'rut', 'giro',
            'direccion', 'comuna', 'ciudad', 'region',
            'telefono', 'email', 'sitio_web', 'logo',
            'regimen_tributario', 'tipo_industria', 'usa_produccion', 'usa_sistema_despacho',
            'max_descuento_lineal', 'max_descuento_total',
            'facturacion_electronica',
            'ambiente_sii', 'modo_reutilizacion_folios', 'password_certificado',
            'razon_social_sii', 'giro_sii', 'codigo_actividad_economica',
            'direccion_casa_matriz', 'comuna_casa_matriz', 'ciudad_casa_matriz',
            'oficina_sii', 'email_intercambio', 'email_contacto_sii',
            'alerta_folios_minimos', 'impresora_factura', 'impresora_boleta',
            'impresora_guia', 'impresora_nota_credito', 'impresora_nota_debito',
            'impresora_vale', 'impresora_cotizacion', 
            'impresora_factura_nombre', 'impresora_boleta_nombre', 'impresora_guia_nombre',
            'impresora_nota_credito_nombre', 'impresora_nota_debito_nombre',
            'impresora_vale_nombre', 'impresora_cotizacion_nombre', 'estado'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'rut': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'giro': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'required': True}),
            'comuna': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'ciudad': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'region': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'required': True}),
            'sitio_web': forms.URLInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'regimen_tributario': forms.Select(attrs={'class': 'form-select'}),
            'tipo_industria': forms.Select(attrs={'class': 'form-select'}),
            'usa_produccion': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'usa_sistema_despacho': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_descuento_lineal': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'max_descuento_total': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
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
            'impresora_factura_nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'impresora_boleta_nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'impresora_guia_nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'impresora_nota_credito_nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'impresora_nota_debito_nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'impresora_vale_nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'impresora_cotizacion_nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
        }


class ConfiguracionesGeneralesForm(forms.ModelForm):
    """Formulario solo para configuraciones generales (NO incluye FE)"""
    class Meta:
        model = Empresa
        fields = [
            'usa_produccion', 'usa_sistema_despacho',
            'tipo_industria', 'max_descuento_lineal', 'max_descuento_total'
        ]
        widgets = {
            'usa_produccion': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'usa_sistema_despacho': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tipo_industria': forms.Select(attrs={'class': 'form-select'}),
            'max_descuento_lineal': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'max_descuento_total': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
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
        # Asegurar formato correcto de fecha
        if 'resolucion_fecha' in self.fields:
            self.fields['resolucion_fecha'].input_formats = ['%Y-%m-%d']
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Si no se proporcionó password, mantener el existente
        if not self.cleaned_data.get('password_certificado'):
            if self.instance.pk:  # Si es edición
                # Recuperar el password anterior de la BD
                original = Empresa.objects.get(pk=self.instance.pk)
                instance.password_certificado = original.password_certificado
        # Si no se proporcionó api_key, mantener el existente
        if not self.cleaned_data.get('api_key'):
            if self.instance.pk:  # Si es edición
                # Recuperar el api_key anterior de la BD
                original = Empresa.objects.get(pk=self.instance.pk)
                instance.api_key = original.api_key
        # Si no se proporcionó dtebox_auth_key, mantener el existente
        if not self.cleaned_data.get('dtebox_auth_key'):
            if self.instance.pk:  # Si es edición
                # Recuperar el dtebox_auth_key anterior de la BD
                original = Empresa.objects.get(pk=self.instance.pk)
                instance.dtebox_auth_key = original.dtebox_auth_key
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
            'api_url',
            'api_key',
            'razon_social_sii',
            'giro_sii',
            'codigo_actividad_economica',
            'direccion_casa_matriz',
            'comuna_casa_matriz',
            'ciudad_casa_matriz',
            'oficina_sii',
            'resolucion_fecha',
            'resolucion_numero',
            'email_intercambio',
            'email_contacto_sii',
            # Campos DTEBox
            'dtebox_habilitado',
            'dtebox_url',
            'dtebox_auth_key',
            'dtebox_ambiente',
            'dtebox_pdf417_columns',
            'dtebox_pdf417_level',
            'dtebox_pdf417_type',
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
            'email_intercambio': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email para recibir acuses'}),
            'email_contacto_sii': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email registrado en SII'}),
            'api_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://api.ejemplo.com/dte'}),
            'api_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese su API KEY', 'type': 'password', 'autocomplete': 'off'}),
            # Widgets DTEBox
            'dtebox_habilitado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'dtebox_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'http://192.168.1.100/api/Core.svc/core/SendDocumentAsXML'}),
            'dtebox_auth_key': forms.TextInput(attrs={'class': 'form-control', 'type': 'password', 'placeholder': 'Llave de autenticación DTEBox', 'autocomplete': 'off'}),
            'dtebox_ambiente': forms.Select(attrs={'class': 'form-select'}),
            'dtebox_pdf417_columns': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'dtebox_pdf417_level': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 8}),
            'dtebox_pdf417_type': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
        }
        labels = {
            # labels dict remains
        }

    def clean(self):
        cleaned = super().clean()
        cert_file = cleaned.get('certificado_digital') or (self.instance.certificado_digital if self.instance and self.instance.pk else None)
        password = cleaned.get('password_certificado') or (self.instance.password_certificado if self.instance and self.instance.pk else '')
        if self.cleaned_data.get('facturacion_electronica'):
            if not cert_file:
                raise ValidationError('Debe adjuntar un certificado digital (.p12/.pfx) para activar Facturación Electrónica.')
            try:
                from facturacion_electronica.firma_electronica import FirmadorDTE
                FirmadorDTE(cert_file.path if hasattr(cert_file, 'path') else cert_file.name, password or '')
            except ValueError as e:
                raise ValidationError(f'Certificado digital inválido o contraseña incorrecta: {e}')
        return cleaned


class ConfiguracionEmpresaForm(forms.ModelForm):
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

