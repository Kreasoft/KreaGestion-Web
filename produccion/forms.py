from django import forms
from articulos.models import RecetaProduccion, InsumoReceta, OrdenProduccion, Articulo
from empresas.models import Sucursal


class RecetaProduccionForm(forms.ModelForm):
    """Formulario para crear/editar recetas de producción"""
    
    class Meta:
        model = RecetaProduccion
        fields = [
            'codigo', 'nombre', 'descripcion', 'producto_final',
            'cantidad_producir', 'merma_estimada', 'tiempo_estimado',
            'temperatura_proceso', 'activo'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: REC-001'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la receta'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción opcional'}),
            'producto_final': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_producir': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'merma_estimada': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'tiempo_estimado': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': 'Minutos'}),
            'temperatura_proceso': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Opcional (°C)'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'codigo': 'Código',
            'nombre': 'Nombre de la Receta',
            'descripcion': 'Descripción',
            'producto_final': 'Producto Final',
            'cantidad_producir': 'Cantidad a Producir',
            'merma_estimada': 'Merma Estimada (%)',
            'tiempo_estimado': 'Tiempo Estimado (minutos)',
            'temperatura_proceso': 'Temperatura de Proceso (°C)',
            'activo': 'Activa',
        }
    
    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if empresa:
            # Filtrar solo artículos de producción
            self.fields['producto_final'].queryset = Articulo.objects.filter(
                empresa=empresa,
                tipo_articulo='produccion',  # Solo artículos de producción
                activo=True
            )


class InsumoRecetaForm(forms.ModelForm):
    """Formulario para agregar insumos a una receta"""
    
    class Meta:
        model = InsumoReceta
        fields = ['articulo', 'cantidad', 'orden', 'notas']
        widgets = {
            'articulo': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Notas opcionales'}),
        }
        labels = {
            'articulo': 'Insumo',
            'cantidad': 'Cantidad Necesaria',
            'orden': 'Orden',
            'notas': 'Notas',
        }
    
    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if empresa:
            # Filtrar solo insumos
            self.fields['articulo'].queryset = Articulo.objects.filter(
                empresa=empresa,
                tipo_articulo__in=['insumo', 'ambos'],
                activo=True
            )


class OrdenProduccionForm(forms.ModelForm):
    """Formulario para crear/editar órdenes de producción"""
    
    class Meta:
        model = OrdenProduccion
        fields = [
            'numero_orden', 'receta', 'sucursal', 'cantidad_planificada',
            'fecha_planificada', 'responsable', 'observaciones',
            'lote_produccion', 'fecha_vencimiento', 'temperatura_proceso'
        ]
        widgets = {
            'numero_orden': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 001'}),
            'receta': forms.Select(attrs={'class': 'form-select'}),
            'sucursal': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_planificada': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'fecha_planificada': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'responsable': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del responsable'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Observaciones opcionales'}),
            'lote_produccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional - Para trazabilidad'}),
            'fecha_vencimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'temperatura_proceso': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Opcional (°C)'}),
        }
        labels = {
            'numero_orden': 'Número de Orden',
            'receta': 'Receta',
            'sucursal': 'Sucursal',
            'cantidad_planificada': 'Cantidad Planificada',
            'fecha_planificada': 'Fecha Planificada',
            'responsable': 'Responsable',
            'observaciones': 'Observaciones',
            'lote_produccion': 'Lote de Producción',
            'fecha_vencimiento': 'Fecha de Vencimiento',
            'temperatura_proceso': 'Temperatura de Proceso (°C)',
        }
    
    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if empresa:
            self.fields['receta'].queryset = RecetaProduccion.objects.filter(
                empresa=empresa,
                activo=True
            )
            self.fields['sucursal'].queryset = Sucursal.objects.filter(
                empresa=empresa,
                activa=True
            )


class FinalizarOrdenForm(forms.Form):
    """Formulario para finalizar una orden de producción"""
    
    cantidad_producida = forms.DecimalField(
        label='Cantidad Producida',
        max_digits=10,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'placeholder': 'Cantidad real producida'
        })
    )
    
    merma_real = forms.DecimalField(
        label='Merma Real',
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'placeholder': 'Merma real (opcional)'
        })
    )
    
    observaciones_finalizacion = forms.CharField(
        label='Observaciones',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Observaciones sobre la producción (opcional)'
        })
    )
