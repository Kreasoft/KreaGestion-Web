"""
Formularios para gestionar Hojas de Ruta
"""
from django import forms
from django.utils import timezone
from .models_rutas import HojaRuta
from .models_transporte import Vehiculo, Chofer


class HojaRutaForm(forms.ModelForm):
    """
    Formulario para crear y editar hojas de ruta
    Las hojas de ruta son por día, con vehículo, chofer y acompañante editables
    """
    
    class Meta:
        model = HojaRuta
        fields = [
            'ruta', 'fecha', 'vehiculo', 'chofer', 'acompanante',
            'estado', 'observaciones'
        ]
        widgets = {
            'ruta': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'fecha': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
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
            'estado': forms.Select(attrs={
                'class': 'form-control'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones adicionales...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar por empresa
        if self.empresa:
            # Solo rutas activas
            from .models_rutas import Ruta
            self.fields['ruta'].queryset = Ruta.objects.filter(
                empresa=self.empresa,
                activo=True
            ).order_by('codigo')
            
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
        self.fields['observaciones'].required = False
        
        # Si es edición y tiene ruta, establecer valores por defecto
        if self.instance and self.instance.pk and self.instance.ruta:
            ruta = self.instance.ruta
            if not self.initial.get('vehiculo') and ruta.vehiculo:
                self.initial['vehiculo'] = ruta.vehiculo.pk
            if not self.initial.get('chofer') and ruta.chofer:
                self.initial['chofer'] = ruta.chofer.pk
            if not self.initial.get('acompanante') and ruta.acompanante:
                self.initial['acompanante'] = ruta.acompanante.pk
        
        # Si es creación y hay datos POST, intentar cargar valores por defecto de la ruta
        if not self.instance.pk and self.data and self.data.get('ruta'):
            try:
                from .models_rutas import Ruta
                ruta_id = self.data.get('ruta')
                ruta = Ruta.objects.filter(pk=ruta_id, empresa=self.empresa).first()
                if ruta:
                    if ruta.vehiculo and not self.data.get('vehiculo'):
                        self.initial['vehiculo'] = ruta.vehiculo.pk
                    if ruta.chofer and not self.data.get('chofer'):
                        self.initial['chofer'] = ruta.chofer.pk
                    if ruta.acompanante and not self.data.get('acompanante'):
                        self.initial['acompanante'] = ruta.acompanante.pk
            except (ValueError, TypeError):
                pass
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.empresa and not instance.empresa_id:
            instance.empresa = self.empresa
        if commit:
            instance.save()
        return instance

