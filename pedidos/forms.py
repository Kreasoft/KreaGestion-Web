from django import forms
from decimal import Decimal
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
            'bodega': forms.Select(attrs={'class': 'form-select form-select-sm bodega-select'}),
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
    
    # Usamos IntegerField para evitar problemas de localización (unto vs coma) en inputs ocultos.
    # El modelo lo guardará correctamente como Decimal.
    impuesto_porcentaje = forms.IntegerField(
        initial=19, 
        widget=forms.HiddenInput(), 
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        # Si el valor es nulo (por ejemplo en edición), forzamos 19
        if self.instance and self.instance.pk and self.instance.impuesto_porcentaje is None:
            self.fields['impuesto_porcentaje'].initial = 19

        from articulos.models import Articulo
        self.fields['articulo'].queryset = Articulo.objects.all()
    
    def clean_impuesto_porcentaje(self):
        """Asegurar que el impuesto nunca sea nulo para evitar errores de BD"""
        impuesto = self.cleaned_data.get('impuesto_porcentaje')
        if impuesto is None:
            return 19
        return impuesto
    
    class Meta:
        model = ItemOrdenPedido
        fields = ['articulo', 'cantidad', 'precio_unitario', 'descuento_porcentaje', 'impuesto_porcentaje', 'observaciones']
        widgets = {
            'articulo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-center', 'min': '1'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'min': '0', 'step': '1'}),
            'descuento_porcentaje': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-center', 'min': '0', 'max': '100'}),
            'observaciones': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Observaciones'}),
        }


# Formset personalizado para pasar la empresa
class BaseItemOrdenPedidoFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
    
    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs['empresa'] = self.empresa
        return kwargs

# Formset para items
ItemOrdenPedidoFormSet = inlineformset_factory(
    OrdenPedido,
    ItemOrdenPedido,
    form=ItemOrdenPedidoForm,
    formset=BaseItemOrdenPedidoFormSet,
    extra=1,
    can_delete=True
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
