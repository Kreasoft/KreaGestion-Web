"""
Formularios para gestionar Vehículos y Choferes
"""
from django import forms
from .models_transporte import Vehiculo, Chofer


class VehiculoForm(forms.ModelForm):
    """
    Formulario para crear y editar vehículos
    """
    
    class Meta:
        model = Vehiculo
        fields = ['patente', 'descripcion', 'capacidad', 'chofer', 'activo']
        widgets = {
            'patente': forms.TextInput(attrs={
                'class': 'form-control text-uppercase',
                'placeholder': 'Ej: ABCD12',
                'maxlength': '10'
            }),
            'descripcion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Camión Toyota Hilux 2020'
            }),
            'capacidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Capacidad en kg',
                'step': '0.01'
            }),
            'chofer': forms.Select(attrs={
                'class': 'form-control'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar choferes por empresa y solo choferes activos
        if self.empresa:
            self.fields['chofer'].queryset = Chofer.objects.filter(
                empresa=self.empresa,
                tipo='chofer',
                activo=True
            ).order_by('codigo')
        
        # Hacer chofer opcional
        self.fields['chofer'].required = False
        
        # Convertir patente a mayúsculas
        if 'patente' in self.data:
            data = self.data.copy()
            data['patente'] = data['patente'].upper()
            self.data = data
    
    def clean_patente(self):
        patente = self.cleaned_data.get('patente', '').upper()
        
        if self.empresa:
            # Verificar si ya existe otro vehículo con esta patente en la misma empresa
            qs = Vehiculo.objects.filter(empresa=self.empresa, patente=patente)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise forms.ValidationError(
                    f'Ya existe un vehículo con la patente {patente} en esta empresa.'
                )
        
        return patente
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.empresa and not instance.empresa_id:
            instance.empresa = self.empresa
        if commit:
            instance.save()
        return instance


class ChoferForm(forms.ModelForm):
    """
    Formulario para crear y editar choferes
    """
    
    class Meta:
        model = Chofer
        fields = ['codigo', 'nombre', 'rut', 'tipo', 'activo']
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: CH001'
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre completo del chofer'
            }),
            'rut': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 12345678-9',
                'maxlength': '12'
            }),
            'tipo': forms.Select(attrs={
                'class': 'form-control'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
    
    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo', '')
        
        if self.empresa:
            # Verificar si ya existe otro chofer con este código en la misma empresa
            qs = Chofer.objects.filter(empresa=self.empresa, codigo=codigo)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise forms.ValidationError(
                    f'Ya existe un chofer con el código {codigo} en esta empresa.'
                )
        
        return codigo
    
    def clean_rut(self):
        rut = self.cleaned_data.get('rut', '')
        
        if self.empresa:
            # Verificar si ya existe otro chofer con este RUT en la misma empresa
            qs = Chofer.objects.filter(empresa=self.empresa, rut=rut)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise forms.ValidationError(
                    f'Ya existe un chofer con el RUT {rut} en esta empresa.'
                )
        
        return rut
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.empresa and not instance.empresa_id:
            instance.empresa = self.empresa
        if commit:
            instance.save()
        return instance
