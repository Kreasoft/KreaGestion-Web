from django import forms
from django.forms import inlineformset_factory
from .models import (
    Vendedor, FormaPago, EstacionTrabajo, PrecioClienteArticulo, 
    NotaCredito, NotaCreditoDetalle, NotaDebito, NotaDebitoDetalle
)


class VendedorForm(forms.ModelForm):
    """Formulario para crear y editar vendedores"""
    
    class Meta:
        model = Vendedor
        fields = ['codigo', 'nombre', 'porcentaje_comision', 'activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: V001'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre completo del vendedor'}),
            'porcentaje_comision': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100', 'step': '0.01'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'codigo': 'Código',
            'nombre': 'Nombre',
            'porcentaje_comision': '% Comisión',
            'activo': 'Activo',
        }


class FormaPagoForm(forms.ModelForm):
    """Formulario para crear y editar formas de pago"""
    
    class Meta:
        model = FormaPago
        fields = ['codigo', 'nombre', 'es_cuenta_corriente', 'requiere_cheque', 'activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: EF, TC, CH'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Efectivo, Tarjeta de Crédito'}),
            'es_cuenta_corriente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'requiere_cheque': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'codigo': 'Código',
            'nombre': 'Nombre',
            'es_cuenta_corriente': 'Es Cuenta Corriente',
            'requiere_cheque': 'Requiere Cheque',
            'activo': 'Activo',
        }


class EstacionTrabajoForm(forms.ModelForm):
    """Formulario para crear y editar estaciones de trabajo"""
    
    class Meta:
        model = EstacionTrabajo
        fields = [
            'numero', 'nombre', 'descripcion',
            'modo_pos', 'correlativo_ticket', 'codigo_comodin',
            'puede_facturar', 'puede_boletar', 'puede_guia', 'puede_cotizar', 'puede_vale',
            'cierre_directo', 'flujo_cierre_directo', 'enviar_sii_directo',
            'max_items_factura', 'max_items_boleta', 'max_items_guia', 'max_items_cotizacion', 'max_items_vale',
            'activo'
        ]
        widgets = {
            'numero': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: EST001'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la estación'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción opcional'}),
            'modo_pos': forms.Select(attrs={'class': 'form-select'}),
            'correlativo_ticket': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'codigo_comodin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 999999 o COMODIN'}),
            'puede_facturar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_boletar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_guia': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_cotizar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_vale': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'cierre_directo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'flujo_cierre_directo': forms.Select(attrs={'class': 'form-select'}),
            'enviar_sii_directo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_items_factura': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'max_items_boleta': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'max_items_guia': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'max_items_cotizacion': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'max_items_vale': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'numero': 'Número',
            'nombre': 'Nombre',
            'descripcion': 'Descripción',
            'modo_pos': 'Modo de Operación POS',
            'correlativo_ticket': 'Correlativo de Ticket',
            'codigo_comodin': 'Código Comodín',
            'puede_facturar': 'Puede Emitir Facturas',
            'puede_boletar': 'Puede Emitir Boletas',
            'puede_guia': 'Puede Emitir Guías',
            'puede_cotizar': 'Puede Emitir Cotizaciones',
            'puede_vale': 'Puede Emitir Vales',
            'cierre_directo': 'Cierre directo (Cerrar y Emitir DTE)',
            'flujo_cierre_directo': 'Flujo para cierre directo',
            'enviar_sii_directo': 'Enviar al SII automáticamente',
            'max_items_factura': 'Máx. Items Factura',
            'max_items_boleta': 'Máx. Items Boleta',
            'max_items_guia': 'Máx. Items Guía',
            'max_items_cotizacion': 'Máx. Items Cotización',
            'max_items_vale': 'Máx. Items Vale',
            'activo': 'Activa',
        }


class PrecioClienteArticuloForm(forms.ModelForm):
    """Formulario para crear y editar precios especiales de artículos por cliente"""
    
    class Meta:
        model = PrecioClienteArticulo
        fields = ['cliente', 'articulo', 'precio_especial']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'articulo': forms.Select(attrs={'class': 'form-select'}),
            'precio_especial': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
        }
        labels = {
            'cliente': 'Cliente',
            'articulo': 'Artículo',
            'precio_especial': 'Precio Especial',
        }


# Estilos terrosos para los formularios de Nota de Crédito
ESTILO_TERROSO = {
    'input': 'form-control',
    'select': 'form-select',
    'textarea': 'form-control',
    'checkbox': 'form-check-input',
    'date': 'form-control',
}


class NotaCreditoForm(forms.ModelForm):
    """Formulario para crear y editar Notas de Crédito"""
    
    class Meta:
        model = NotaCredito
        fields = [
            'fecha', 'cliente', 'vendedor', 'bodega',
            'tipo_nc', 'tipo_doc_afectado', 'numero_doc_afectado',
            'fecha_doc_afectado', 'motivo'
        ]
        widgets = {
            'numero': forms.TextInput(attrs={
                'class': ESTILO_TERROSO['input'],
                'placeholder': 'N° Nota de Crédito',
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'fecha': forms.DateInput(attrs={
                'class': ESTILO_TERROSO['date'],
                'type': 'date',
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'cliente': forms.Select(attrs={
                'class': ESTILO_TERROSO['select'],
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'vendedor': forms.Select(attrs={
                'class': ESTILO_TERROSO['select'],
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'bodega': forms.Select(attrs={
                'class': ESTILO_TERROSO['select'],
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'tipo_nc': forms.RadioSelect(attrs={
                'class': 'form-check-input',
                'style': 'border-color: #8B7355;'
            }),
            'tipo_doc_afectado': forms.Select(attrs={
                'class': ESTILO_TERROSO['select'],
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'numero_doc_afectado': forms.TextInput(attrs={
                'class': ESTILO_TERROSO['input'],
                'placeholder': 'N° Documento',
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'fecha_doc_afectado': forms.DateInput(attrs={
                'class': ESTILO_TERROSO['date'],
                'type': 'date',
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'motivo': forms.Textarea(attrs={
                'class': ESTILO_TERROSO['textarea'],
                'rows': 3,
                'placeholder': 'Describa el motivo de la nota de crédito...',
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
        }
        labels = {
            'numero': 'N° NC',
            'fecha': 'Fecha Emisión',
            'cliente': 'Cliente (RUT - Nombre)',
            'vendedor': 'Vendedor',
            'bodega': 'Bodega',
            'tipo_nc': 'Tipo de Nota (Referencia)',
            'tipo_doc_afectado': 'Documento a Referenciar',
            'numero_doc_afectado': 'N° Documento Referenciado',
            'fecha_doc_afectado': 'Fecha Emisión Doc.',
            'motivo': 'Motivo / Razón',
        }


class NotaCreditoDetalleForm(forms.ModelForm):
    """Formulario para items de Nota de Crédito"""
    cantidad = forms.DecimalField(localize=True, widget=forms.TextInput)
    precio_unitario = forms.DecimalField(localize=True, widget=forms.TextInput)
    
    class Meta:
        model = NotaCreditoDetalle
        fields = ['articulo', 'cantidad', 'precio_unitario', 'descuento']
        widgets = {
            'articulo': forms.Select(attrs={
                'class': 'form-select form-select-sm',
                'style': 'border-color: #D4C4A8; font-size: 0.875rem;'
            }),
            'codigo': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'readonly': 'readonly',
                'style': 'border-color: #D4C4A8; font-size: 0.875rem; background-color: #FAF8F3;'
            }),
            'descripcion': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'style': 'border-color: #D4C4A8; font-size: 0.875rem;'
            }),
            'cantidad': forms.TextInput(attrs={
                'class': 'form-control form-control-sm text-end',
                'style': 'border-color: #D4C4A8; font-size: 0.875rem;'
            }),
            'precio_unitario': forms.TextInput(attrs={
                'class': 'form-control form-control-sm text-end',
                'style': 'border-color: #D4C4A8; font-size: 0.875rem;'
            }),
            'descuento': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm text-end',
                'min': '0',
                'max': '100',
                'step': '0.01',
                'style': 'border-color: #D4C4A8; font-size: 0.875rem;'
            }),
        }


# Formset para los detalles de Nota de Crédito
NotaCreditoDetalleFormSet = inlineformset_factory(
    NotaCredito,
    NotaCreditoDetalle,
    form=NotaCreditoDetalleForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class NotaDebitoForm(forms.ModelForm):
    """Formulario para Notas de Débito con Estilo Terroso"""
    class Meta:
        model = NotaDebito
        fields = [
            'empresa', 'sucursal', 'numero', 'fecha', 'cliente', 'vendedor', 
            'bodega', 'tipo_nd', 'tipo_doc_afectado', 'numero_doc_afectado', 
            'fecha_doc_afectado', 'motivo'
        ]
        widgets = {
            'empresa': forms.HiddenInput(),
            'sucursal': forms.HiddenInput(),
            'numero': forms.TextInput(attrs={
                'class': ESTILO_TERROSO['input'],
                'placeholder': 'N° Nota de Débito',
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'fecha': forms.DateInput(attrs={
                'class': ESTILO_TERROSO['date'],
                'type': 'date',
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'cliente': forms.Select(attrs={
                'class': ESTILO_TERROSO['select'],
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'vendedor': forms.Select(attrs={
                'class': ESTILO_TERROSO['select'],
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'bodega': forms.Select(attrs={
                'class': ESTILO_TERROSO['select'],
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'tipo_nd': forms.RadioSelect(attrs={
                'class': 'form-check-input',
                'style': 'border-color: #8B7355;'
            }),
            'tipo_doc_afectado': forms.Select(attrs={
                'class': ESTILO_TERROSO['select'],
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'numero_doc_afectado': forms.TextInput(attrs={
                'class': ESTILO_TERROSO['input'],
                'placeholder': 'N° Documento',
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'fecha_doc_afectado': forms.DateInput(attrs={
                'class': ESTILO_TERROSO['date'],
                'type': 'date',
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
            'motivo': forms.Textarea(attrs={
                'class': ESTILO_TERROSO['textarea'],
                'rows': 3,
                'placeholder': 'Describa el motivo de la nota de débito...',
                'style': 'border-color: #8B7355; background-color: #FAF8F3;'
            }),
        }
        labels = {
            'numero': 'N° ND',
            'fecha': 'Fecha Emisión',
            'cliente': 'Cliente (RUT - Nombre)',
            'vendedor': 'Vendedor',
            'bodega': 'Bodega',
            'tipo_nd': 'Tipo de Nota (Referencia)',
            'tipo_doc_afectado': 'Documento a Referenciar',
            'numero_doc_afectado': 'N° Documento Referenciado',
            'fecha_doc_afectado': 'Fecha Emisión Doc.',
            'motivo': 'Motivo / Razón',
        }


class NotaDebitoDetalleForm(forms.ModelForm):
    """Formulario para items de Nota de Débito"""
    cantidad = forms.DecimalField(localize=True, widget=forms.TextInput)
    precio_unitario = forms.DecimalField(localize=True, widget=forms.TextInput)
    
    class Meta:
        model = NotaDebitoDetalle
        fields = ['articulo', 'cantidad', 'precio_unitario', 'descuento']
        widgets = {
            'articulo': forms.Select(attrs={
                'class': 'form-select form-select-sm',
                'style': 'border-color: #D4C4A8; font-size: 0.875rem;'
            }),
            'codigo': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'readonly': 'readonly',
                'style': 'border-color: #D4C4A8; font-size: 0.875rem; background-color: #FAF8F3;'
            }),
            'descripcion': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'style': 'border-color: #D4C4A8; font-size: 0.875rem;'
            }),
            'cantidad': forms.TextInput(attrs={
                'class': 'form-control form-control-sm text-end',
                'style': 'border-color: #D4C4A8; font-size: 0.875rem;'
            }),
            'precio_unitario': forms.TextInput(attrs={
                'class': 'form-control form-control-sm text-end',
                'style': 'border-color: #D4C4A8; font-size: 0.875rem;'
            }),
            'descuento': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm text-end',
                'min': '0',
                'max': '100',
                'step': '0.01',
                'style': 'border-color: #D4C4A8; font-size: 0.875rem;'
            }),
        }


NotaDebitoDetalleFormSet = inlineformset_factory(
    NotaDebito,
    NotaDebitoDetalle,
    form=NotaDebitoDetalleForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)