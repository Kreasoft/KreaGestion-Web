from django import forms
from django.core.exceptions import ValidationError
from .models import Empresa, Sucursal, ConfiguracionEmpresa
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, Fieldset, HTML, Div
from crispy_forms.bootstrap import Tab, TabHolder


class EmpresaForm(forms.ModelForm):
    """Formulario para crear y editar empresas"""
    
    class Meta:
        model = Empresa
        fields = [
            'nombre', 'razon_social', 'rut', 'giro', 'direccion', 
            'comuna', 'ciudad', 'region', 'telefono', 'email', 
            'sitio_web', 'logo', 'regimen_tributario', 'estado'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese el nombre de la empresa'
            }),
            'razon_social': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese la razón social'
            }),
            'rut': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '12.345.678-9',
                'id': 'id_rut',
                'maxlength': '12'
            }),
            'giro': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese el giro comercial'
            }),
            'direccion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ingrese la dirección completa'
            }),
            'comuna': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese la comuna'
            }),
            'ciudad': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese la ciudad'
            }),
            'region': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese la región'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+56 9 1234 5678'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'empresa@ejemplo.com'
            }),
            'sitio_web': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://www.empresa.com'
            }),
            'logo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'regimen_tributario': forms.Select(attrs={
                'class': 'form-control'
            }),
            'estado': forms.Select(attrs={
                'class': 'form-control'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            TabHolder(
                Tab('Información Básica',
                    Row(
                        Column('nombre', css_class='col-md-6'),
                        Column('razon_social', css_class='col-md-6'),
                    ),
                    Row(
                        Column('rut', css_class='col-md-6'),
                        Column('giro', css_class='col-md-6'),
                    ),
                    Row(
                        Column('regimen_tributario', css_class='col-md-6'),
                        Column('estado', css_class='col-md-6'),
                    ),
                ),
                Tab('Ubicación',
                    Row(
                        Column('direccion', css_class='col-12'),
                    ),
                    Row(
                        Column('comuna', css_class='col-md-4'),
                        Column('ciudad', css_class='col-md-4'),
                        Column('region', css_class='col-md-4'),
                    ),
                ),
                Tab('Contacto',
                    Row(
                        Column('telefono', css_class='col-md-6'),
                        Column('email', css_class='col-md-6'),
                    ),
                    Row(
                        Column('sitio_web', css_class='col-12'),
                    ),
                ),
                Tab('Personalización',
                    Row(
                        Column('logo', css_class='col-md-6'),
                        Column(HTML('<div class="col-md-6"><label class="form-label">Vista previa del logo:</label><br><img id="logo-preview" src="" alt="Vista previa" class="img-thumbnail" style="max-width: 200px; max-height: 200px; display: none;"></div>'), css_class='col-md-6'),
                    ),
                ),
            ),
            Div(
                HTML('<button type="submit" class="btn btn-primary me-2"><i class="fas fa-save"></i> Guardar</button>'),
                HTML('<a href="{% url "empresas:empresa_list" %}" class="btn btn-secondary"><i class="fas fa-arrow-left"></i> Cancelar</a>'),
                css_class='d-flex justify-content-end mt-3'
            )
        )
        
        # Agregar clases CSS para mejorar el estilo
        for field_name, field in self.fields.items():
            if field_name not in ['logo']:
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'
    
    def clean_rut(self):
        """Validación personalizada del RUT"""
        rut = self.cleaned_data.get('rut')
        if rut:
            # Limpiar el RUT
            rut_limpio = rut.replace('.', '').replace('-', '').strip()
            
            # Validar longitud
            if len(rut_limpio) < 8 or len(rut_limpio) > 9:
                raise ValidationError('El RUT debe tener entre 8 y 9 dígitos')
            
            # Validar que solo contenga números y K
            if not rut_limpio[:-1].isdigit() or not (rut_limpio[-1].isdigit() or rut_limpio[-1].upper() == 'K'):
                raise ValidationError('El RUT contiene caracteres inválidos')
            
            # Formatear el RUT
            if len(rut_limpio) >= 8:
                numero = rut_limpio[:-1]
                dv = rut_limpio[-1].upper()
                
                # Formatear número con puntos
                numero_formateado = ''
                for i, digito in enumerate(reversed(numero)):
                    if i > 0 and i % 3 == 0:
                        numero_formateado = '.' + numero_formateado
                    numero_formateado = digito + numero_formateado
                
                rut_formateado = numero_formateado + '-' + dv
                return rut_formateado
        
        return rut


class SucursalForm(forms.ModelForm):
    """Formulario para crear y editar sucursales"""
    
    class Meta:
        model = Sucursal
        fields = [
            'nombre', 'codigo', 'direccion', 'comuna', 'ciudad', 'region',
            'telefono', 'email', 'es_principal', 'horario_apertura', 
            'horario_cierre', 'gerente', 'telefono_gerente', 'estado'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese el nombre de la sucursal'
            }),
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: SUC001'
            }),
            'direccion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ingrese la dirección de la sucursal'
            }),
            'comuna': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese la comuna'
            }),
            'ciudad': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese la ciudad'
            }),
            'region': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese la región'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+56 9 1234 5678'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'sucursal@empresa.com'
            }),
            'es_principal': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'horario_apertura': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'horario_cierre': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'gerente': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del gerente'
            }),
            'telefono_gerente': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+56 9 1234 5678'
            }),
            'estado': forms.Select(attrs={
                'class': 'form-control'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('nombre', css_class='col-md-6'),
                Column('codigo', css_class='col-md-6'),
            ),
            Row(
                Column('direccion', css_class='col-12'),
            ),
            Row(
                Column('comuna', css_class='col-md-4'),
                Column('ciudad', css_class='col-md-4'),
                Column('region', css_class='col-md-4'),
            ),
            Row(
                Column('telefono', css_class='col-md-6'),
                Column('email', css_class='col-md-6'),
            ),
            Row(
                Column('es_principal', css_class='col-md-6'),
                Column('estado', css_class='col-md-6'),
            ),
            Row(
                Column('horario_apertura', css_class='col-md-6'),
                Column('horario_cierre', css_class='col-md-6'),
            ),
            Row(
                Column('gerente', css_class='col-md-6'),
                Column('telefono_gerente', css_class='col-md-6'),
            ),
            Div(
                HTML('<button type="submit" class="btn btn-primary me-2"><i class="fas fa-save"></i> Guardar</button>'),
                HTML('<a href="{% url "empresas:sucursal_list" %}" class="btn btn-secondary"><i class="fas fa-arrow-left"></i> Cancelar</a>'),
                css_class='d-flex justify-content-end mt-3'
            )
        )


class ConfiguracionEmpresaForm(forms.ModelForm):
    """Formulario para configurar empresa"""
    
    class Meta:
        model = ConfiguracionEmpresa
        fields = [
            'prefijo_ajustes', 'siguiente_ajuste', 'formato_ajustes',
            'imprimir_logo', 'pie_pagina_documentos',
            'alerta_stock_minimo', 'notificar_vencimientos',
            'respaldo_automatico', 'frecuencia_respaldo'
        ]
        widgets = {
            'prefijo_ajustes': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': 10
            }),
            'siguiente_ajuste': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'formato_ajustes': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: {prefijo}-{000}'
            }),
            'imprimir_logo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'pie_pagina_documentos': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'alerta_stock_minimo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notificar_vencimientos': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'respaldo_automatico': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'frecuencia_respaldo': forms.Select(attrs={
                'class': 'form-control'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            TabHolder(
                Tab('Folios y Correlativos',
                    HTML('<div class="alert alert-info"><i class="fas fa-info-circle me-2"></i>Configure la numeración para los ajustes de stock.</div>'),
                    Row(
                        Column('prefijo_ajustes', css_class='col-md-4'),
                        Column('siguiente_ajuste', css_class='col-md-4'),
                        Column('formato_ajustes', css_class='col-md-4'),
                    ),
                    HTML('<div class="mt-3"><small class="text-muted"><strong>Variables disponibles:</strong> {prefijo} = Prefijo configurado, {000} = Número con ceros a la izquierda</small></div>'),
                ),
                Tab('Documentos',
                    Row(
                        Column('imprimir_logo', css_class='col-md-6'),
                        Column('pie_pagina_documentos', css_class='col-12'),
                    ),
                ),
                Tab('Notificaciones',
                    Row(
                        Column('alerta_stock_minimo', css_class='col-md-6'),
                        Column('notificar_vencimientos', css_class='col-md-6'),
                    ),
                ),
                Tab('Respaldo',
                    Row(
                        Column('respaldo_automatico', css_class='col-md-6'),
                        Column('frecuencia_respaldo', css_class='col-md-6'),
                    ),
                ),
            ),
            Div(
                HTML('<button type="submit" class="btn btn-primary me-2"><i class="fas fa-save"></i> Guardar Configuración</button>'),
                HTML('<a href="{% url "empresas:empresa_list" %}" class="btn btn-secondary"><i class="fas fa-arrow-left"></i> Volver</a>'),
                css_class='d-flex justify-content-end mt-3'
            )
        )
