"""
Formularios para gestionar Órdenes de Despacho
"""
from django import forms
from django.db import models
from django.forms import inlineformset_factory
from .models_despacho import OrdenDespacho, DetalleOrdenDespacho
from .models import OrdenPedido


class OrdenDespachoForm(forms.ModelForm):
    """Formulario para crear/editar órdenes de despacho"""
    
    TIPO_DOCUMENTO_CHOICES = [
        ('guia', 'Guía de Despacho'),
        ('factura', 'Factura Electrónica'),
    ]
    tipo_documento = forms.ChoiceField(
        choices=TIPO_DOCUMENTO_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        required=True,
        label="Documento a Generar"
    )
    
    class Meta:
        model = OrdenDespacho
        fields = [
            'orden_pedido', 'fecha_despacho', 'fecha_entrega_estimada',
            'estado', 'chofer', 'vehiculo', 'transportista_externo',
            'tipo_documento', 'direccion_entrega', 'observaciones', 'tipo_traslado'
        ]
        widgets = {
            'tipo_traslado': forms.Select(attrs={
                'class': 'form-select form-select-sm',
                'id': 'id_tipo_traslado'
            }),
            'orden_pedido': forms.Select(attrs={
                'class': 'form-select form-select-sm',
                'id': 'id_orden_pedido',
                'required': True
            }),
            'fecha_despacho': forms.DateInput(
                format='%Y-%m-%d',
                attrs={
                    'class': 'form-control form-control-sm',
                    'type': 'date',
                    'required': True
                }
            ),
            'fecha_entrega_estimada': forms.DateInput(attrs={
                'class': 'form-control form-control-sm',
                'type': 'date'
            }),
            'estado': forms.Select(attrs={
                'class': 'form-select form-select-sm'
            }),
            'chofer': forms.Select(attrs={
                'class': 'form-select form-select-sm'
            }),
            'vehiculo': forms.Select(attrs={
                'class': 'form-select form-select-sm'
            }),
            'transportista_externo': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Solo si el transporte es externo'
            }),
            'direccion_entrega': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 2,
                'placeholder': 'Dirección de entrega'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 3,
                'placeholder': 'Observaciones adicionales'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)

        self.fields['estado'].widget = forms.HiddenInput()
        self.fields['estado'].required = False

        if self.instance and self.instance.pk:
            self.fields['tipo_documento'].required = False
            self.fields['tipo_documento'].widget = forms.HiddenInput()

        if empresa:
            from django.db.models import Q
            from .models_transporte import Chofer, Vehiculo

            pedidos_qs = OrdenPedido.con_saldo_pendiente(empresa=empresa)

            pedido_actual_id = None
            if self.data:
                pedido_actual_id = self.data.get(self.add_prefix('orden_pedido'))
            elif self.instance and getattr(self.instance, 'orden_pedido_id', None):
                pedido_actual_id = self.instance.orden_pedido_id
            elif self.initial.get('orden_pedido'):
                inicial = self.initial.get('orden_pedido')
                pedido_actual_id = getattr(inicial, 'pk', inicial)

            if pedido_actual_id:
                pedidos_qs = OrdenPedido.objects.filter(empresa=empresa).filter(
                    Q(pk__in=pedidos_qs.values('pk')) | Q(pk=pedido_actual_id)
                )

            self.fields['orden_pedido'].queryset = pedidos_qs.select_related('cliente').order_by('-fecha_creacion')
            self.fields['chofer'].queryset = Chofer.objects.filter(empresa=empresa, activo=True).order_by('nombre')
            self.fields['vehiculo'].queryset = Vehiculo.objects.filter(empresa=empresa, activo=True).order_by('patente')

        self.fields['orden_pedido'].empty_label = 'Seleccione un pedido'
        self.fields['orden_pedido'].widget.attrs.pop('required', None)

        self.fields['chofer'].required = False
        self.fields['vehiculo'].required = False
        self.fields['tipo_traslado'].required = False
        self.fields['direccion_entrega'].required = False

    def clean_orden_pedido(self):
        pedido = self.cleaned_data.get('orden_pedido')
        if pedido and pedido.estado in ('completada', 'cancelada'):
            raise forms.ValidationError(
                'Este pedido está %s y no admite nuevos despachos.' % pedido.get_estado_display().lower()
            )
        if pedido and not pedido.tiene_saldo_pendiente():
            mismo_pedido = (
                self.instance
                and self.instance.pk
                and self.instance.orden_pedido_id == pedido.pk
            )
            if not mismo_pedido:
                raise forms.ValidationError(
                    'Este pedido no tiene saldo pendiente por despachar.'
                )
        return pedido

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo_documento')
        if tipo == 'guia':
            if not cleaned.get('tipo_traslado'):
                self.add_error('tipo_traslado', 'Obligatorio en guía de despacho.')
            if not cleaned.get('chofer'):
                self.add_error('chofer', 'Obligatorio en guía de despacho.')
            if not cleaned.get('vehiculo'):
                self.add_error('vehiculo', 'Obligatorio en guía de despacho.')
            if not (cleaned.get('direccion_entrega') or '').strip():
                self.add_error('direccion_entrega', 'Obligatorio en guía de despacho.')
        return cleaned


class DetalleOrdenDespachoForm(forms.ModelForm):
    """Formulario para items de orden de despacho"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacemos el campo opcional para la validación inicial,
        # ya que se llena con JS. La validación real se hará en la vista.
        self.fields['item_pedido'].required = False

    def clean(self):
        cleaned_data = super().clean()
        cantidad = cleaned_data.get('cantidad')
        item_pedido = cleaned_data.get('item_pedido')

        if cantidad and item_pedido:
            # Usar la propiedad 'cantidad_pendiente' del modelo que ya hemos creado.
            # Esta propiedad ya calcula correctamente lo que falta por despachar.
            cantidad_pendiente = item_pedido.cantidad_pendiente

            # Si estamos editando un despacho existente, debemos sumar de vuelta la cantidad
            # de este despacho al pendiente, porque la propiedad 'cantidad_pendiente' ya la restó.
            if self.instance and self.instance.pk:
                cantidad_pendiente += self.instance.cantidad

            if cantidad > cantidad_pendiente:
                raise forms.ValidationError(
                    f"La cantidad a despachar ({cantidad}) supera la cantidad pendiente ({cantidad_pendiente}) del pedido."
                )

        return cleaned_data

    class Meta:
        model = DetalleOrdenDespacho
        fields = [
            'item_pedido', 'cantidad', 'guia_despacho', 'factura',
            'lote', 'fecha_vencimiento', 'observaciones'
        ]
        widgets = {
            'item_pedido': forms.HiddenInput(),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'step': '0.01',
                'min': '0.01',
                'required': True
            }),
            'guia_despacho': forms.Select(attrs={
                'class': 'form-select form-select-sm'
            }),
            'factura': forms.Select(attrs={
                'class': 'form-select form-select-sm'
            }),
            'lote': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Número de lote'
            }),
            'fecha_vencimiento': forms.DateInput(attrs={
                'class': 'form-control form-control-sm',
                'type': 'date'
            }),
            'observaciones': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Observaciones'
            }),
        }


# Formset para gestionar múltiples items en una orden de despacho
DetalleOrdenDespachoFormSet = inlineformset_factory(
    OrdenDespacho,
    DetalleOrdenDespacho,
    form=DetalleOrdenDespachoForm,
    extra=0,
    can_delete=True,
    min_num=0,
    validate_min=False,
)

