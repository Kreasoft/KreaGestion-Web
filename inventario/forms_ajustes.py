from django import forms
from django.forms import inlineformset_factory
from .models_ajustes import AjusteStock, DetalleAjuste
from .models_correlativos import CorrelativoEmpresa
from bodegas.models import Bodega
from articulos.models import Articulo


class CorrelativoForm(forms.ModelForm):
    """Formulario para configurar correlativos de empresa"""
    
    class Meta:
        model = CorrelativoEmpresa
        fields = ['tipo_documento', 'prefijo', 'numero_actual', 'formato', 'activo']
        widgets = {
            'tipo_documento': forms.Select(attrs={
                'class': 'form-control',
                'readonly': True
            }),
            'prefijo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: AJ, VE, CO'
            }),
            'numero_actual': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': '0'
            }),
            'formato': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '{prefijo}-{numero:04d}'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.instance.pk:
            self.fields['tipo_documento'].widget.attrs['readonly'] = True
            self.fields['tipo_documento'].widget.attrs['class'] += ' bg-light'


class AjusteStockForm(forms.ModelForm):
    """Formulario para crear/editar ajustes de stock"""
    
    class Meta:
        model = AjusteStock
        fields = ['tipo_ajuste', 'fecha_ajuste', 'bodega', 'descripcion']
        widgets = {
            'tipo_ajuste': forms.Select(attrs={
                'class': 'form-control',
                'onchange': 'toggleCantidadSign()'
            }),
            'fecha_ajuste': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'bodega': forms.Select(attrs={
                'class': 'form-control'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Motivo del ajuste (rotura, merma, robo, etc.)'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            # Filtrar bodegas por empresa
            self.fields['bodega'].queryset = Bodega.objects.filter(
                empresa=self.empresa, 
                activa=True
            ).order_by('nombre')
            
            # Establecer fecha actual por defecto
            from django.utils import timezone
            self.fields['fecha_ajuste'].initial = timezone.now()


class DetalleAjusteForm(forms.ModelForm):
    """Formulario para detalles de ajuste"""
    
    class Meta:
        model = DetalleAjuste
        fields = ['articulo', 'cantidad', 'comentario']
        widgets = {
            'articulo': forms.Select(attrs={
                'class': 'form-control articulo-select',
                'onchange': 'cargarInfoArticulo(this)'
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control cantidad-input',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'comentario': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Comentario específico del artículo'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            # Filtrar artículos por empresa
            self.fields['articulo'].queryset = Articulo.objects.filter(
                empresa=self.empresa, 
                activo=True
            ).order_by('codigo')


# Formset para manejar múltiples detalles
DetalleAjusteFormSet = inlineformset_factory(
    AjusteStock,
    DetalleAjuste,
    form=DetalleAjusteForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class AjusteStockFormCompleto(forms.ModelForm):
    """Formulario completo que incluye el formset de detalles"""
    
    class Meta:
        model = AjusteStock
        fields = ['tipo_ajuste', 'fecha_ajuste', 'bodega', 'descripcion']
        widgets = {
            'tipo_ajuste': forms.Select(attrs={
                'class': 'form-control',
                'onchange': 'toggleCantidadSign()'
            }),
            'fecha_ajuste': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'bodega': forms.Select(attrs={
                'class': 'form-control'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Motivo del ajuste (rotura, merma, robo, etc.)'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            # Filtrar bodegas por empresa
            self.fields['bodega'].queryset = Bodega.objects.filter(
                empresa=self.empresa, 
                activa=True
            ).order_by('nombre')
            
            # Establecer fecha actual por defecto
            from django.utils import timezone
            self.fields['fecha_ajuste'].initial = timezone.now()
    
    def get_formset(self, data=None):
        """Retorna el formset de detalles configurado"""
        formset = DetalleAjusteFormSet(
            data=data,
            instance=self.instance,
            form_kwargs={'empresa': self.empresa}
        )
        return formset


































