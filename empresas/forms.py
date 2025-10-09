from django import forms
from .models import Empresa, Sucursal, ConfiguracionEmpresa


class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = [
            'nombre', 'razon_social', 'rut', 'giro', 
            'direccion', 'comuna', 'ciudad', 'region',
            'telefono', 'email', 'sitio_web', 'logo',
            'regimen_tributario', 'estado'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control'}),
            'rut': forms.TextInput(attrs={'class': 'form-control'}),
            'giro': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'comuna': forms.TextInput(attrs={'class': 'form-control'}),
            'ciudad': forms.TextInput(attrs={'class': 'form-control'}),
            'region': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'sitio_web': forms.URLInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'regimen_tributario': forms.Select(attrs={'class': 'form-select'}),
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

