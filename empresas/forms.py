from django import forms
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
            'regimen_tributario', 'tipo_industria', 'facturacion_electronica',
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


class FacturacionElectronicaForm(forms.ModelForm):
    """Formulario para configurar Facturación Electrónica"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Asegurar formato correcto de fecha
        if 'resolucion_fecha' in self.fields:
            self.fields['resolucion_fecha'].input_formats = ['%Y-%m-%d']
    
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
            'email_intercambio',
            'email_contacto_sii',
        ]
        widgets = {
            'facturacion_electronica': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ambiente_sii': forms.Select(attrs={'class': 'form-select'}),
            'certificado_digital': forms.FileInput(attrs={'class': 'form-control', 'accept': '.p12,.pfx'}),
            'password_certificado': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña del certificado'}),
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
        }
        labels = {
            'facturacion_electronica': 'Activar Facturación Electrónica',
            'ambiente_sii': 'Ambiente SII',
            'certificado_digital': 'Certificado Digital (.p12 o .pfx)',
            'password_certificado': 'Contraseña del Certificado',
            'razon_social_sii': 'Razón Social SII',
            'giro_sii': 'Giro SII',
            'codigo_actividad_economica': 'Código Actividad Económica',
            'direccion_casa_matriz': 'Dirección Casa Matriz',
            'comuna_casa_matriz': 'Comuna Casa Matriz',
            'ciudad_casa_matriz': 'Ciudad Casa Matriz',
            'oficina_sii': 'Oficina SII',
            'resolucion_fecha': 'Fecha Resolución',
            'resolucion_numero': 'Número Resolución',
            'email_intercambio': 'Email de Intercambio',
            'email_contacto_sii': 'Email Contacto SII',
        }


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
        ]
        widgets = {
            'prefijo_ajustes': forms.TextInput(attrs={'class': 'form-control'}),
            'siguiente_ajuste': forms.NumberInput(attrs={'class': 'form-control'}),
            'formato_ajustes': forms.TextInput(attrs={'class': 'form-control'}),
            'prefijo_orden_compra': forms.TextInput(attrs={'class': 'form-control'}),
            'siguiente_orden_compra': forms.NumberInput(attrs={'class': 'form-control'}),
            'formato_orden_compra': forms.TextInput(attrs={'class': 'form-control'}),
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

