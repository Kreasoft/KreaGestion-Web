from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone
from empresas.models import Sucursal
from .models import (
    Vendedor, FormaPago, EstacionTrabajo, PrecioClienteArticulo, 
    NotaCredito, NotaCreditoDetalle, NotaDebito, NotaDebitoDetalle,
    ensure_estacion_caja_impresion,
)


class VendedorForm(forms.ModelForm):
    """Formulario para crear y editar vendedores"""
    
    class Meta:
        model = Vendedor
        fields = ['codigo', 'nombre', 'porcentaje_comision', 'telefono_app', 'app_movil_activa', 'activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: V001'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre completo del vendedor'}),
            'porcentaje_comision': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100', 'step': '0.01'}),
            'telefono_app': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+56 9 63697225'}),
            'app_movil_activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'codigo': 'Código',
            'nombre': 'Nombre',
            'porcentaje_comision': '% Comisión',
            'telefono_app': 'Celular app',
            'app_movil_activa': 'App móvil activa',
            'activo': 'Activo',
        }

    def clean_telefono_app(self):
        from .telefono_app import normalizar_telefono_cl
        raw = self.cleaned_data.get('telefono_app') or ''
        if not str(raw).strip():
            return ''
        tel = normalizar_telefono_cl(raw)
        if not tel:
            raise forms.ValidationError('Use un celular chileno: +56 9 63697225')
        return tel

    def save(self, commit=True):
        obj = super().save(commit=False)
        previa_activa = bool(self.instance.pk and Vendedor.objects.filter(pk=self.instance.pk, app_movil_activa=True).exists())
        if obj.app_movil_activa and obj.telefono_app:
            if not obj.app_movil_activado_en:
                obj.app_movil_activado_en = timezone.now()
            obj.app_movil_revocado_en = None
        elif previa_activa and not obj.app_movil_activa:
            obj.app_movil_revocado_en = timezone.now()
        if commit:
            obj.save()
        return obj


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

    def __init__(self, *args, empresa=None, **kwargs):
        ensure_estacion_caja_impresion()
        super().__init__(*args, **kwargs)
        empresa = empresa or getattr(self.instance, 'empresa', None)
        self.empresa = empresa
        if empresa:
            self.fields['sucursal'].queryset = Sucursal.objects.filter(empresa=empresa).order_by('nombre')
            self.fields['sucursal'].required = True
            if not self.instance.pk and self.fields['sucursal'].queryset.count() == 1:
                self.initial.setdefault('sucursal', self.fields['sucursal'].queryset.first())
        else:
            self.fields['sucursal'].queryset = Sucursal.objects.none()
    
    class Meta:
        model = EstacionTrabajo
        fields = [
            'sucursal', 'numero', 'nombre', 'descripcion',
            'modo_pos', 'correlativo_ticket', 'codigo_comodin',
            'puede_facturar', 'puede_boletar', 'puede_guia', 'puede_cotizar', 'puede_ticket', 'puede_vale',
            'cierre_directo', 'flujo_cierre_directo', 'enviar_sii_directo',
            'max_items_factura', 'max_items_boleta', 'max_items_guia', 'max_items_cotizacion', 'max_items_ticket', 'max_items_vale',
            'copias_factura', 'copias_boleta', 'copias_guia', 'copias_notacredito', 'copias_cotizacion', 'copias_ticket', 'copias_vale',
            'activo'
        ]
        widgets = {
            'sucursal': forms.Select(attrs={'class': 'form-select'}),
            'numero': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 001'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Estación 1'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Opcional'}),
            'modo_pos': forms.Select(attrs={'class': 'form-select'}),
            'correlativo_ticket': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'codigo_comodin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '999999'}),
            'puede_facturar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_boletar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_guia': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_cotizar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_ticket': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_vale': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'cierre_directo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'data-est-cierre': '1'}),
            'flujo_cierre_directo': forms.Select(attrs={'class': 'form-select'}),
            'enviar_sii_directo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_items_factura': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'max_items_boleta': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'max_items_guia': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'max_items_cotizacion': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'max_items_ticket': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'max_items_vale': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'copias_factura': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
            'copias_boleta': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
            'copias_guia': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
            'copias_notacredito': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
            'copias_cotizacion': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
            'copias_ticket': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
            'copias_vale': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'sucursal': 'Sucursal',
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
            'puede_ticket': 'Puede Emitir Tickets',
            'puede_vale': 'Puede Emitir Vales',
            'cierre_directo': 'Cierre directo (Cerrar y Emitir DTE)',
            'flujo_cierre_directo': 'Flujo para cierre directo',
            'enviar_sii_directo': 'Enviar al SII automáticamente',
            'max_items_factura': 'Máx. Items Factura',
            'max_items_boleta': 'Máx. Items Boleta',
            'max_items_guia': 'Máx. Items Guía',
            'max_items_cotizacion': 'Máx. Items Cotización',
            'max_items_ticket': 'Máx. Items Ticket',
            'max_items_vale': 'Máx. Items Vale',
            'copias_factura': 'Copias Factura',
            'copias_boleta': 'Copias Boleta',
            'copias_guia': 'Copias Guía',
            'copias_cotizacion': 'Copias Cotización',
            'copias_ticket': 'Copias Ticket',
            'copias_vale': 'Copias Vale',
            'activo': 'Activa',
        }

    def clean(self):
        cleaned = super().clean()
        empresa = self.empresa or getattr(self.instance, 'empresa', None)
        sucursal = cleaned.get('sucursal')
        nombre = (cleaned.get('nombre') or '').strip()
        cleaned['nombre'] = nombre
        if empresa and sucursal and nombre:
            qs = EstacionTrabajo.objects.filter(
                empresa=empresa, sucursal=sucursal, nombre__iexact=nombre
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    'nombre',
                    'Ya existe una estación con ese nombre en esta sucursal. '
                    'Debe ser distinto para no mezclar ventas (estación + vendedor + sucursal).',
                )
        return cleaned


class PrecioClienteArticuloForm(forms.ModelForm):
    """Formulario para crear y editar precios especiales de artículos por cliente"""
    
    class Meta:
        model = PrecioClienteArticulo
        fields = ['cliente', 'articulo', 'precio_especial', 'descuento_porcentaje', 'fecha_inicio', 'fecha_fin', 'activo']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'articulo': forms.Select(attrs={'class': 'form-select'}),
            'precio_especial': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'descuento_porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100', 'step': '0.01'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'cliente': 'Cliente',
            'articulo': 'Artículo',
            'precio_especial': 'Precio Especial',
            'descuento_porcentaje': '% Descuento Adicional',
            'fecha_inicio': 'Fecha Inicio',
            'fecha_fin': 'Fecha Fin',
            'activo': 'Activo',
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