from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Caja, AperturaCaja, MovimientoCaja
from empresas.models import Empresa, Sucursal
from ventas.models import EstacionTrabajo, FormaPago, Venta
from bodegas.models import Bodega


class CajaForm(forms.ModelForm):
    """Formulario para crear/editar cajas"""
    
    class Meta:
        model = Caja
        fields = ['numero', 'nombre', 'descripcion', 'sucursal', 'estacion_trabajo', 'bodega', 'activo']
        widgets = {
            'numero': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 001'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Caja Principal'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción de la caja'}),
            'sucursal': forms.Select(attrs={'class': 'form-select'}),
            'estacion_trabajo': forms.Select(attrs={'class': 'form-select'}),
            'bodega': forms.Select(attrs={'class': 'form-select'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'numero': 'Número de Caja',
            'nombre': 'Nombre de la Caja',
            'descripcion': 'Descripción',
            'estacion_trabajo': 'Estación de trabajo (POS)',
            'bodega': 'Bodega (para descuento de stock)',
            'activo': 'Caja Activa',
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['sucursal'].queryset = Sucursal.objects.filter(empresa=self.empresa)
            self.fields['bodega'].queryset = Bodega.objects.filter(empresa=self.empresa)
            self.fields['estacion_trabajo'].queryset = EstacionTrabajo.objects.filter(
                empresa=self.empresa, activo=True
            ).select_related('sucursal').order_by('numero')
            self.fields['bodega'].empty_label = "Seleccione una bodega"
            self.fields['sucursal'].empty_label = "Seleccione una sucursal"
            self.fields['estacion_trabajo'].empty_label = "Sin asignar"
            self.fields['estacion_trabajo'].required = False
        else:
            self.fields['estacion_trabajo'].queryset = EstacionTrabajo.objects.none()

    def clean(self):
        cleaned = super().clean()
        sucursal = cleaned.get('sucursal')
        estacion = cleaned.get('estacion_trabajo')
        if estacion and self.empresa and estacion.empresa_id != self.empresa.id:
            raise ValidationError('La estación de trabajo no pertenece a esta empresa.')
        if estacion and sucursal and estacion.sucursal_id and estacion.sucursal_id != sucursal.id:
            raise ValidationError('La estación de trabajo no pertenece a la sucursal seleccionada.')
        return cleaned


class AperturaCajaForm(forms.ModelForm):
    """Formulario para apertura de caja"""
    
    class Meta:
        model = AperturaCaja
        fields = ['caja', 'monto_inicial', 'observaciones_apertura']
        widgets = {
            'caja': forms.Select(attrs={'class': 'form-select'}),
            'monto_inicial': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'observaciones_apertura': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Observaciones de apertura'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        sucursal = kwargs.pop('sucursal', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            # Solo mostrar cajas activas que no tengan apertura activa
            cajas_base = Caja.objects.filter(empresa=self.empresa, activo=True)
            if sucursal is not None:
                cajas_base = cajas_base.filter(sucursal=sucursal)
            
            cajas_disponibles = []
            for caja in cajas_base:
                if not caja.tiene_apertura_activa():
                    cajas_disponibles.append(caja.id)
            
            self.fields['caja'].queryset = Caja.objects.filter(id__in=cajas_disponibles)
    
    def clean_caja(self):
        caja = self.cleaned_data.get('caja')
        if caja and caja.tiene_apertura_activa():
            raise ValidationError('Esta caja ya tiene una apertura activa.')
        return caja


class CierreCajaForm(forms.Form):
    """Formulario para cierre de caja"""
    
    monto_contado = forms.DecimalField(
        label='Monto Contado en Caja',
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.00'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'placeholder': '0.00'
        })
    )
    observaciones_cierre = forms.CharField(
        label='Observaciones de Cierre',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Observaciones sobre el cierre de caja'
        })
    )


class ProcesarVentaForm(forms.Form):
    """Formulario para procesar una preventa (ticket) y convertirla en documento tributario"""
    
    ticket_id = forms.IntegerField(widget=forms.HiddenInput())
    
    tipo_documento = forms.ChoiceField(
        label='Tipo de Documento',
        choices=[
            ('boleta', 'Boleta'),
            ('factura', 'Factura'),
            ('guia', 'Guía de Despacho'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    forma_pago = forms.ModelChoiceField(
        label='Forma de Pago',
        queryset=FormaPago.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    monto_recibido = forms.DecimalField(
        label='Monto Recibido',
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.00'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'placeholder': '0.00'
        })
    )
    
    # Campos opcionales para cheque
    numero_cheque = forms.CharField(
        label='Número de Cheque',
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número de cheque'})
    )
    banco = forms.CharField(
        label='Banco',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del banco'})
    )
    fecha_cheque = forms.DateField(
        label='Fecha del Cheque',
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    observaciones = forms.CharField(
        label='Observaciones',
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observaciones adicionales'})
    )
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        self.ticket = kwargs.pop('ticket', None)
        super().__init__(*args, **kwargs)
        
        if self.empresa:
            self.fields['forma_pago'].queryset = FormaPago.objects.filter(empresa=self.empresa, activo=True)
        
        if self.ticket:
            self.fields['monto_recibido'].initial = self.ticket.total
    
    def clean(self):
        cleaned_data = super().clean()
        forma_pago = cleaned_data.get('forma_pago')
        numero_cheque = cleaned_data.get('numero_cheque')
        
        # Validar que si la forma de pago requiere cheque, se proporcione la información
        if forma_pago and forma_pago.requiere_cheque:
            if not numero_cheque:
                raise ValidationError('Debe proporcionar el número de cheque para esta forma de pago.')
        
        return cleaned_data


class MovimientoCajaForm(forms.ModelForm):
    """Formulario para registrar movimientos manuales de caja (retiros/ingresos)"""
    
    class Meta:
        model = MovimientoCaja
        fields = ['tipo', 'monto', 'descripcion']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}, choices=[
                ('retiro', 'Retiro'),
                ('ingreso', 'Ingreso'),
            ]),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Motivo del movimiento'}),
        }
    
    def clean_descripcion(self):
        descripcion = self.cleaned_data.get('descripcion')
        if not descripcion or len(descripcion.strip()) < 10:
            raise ValidationError('Debe proporcionar una descripción detallada (mínimo 10 caracteres).')
        return descripcion

