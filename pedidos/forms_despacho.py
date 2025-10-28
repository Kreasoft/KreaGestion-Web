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
            'orden_pedido', 'fecha_despacho', 'tipo_documento',
            'fecha_entrega_estimada', 'chofer', 'vehiculo', 'transportista_externo',
            'direccion_entrega', 'observaciones'
        ]
        widgets = {
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

        # Si se está creando desde un pedido específico, ocultar el campo
        if self.initial.get('orden_pedido'):
            self.fields['orden_pedido'].widget = forms.HiddenInput()
        elif empresa:
            from .models_transporte import Chofer, Vehiculo
            
            # Filtrar solo pedidos de la empresa para selección manual
            self.fields['orden_pedido'].queryset = OrdenPedido.objects.filter(
                empresa=empresa,
                estado__in=['confirmada', 'en_proceso'] # Solo mostrar pedidos que pueden ser despachados
            ).select_related('cliente')
            
            # Filtrar choferes y vehículos por empresa
            self.fields['chofer'].queryset = Chofer.objects.filter(
                empresa=empresa,
                activo=True
            ).order_by('nombre')
            
            self.fields['vehiculo'].queryset = Vehiculo.objects.filter(
                empresa=empresa,
                activo=True
            ).order_by('patente')


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
            # Excluir la instancia actual si se está editando para no contarla dos veces
            instance = self.instance
            despachos_previos = item_pedido.despachos.exclude(
                orden_despacho__estado='cancelado'
            )
            if instance and instance.pk:
                despachos_previos = despachos_previos.exclude(pk=instance.pk)

            total_despachado_previo = despachos_previos.aggregate(
                total=models.Sum('cantidad')
            )['total'] or 0

            cantidad_pendiente = item_pedido.cantidad - total_despachado_previo

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
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)

