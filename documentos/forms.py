from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from .models import DocumentoCompra, ItemDocumentoCompra, HistorialPagoDocumento
from proveedores.models import Proveedor
from articulos.models import Articulo
from bodegas.models import Bodega


class DocumentoCompraForm(forms.ModelForm):
    """Formulario para crear y editar documentos de compra"""
    
    class Meta:
        model = DocumentoCompra
        fields = [
            'tipo_documento', 'proveedor', 'bodega', 
            'numero_documento', 'fecha_emision', 
            'fecha_vencimiento', 'estado_documento', 'estado_pago',
            'observaciones'
        ]
        widgets = {
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'proveedor': forms.Select(attrs={'class': 'form-select'}),
            'bodega': forms.Select(attrs={'class': 'form-select'}),
            'numero_documento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 0001-00012345'}),
            'fecha_emision': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_vencimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'estado_documento': forms.Select(attrs={'class': 'form-select'}),
            'estado_pago': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Ingrese observaciones adicionales sobre el documento...'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        # Configurar querysets por empresa
        if self.empresa:
            self.fields['proveedor'].queryset = Proveedor.objects.filter(empresa=self.empresa)
            self.fields['bodega'].queryset = Bodega.objects.filter(empresa=self.empresa)
        
        # Hacer campos requeridos
        for field_name in ['tipo_documento', 'proveedor', 'bodega', 'numero_documento', 'fecha_emision']:
            self.fields[field_name].required = True
        
        # Establecer fecha de emisión por defecto si no hay valor
        if not self.instance.pk and not self.initial.get('fecha_emision'):
            from datetime import date
            self.initial['fecha_emision'] = date.today()
    
    def clean_numero_documento(self):
        numero_documento = self.cleaned_data.get('numero_documento')
        tipo_documento = self.cleaned_data.get('tipo_documento')
        empresa = self.empresa
        
        if numero_documento and tipo_documento and empresa:
            # Verificar unicidad por empresa, tipo y número
            queryset = DocumentoCompra.objects.filter(
                empresa=empresa,
                tipo_documento=tipo_documento,
                numero_documento=numero_documento
            )
            
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise ValidationError(f'Ya existe un {self.get_tipo_documento_display()} con el número {numero_documento} en esta empresa.')
        
        return numero_documento


class ItemDocumentoCompraForm(forms.ModelForm):
    """Formulario para items de documento de compra"""
    
    class Meta:
        model = ItemDocumentoCompra
        fields = [
            'articulo', 'cantidad', 
            'precio_unitario', 'descuento_porcentaje', 'impuesto_porcentaje'
        ]
        widgets = {
            'articulo': forms.Select(attrs={'class': 'form-select articulo-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control cantidad-input', 'min': '1', 'value': '1'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control precio-input', 'min': '0', 'placeholder': 'Precio sin decimales'}),
            'descuento_porcentaje': forms.NumberInput(attrs={'class': 'form-control descuento-input', 'min': '0', 'max': '100', 'value': '0'}),
            'impuesto_porcentaje': forms.NumberInput(attrs={'class': 'form-control impuesto-input', 'min': '0', 'value': '19'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Hacer que impuesto_porcentaje no sea requerido
        self.fields['impuesto_porcentaje'].required = False
        self.fields['descuento_porcentaje'].required = False
        
        # Configurar el queryset de artículos por empresa
        # Esto se hará en la vista pasando la empresa al contexto
    
    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad and cantidad <= 0:
            raise ValidationError('La cantidad debe ser mayor a 0.')
        return cantidad
    
    def clean_precio_unitario(self):
        precio = self.cleaned_data.get('precio_unitario')
        if precio and precio < 0:
            raise ValidationError('El precio no puede ser negativo.')
        return precio
    
    def clean_descuento_porcentaje(self):
        descuento = self.cleaned_data.get('descuento_porcentaje')
        if descuento and descuento < 0:
            raise ValidationError('El descuento no puede ser negativo.')
        if descuento and descuento > 100:
            raise ValidationError('El descuento no puede ser mayor al 100%.')
        return descuento


# Formset para items del documento
ItemDocumentoCompraFormSet = inlineformset_factory(
    DocumentoCompra,
    ItemDocumentoCompra,
    form=ItemDocumentoCompraForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class HistorialPagoDocumentoForm(forms.ModelForm):
    """Formulario para registrar pagos de documentos"""
    
    METODO_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia Bancaria'),
        ('cheque', 'Cheque'),
        ('tarjeta_credito', 'Tarjeta de Crédito'),
        ('tarjeta_debito', 'Tarjeta de Débito'),
        ('otro', 'Otro'),
    ]
    
    metodo_pago = forms.ChoiceField(choices=METODO_PAGO_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    
    class Meta:
        model = HistorialPagoDocumento
        fields = ['fecha_pago', 'monto_pagado', 'metodo_pago', 'observaciones']
        widgets = {
            'fecha_pago': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'monto_pagado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def clean_monto_pagado(self):
        monto = self.cleaned_data.get('monto_pagado')
        if monto and monto <= 0:
            raise ValidationError('El monto debe ser mayor a 0.')
        return monto


class BusquedaDocumentoForm(forms.Form):
    """Formulario de búsqueda para documentos de compra"""
    
    TIPO_DOCUMENTO_CHOICES = [
        ('', 'Todos los tipos'),
        ('factura', 'Factura'),
        ('guia_despacho', 'Guía de Despacho'),
        ('nota_credito', 'Nota de Crédito'),
        ('nota_debito', 'Nota de Débito'),
        ('boleta', 'Boleta'),
        ('factura_exenta', 'Factura Exenta'),
        ('recibo', 'Recibo'),
    ]
    
    ESTADO_DOCUMENTO_CHOICES = [
        ('', 'Todos los estados'),
        ('borrador', 'Borrador'),
        ('pendiente', 'Pendiente'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
        ('anulado', 'Anulado'),
    ]
    
    ESTADO_PAGO_CHOICES = [
        ('', 'Todos los estados de pago'),
        ('pagada', 'Pagada'),
        ('credito', 'Crédito'),
        ('parcial', 'Pago Parcial'),
        ('vencida', 'Vencida'),
    ]
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por número, proveedor, RUT...'
        })
    )
    
    tipo_documento = forms.ChoiceField(
        choices=TIPO_DOCUMENTO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    estado_documento = forms.ChoiceField(
        choices=ESTADO_DOCUMENTO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    estado_pago = forms.ChoiceField(
        choices=ESTADO_PAGO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    proveedor = forms.ModelChoiceField(
        queryset=Proveedor.objects.none(),
        required=False,
        empty_label="Todos los proveedores",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if empresa:
            self.fields['proveedor'].queryset = Proveedor.objects.filter(empresa=empresa)
