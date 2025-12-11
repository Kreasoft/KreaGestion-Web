"""
Formularios para gestionar Rutas
"""
from django import forms
from .models_rutas import Ruta
from .models_transporte import Vehiculo, Chofer


class RutaForm(forms.ModelForm):
    """
    Formulario para crear y editar rutas
    Las rutas son diarias y por móvil, con chofer y acompañante asignados
    """
    
    class Meta:
        model = Ruta
        fields = [
            'codigo', 'nombre', 'descripcion', 
            'vehiculo', 'chofer', 'acompanante',
            'dias_visita', 'orden_visita', 'activo'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: RUTA-01, NORTE-01',
                'required': True
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Ruta Norte, Ruta Centro',
                'required': True
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción detallada de la ruta, zonas que cubre, etc.'
            }),
            'vehiculo': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'chofer': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'acompanante': forms.Select(attrs={
                'class': 'form-control'
            }),
            'dias_visita': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Lunes, Miércoles, Viernes'
            }),
            'orden_visita': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'placeholder': 'Orden de visita (1, 2, 3...)'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar vehículos y choferes por empresa
        if self.empresa:
            # Solo vehículos activos
            self.fields['vehiculo'].queryset = Vehiculo.objects.filter(
                empresa=self.empresa,
                activo=True
            ).order_by('patente')
            
            # Solo choferes activos
            self.fields['chofer'].queryset = Chofer.objects.filter(
                empresa=self.empresa,
                tipo='chofer',
                activo=True
            ).order_by('codigo')
            
            # Solo acompañantes activos
            self.fields['acompanante'].queryset = Chofer.objects.filter(
                empresa=self.empresa,
                tipo='acompanante',
                activo=True
            ).order_by('codigo')
        
        # Hacer campos opcionales
        self.fields['acompanante'].required = False
        self.fields['descripcion'].required = False
        self.fields['dias_visita'].required = False
    
    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo', '')
        
        if self.empresa:
            # Verificar si ya existe otra ruta con este código en la misma empresa
            qs = Ruta.objects.filter(empresa=self.empresa, codigo=codigo)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise forms.ValidationError(
                    f'Ya existe una ruta con el código {codigo} en esta empresa.'
                )
        
        return codigo
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.empresa and not instance.empresa_id:
            instance.empresa = self.empresa
        if commit:
            instance.save()
        return instance

