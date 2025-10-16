from django import forms
from .models import Vendedor, FormaPago, EstacionTrabajo, PrecioClienteArticulo


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
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: EF', 'maxlength': '20'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Efectivo'}),
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


class PrecioClienteArticuloForm(forms.ModelForm):
    """Formulario para crear y editar precios especiales por cliente"""
    
    class Meta:
        model = PrecioClienteArticulo
        fields = ['cliente', 'articulo', 'precio_especial', 'descuento_porcentaje', 'activo', 'fecha_inicio', 'fecha_fin']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'articulo': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'precio_especial': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'required': True}),
            'descuento_porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'fecha_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Configurar formato de fecha para que funcione con input type="date"
        self.fields['fecha_inicio'].input_formats = ['%Y-%m-%d']
        self.fields['fecha_fin'].input_formats = ['%Y-%m-%d']
        
        # Valores por defecto solo para nuevos registros
        if not self.instance.pk:
            from datetime import date
            hoy = date.today()
            ultimo_dia_año = date(hoy.year, 12, 31)
            self.fields['fecha_inicio'].initial = hoy
            self.fields['fecha_fin'].initial = ultimo_dia_año
        labels = {
            'cliente': 'Cliente',
            'articulo': 'Artículo',
            'precio_especial': 'Precio Especial',
            'descuento_porcentaje': 'Descuento Adicional (%)',
            'activo': 'Activo',
            'fecha_inicio': 'Fecha Inicio Vigencia',
            'fecha_fin': 'Fecha Fin Vigencia',
        }


class EstacionTrabajoForm(forms.ModelForm):
    """Formulario para crear y editar estaciones de trabajo"""

    class Meta:
        model = EstacionTrabajo
        fields = ['numero', 'nombre', 'descripcion', 'modo_pos', 'correlativo_ticket', 'puede_facturar', 'puede_boletar', 'puede_guia', 'puede_cotizar', 'puede_vale', 'max_items_factura', 'max_items_boleta', 'max_items_guia', 'max_items_cotizacion', 'max_items_vale', 'activo']
        widgets = {
            'numero': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 001', 'maxlength': '10'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Caja Principal'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción de la estación de trabajo'}),
            'modo_pos': forms.Select(attrs={'class': 'form-select'}),
            'correlativo_ticket': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'title': 'Correlativo único de ticket de la estación'}),
            'puede_facturar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_boletar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_guia': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_cotizar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'puede_vale': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_items_factura': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '100'}),
            'max_items_boleta': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '100'}),
            'max_items_guia': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '100'}),
            'max_items_cotizacion': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '100'}),
            'max_items_vale': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '100'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'numero': 'Número de Estación',
            'nombre': 'Nombre de la Estación',
            'descripcion': 'Descripción',
            'modo_pos': 'Modo de Operación POS',
            'correlativo_ticket': 'Correlativo de Ticket',
            'puede_facturar': 'Puede Emitir Facturas',
            'puede_boletar': 'Puede Emitir Boletas',
            'puede_guia': 'Puede Emitir Guías',
            'puede_cotizar': 'Puede Emitir Cotizaciones',
            'puede_vale': 'Puede Emitir Vales',
            'max_items_factura': 'Máx. Items Factura',
            'max_items_boleta': 'Máx. Items Boleta',
            'max_items_guia': 'Máx. Items Guía',
            'max_items_cotizacion': 'Máx. Items Cotización',
            'max_items_vale': 'Máx. Items Vale',
            'activo': 'Activo',
        }













