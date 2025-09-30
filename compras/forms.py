from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from .models import OrdenCompra, ItemOrdenCompra, RecepcionMercancia, ItemRecepcion
# from proveedores.models import Proveedor  # Temporal
from articulos.models import Articulo
from empresas.models import Sucursal


class OrdenCompraForm(forms.ModelForm):
    """Formulario para crear y editar órdenes de compra"""
    
    class Meta:
        model = OrdenCompra
        fields = [
            'proveedor', 'sucursal', 'numero_orden', 'fecha_orden', 
            'fecha_entrega_esperada', 'estado', 'prioridad', 'observaciones',
            'condiciones_pago', 'plazo_entrega'
        ]
        widgets = {
            'proveedor': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del proveedor'}),
            'sucursal': forms.Select(attrs={'class': 'form-select'}),
            'numero_orden': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'fecha_orden': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_entrega_esperada': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'prioridad': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'condiciones_pago': forms.TextInput(attrs={'class': 'form-control'}),
            'plazo_entrega': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        # Configurar sucursales por empresa
        if self.empresa:
            self.fields['sucursal'].queryset = Sucursal.objects.filter(empresa=self.empresa)
        
        # Generar número de orden automáticamente
        if not self.instance.pk:
            ultima_orden = OrdenCompra.objects.filter(empresa=self.empresa).order_by('-numero_orden').first()
            if ultima_orden:
                try:
                    numero = int(ultima_orden.numero_orden) + 1
                except ValueError:
                    numero = 1
            else:
                numero = 1
            self.fields['numero_orden'].initial = f"{numero:06d}"


class ItemOrdenCompraForm(forms.ModelForm):
    """Formulario para items de orden de compra"""
    
    class Meta:
        model = ItemOrdenCompra
        fields = [
            'articulo', 'cantidad_solicitada', 'precio_unitario', 
            'descuento_unitario', 'especificaciones', 'fecha_entrega_item'
        ]
        widgets = {
            'articulo': forms.Select(attrs={'class': 'form-select articulo-select'}),
            'cantidad_solicitada': forms.NumberInput(attrs={'class': 'form-control cantidad-input', 'step': '0.01'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control precio-input', 'step': '0.01'}),
            'descuento_unitario': forms.NumberInput(attrs={'class': 'form-control descuento-input', 'step': '0.01', 'value': '0.00'}),
            'especificaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'fecha_entrega_item': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrar artículos por empresa - esto se hará en la vista
        # La empresa se pasará a través del contexto del template
    
    def clean_cantidad_solicitada(self):
        cantidad = self.cleaned_data.get('cantidad_solicitada')
        if cantidad and cantidad <= 0:
            raise ValidationError('La cantidad debe ser mayor a 0.')
        return cantidad
    
    def clean_precio_unitario(self):
        precio = self.cleaned_data.get('precio_unitario')
        if precio and precio <= 0:
            raise ValidationError('El precio debe ser mayor a 0.')
        return precio


# Formset para manejar múltiples items
ItemOrdenCompraFormSet = inlineformset_factory(
    OrdenCompra,
    ItemOrdenCompra,
    form=ItemOrdenCompraForm,
    extra=1,
    can_delete=True,
    fields=[
        'articulo', 'cantidad_solicitada', 'precio_unitario', 
        'descuento_unitario', 'especificaciones', 'fecha_entrega_item'
    ]
)


class RecepcionMercanciaForm(forms.ModelForm):
    """Formulario para crear recepciones de mercancía"""
    
    class Meta:
        model = RecepcionMercancia
        fields = [
            'numero_recepcion', 'fecha_recepcion', 'estado',
            'transportista', 'numero_guia', 'observaciones'
        ]
        widgets = {
            'numero_recepcion': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'fecha_recepcion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'transportista': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_guia': forms.TextInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.orden_compra = kwargs.pop('orden_compra', None)
        super().__init__(*args, **kwargs)
        
        # Generar número de recepción automáticamente
        if not self.instance.pk:
            ultima_recepcion = RecepcionMercancia.objects.order_by('-numero_recepcion').first()
            if ultima_recepcion:
                try:
                    numero = int(ultima_recepcion.numero_recepcion) + 1
                except ValueError:
                    numero = 1
            else:
                numero = 1
            self.fields['numero_recepcion'].initial = f"{numero:06d}"


class ItemRecepcionForm(forms.ModelForm):
    """Formulario para items de recepción"""
    
    class Meta:
        model = ItemRecepcion
        fields = [
            'item_orden', 'cantidad_recibida', 'calidad_aceptable', 
            'observaciones_calidad'
        ]
        widgets = {
            'item_orden': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_recibida': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'calidad_aceptable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observaciones_calidad': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # La orden de compra se pasará a través del contexto del template
    
    def clean_cantidad_recibida(self):
        cantidad = self.cleaned_data.get('cantidad_recibida')
        item_orden = self.cleaned_data.get('item_orden')
        
        if cantidad and cantidad <= 0:
            raise ValidationError('La cantidad debe ser mayor a 0.')
        
        if cantidad and item_orden:
            cantidad_pendiente = item_orden.get_cantidad_pendiente()
            if cantidad > cantidad_pendiente:
                raise ValidationError(f'La cantidad recibida no puede ser mayor a la pendiente ({cantidad_pendiente}).')
        
        return cantidad


# Formset para manejar múltiples items de recepción
ItemRecepcionFormSet = inlineformset_factory(
    RecepcionMercancia,
    ItemRecepcion,
    form=ItemRecepcionForm,
    extra=0,
    can_delete=False,
    fields=[
        'item_orden', 'cantidad_recibida', 'calidad_aceptable', 
        'observaciones_calidad'
    ]
)


class BusquedaOrdenForm(forms.Form):
    """Formulario para buscar órdenes de compra"""
    
    ESTADO_CHOICES = [
        ('', 'Todos los estados'),
        ('borrador', 'Borrador'),
        ('pendiente_aprobacion', 'Pendiente de Aprobación'),
        ('aprobada', 'Aprobada'),
        ('en_proceso', 'En Proceso'),
        ('parcialmente_recibida', 'Parcialmente Recibida'),
        ('completamente_recibida', 'Completamente Recibida'),
        ('cancelada', 'Cancelada'),
        ('cerrada', 'Cerrada'),
    ]
    
    PRIORIDAD_CHOICES = [
        ('', 'Todas las prioridades'),
        ('baja', 'Baja'),
        ('normal', 'Normal'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]
    
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por número, proveedor o artículo...'
        })
    )
    
    estado = forms.ChoiceField(
        choices=ESTADO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    prioridad = forms.ChoiceField(
        choices=PRIORIDAD_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
