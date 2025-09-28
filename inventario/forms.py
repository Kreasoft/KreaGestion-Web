from django import forms
from django.core.exceptions import ValidationError
from .models import Inventario, Stock
from bodegas.models import Bodega
from articulos.models import Articulo
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, Fieldset, HTML, Div, Submit
from crispy_forms.bootstrap import Tab, TabHolder


class InventarioForm(forms.ModelForm):
    """Formulario para crear y editar movimientos de inventario"""
    
    class Meta:
        model = Inventario
        fields = [
            'bodega_destino', 'bodega_origen', 'articulo', 'tipo_movimiento', 'cantidad', 
            'precio_unitario', 'descripcion', 'motivo', 'numero_documento', 'proveedor', 
            'estado'
        ]
        widgets = {
            'bodega_destino': forms.Select(attrs={'class': 'form-control'}),
            'bodega_origen': forms.Select(attrs={'class': 'form-control'}),
            'articulo': forms.Select(attrs={'class': 'form-control'}),
            'tipo_movimiento': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descripción breve del movimiento'}),
            'motivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ingrese el motivo del movimiento'}),
            'numero_documento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número de documento (opcional)'}),
            'proveedor': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del proveedor (opcional)'}),
            'estado': forms.Select(attrs={'class': 'form-control'})
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['bodega_destino'].queryset = Bodega.objects.filter(empresa=self.empresa, activa=True)
            self.fields['bodega_origen'].queryset = Bodega.objects.filter(empresa=self.empresa, activa=True)
            self.fields['articulo'].queryset = Articulo.objects.filter(empresa=self.empresa, activo=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('bodega_origen', css_class='col-md-6'),
                Column('bodega_destino', css_class='col-md-6'),
            ),
            Row(
                Column('articulo', css_class='col-md-6'),
                Column('tipo_movimiento', css_class='col-md-6'),
            ),
            Row(
                Column('cantidad', css_class='col-md-6'),
                Column('precio_unitario', css_class='col-md-6'),
            ),
            'descripcion',
            'motivo',
            Row(
                Column('numero_documento', css_class='col-md-6'),
                Column('proveedor', css_class='col-md-6'),
            ),
            'estado',
            Div(
                Submit('submit', 'Guardar Movimiento', css_class='btn btn-primary me-2'),
                HTML('<a href="{% url "inventario:inventario_list" %}" class="btn btn-secondary"><i class="fas fa-arrow-left"></i> Cancelar</a>'),
                css_class='d-flex justify-content-end mt-3'
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        tipo_movimiento = cleaned_data.get('tipo_movimiento')
        bodega_origen = cleaned_data.get('bodega_origen')
        bodega_destino = cleaned_data.get('bodega_destino')
        cantidad = cleaned_data.get('cantidad')

        if tipo_movimiento == 'transferencia':
            if not bodega_origen:
                self.add_error('bodega_origen', 'La bodega de origen es requerida para transferencias.')
            if not bodega_destino:
                self.add_error('bodega_destino', 'La bodega de destino es requerida para transferencias.')
            if bodega_origen and bodega_destino and bodega_origen == bodega_destino:
                self.add_error('bodega_destino', 'La bodega de origen y destino no pueden ser la misma.')
        else:
            if tipo_movimiento == 'entrada' and not bodega_destino:
                self.add_error('bodega_destino', 'La bodega de destino es requerida para entradas.')
            if tipo_movimiento == 'salida' and not bodega_origen:
                self.add_error('bodega_origen', 'La bodega de origen es requerida para salidas.')
            
            # Asegurarse de que los campos no relevantes para el tipo de movimiento sean None
            if tipo_movimiento == 'entrada':
                cleaned_data['bodega_origen'] = None
            elif tipo_movimiento == 'salida':
                cleaned_data['bodega_destino'] = None
            elif tipo_movimiento == 'ajuste':
                cleaned_data['bodega_origen'] = None
                cleaned_data['bodega_destino'] = None

        if cantidad and cantidad <= 0:
            self.add_error('cantidad', 'La cantidad debe ser mayor a 0.')
        
        return cleaned_data


class StockForm(forms.ModelForm):
    """Formulario para gestionar el stock de artículos"""
    
    class Meta:
        model = Stock
        fields = [
            'bodega', 'articulo', 'cantidad', 'stock_minimo', 
            'stock_maximo', 'precio_promedio'
        ]
        widgets = {
            'bodega': forms.Select(attrs={
                'class': 'form-control',
            }),
            'articulo': forms.Select(attrs={
                'class': 'form-control',
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'stock_minimo': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'stock_maximo': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'precio_promedio': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar bodegas y artículos por empresa
        if self.empresa:
            self.fields['bodega'].queryset = Bodega.objects.filter(empresa=self.empresa, activa=True)
            self.fields['articulo'].queryset = Articulo.objects.filter(empresa=self.empresa, activo=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('bodega', css_class='col-md-6'),
                Column('articulo', css_class='col-md-6'),
            ),
            Row(
                Column('cantidad', css_class='col-md-6'),
                Column('precio_promedio', css_class='col-md-6'),
            ),
            Row(
                Column('stock_minimo', css_class='col-md-6'),
                Column('stock_maximo', css_class='col-md-6'),
            ),
            Div(
                Submit('submit', 'Guardar Stock', css_class='btn btn-primary me-2'),
                HTML('<a href="{% url "inventario:stock_list" %}" class="btn btn-secondary"><i class="fas fa-arrow-left"></i> Cancelar</a>'),
                css_class='d-flex justify-content-end mt-3'
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        stock_minimo = cleaned_data.get('stock_minimo')
        stock_maximo = cleaned_data.get('stock_maximo')
        
        # Validar que el stock mínimo no sea mayor al máximo
        if stock_minimo and stock_maximo and stock_minimo > stock_maximo:
            raise ValidationError('El stock mínimo no puede ser mayor al stock máximo.')
        
        return cleaned_data


class StockModalForm(forms.ModelForm):
    """Formulario para editar stock en modal (sin precio_promedio)"""
    
    class Meta:
        model = Stock
        fields = [
            'bodega', 'articulo', 'cantidad', 'stock_minimo', 
            'stock_maximo'
        ]
        widgets = {
            'bodega': forms.Select(attrs={
                'class': 'form-control',
            }),
            'articulo': forms.Select(attrs={
                'class': 'form-control',
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'stock_minimo': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'stock_maximo': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar bodegas y artículos por empresa
        if self.empresa:
            self.fields['bodega'].queryset = Bodega.objects.filter(empresa=self.empresa, activa=True)
            self.fields['articulo'].queryset = Articulo.objects.filter(empresa=self.empresa, activo=True)
    
    def clean(self):
        cleaned_data = super().clean()
        stock_minimo = cleaned_data.get('stock_minimo')
        stock_maximo = cleaned_data.get('stock_maximo')
        
        # Validar que el stock mínimo no sea mayor al máximo
        if stock_minimo and stock_maximo and stock_minimo > stock_maximo:
            raise ValidationError('El stock mínimo no puede ser mayor al stock máximo.')
        
        return cleaned_data


class InventarioFilterForm(forms.Form):
    """Formulario para filtrar movimientos de inventario"""
    
    TIPO_MOVIMIENTO_CHOICES = [('', 'Todos los tipos')] + Inventario.TIPO_MOVIMIENTO_CHOICES
    ESTADO_CHOICES = [('', 'Todos los estados')] + Inventario.ESTADO_CHOICES
    
    bodega_destino = forms.ModelChoiceField(
        queryset=Bodega.objects.none(),
        required=False,
        empty_label="Todas las bodegas",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    bodega_origen = forms.ModelChoiceField(
        queryset=Bodega.objects.none(),
        required=False,
        empty_label="Todas las bodegas",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    articulo = forms.ModelChoiceField(
        queryset=Articulo.objects.none(),
        required=False,
        empty_label="Todos los artículos",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    tipo_movimiento = forms.ChoiceField(
        choices=TIPO_MOVIMIENTO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    estado = forms.ChoiceField(
        choices=ESTADO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['bodega_destino'].queryset = Bodega.objects.filter(empresa=self.empresa, activa=True)
            self.fields['bodega_origen'].queryset = Bodega.objects.filter(empresa=self.empresa, activa=True)
            self.fields['articulo'].queryset = Articulo.objects.filter(empresa=self.empresa, activo=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.layout = Layout(
            Row(
                Column('bodega_destino', css_class='col-md-3'),
                Column('bodega_origen', css_class='col-md-3'),
                Column('articulo', css_class='col-md-3'),
                Column('tipo_movimiento', css_class='col-md-3'),
            ),
            Row(
                Column('estado', css_class='col-md-3'),
                Column('fecha_desde', css_class='col-md-3'),
                Column('fecha_hasta', css_class='col-md-3'),
                Column(
                    Submit('submit', 'Filtrar', css_class='btn btn-primary'),
                    css_class='col-md-3 d-flex align-items-end'
                ),
            )
        )