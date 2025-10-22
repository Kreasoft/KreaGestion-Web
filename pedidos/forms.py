from django import forms
from django.forms import inlineformset_factory
from .models import OrdenPedido, ItemOrdenPedido
from clientes.models import Cliente
from bodegas.models import Bodega


class OrdenPedidoForm(forms.ModelForm):
    """Formulario para crear/editar órdenes de pedido"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ['fecha_pedido', 'fecha_entrega_estimada', 'fecha_oc_cliente']:
            if f in self.fields:
                self.fields[f].input_formats = ['%Y-%m-%d']

    class Meta:
        model = OrdenPedido
        fields = [
            'cliente', 'bodega', 'fecha_pedido', 'fecha_entrega_estimada',
            'numero_oc_cliente', 'fecha_oc_cliente', 'condiciones_pago',
            'observaciones', 'estado'
        ]
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'bodega': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'fecha_pedido': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
            'fecha_entrega_estimada': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
            'numero_oc_cliente': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'N° OC del cliente'}),
            'fecha_oc_cliente': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
            'condiciones_pago': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Ej: 30 días'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3, 'placeholder': 'Observaciones adicionales'}),
            'estado': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        }


class ItemOrdenPedidoForm(forms.ModelForm):
    """Formulario para items de orden de pedido"""
    
    class Meta:
        model = ItemOrdenPedido
        fields = ['articulo', 'cantidad', 'precio_unitario', 'descuento_porcentaje', 'impuesto_porcentaje', 'observaciones']
        widgets = {
            'articulo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-center', 'min': '1'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'min': '0', 'step': '1'}),
            'descuento_porcentaje': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-center', 'min': '0', 'max': '100'}),
            'impuesto_porcentaje': forms.HiddenInput(),
            'observaciones': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Observaciones'}),
        }


# Formset para items
ItemOrdenPedidoFormSet = inlineformset_factory(
    OrdenPedido,
    ItemOrdenPedido,
    form=ItemOrdenPedidoForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class BusquedaPedidoForm(forms.Form):
    """Formulario de búsqueda de pedidos"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Buscar por número, cliente...'
        })
    )
    
    estado = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos los estados')] + OrdenPedido.ESTADO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    cliente = forms.ModelChoiceField(
        required=False,
        queryset=Cliente.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        empty_label='Todos los clientes'
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-sm',
            'type': 'date'
        })
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-sm',
            'type': 'date'
        })
    )
