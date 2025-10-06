from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from .models import OrdenCompra, ItemOrdenCompra, RecepcionMercancia, ItemRecepcion
from proveedores.models import Proveedor
from articulos.models import Articulo
from empresas.models import Sucursal
from bodegas.models import Bodega


class OrdenCompraForm(forms.ModelForm):
    """Formulario para crear y editar órdenes de compra"""
    
    class Meta:
        model = OrdenCompra
        fields = [
            'proveedor', 'bodega', 'numero_orden', 'fecha_orden', 
            'fecha_entrega_esperada', 'estado_orden', 'prioridad', 
            'observaciones', 'condiciones_pago', 'plazo_entrega',
            'subtotal', 'descuentos_totales', 'impuestos_totales', 'total_orden'
        ]
        widgets = {
            'proveedor': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'bodega': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'numero_orden': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'readonly': True, 'placeholder': 'Se generará automáticamente'}),
            'fecha_orden': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
            'fecha_entrega_esperada': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
            'estado_orden': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'prioridad': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2}),
            'condiciones_pago': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'plazo_entrega': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'subtotal': forms.HiddenInput(),
            'descuentos_totales': forms.HiddenInput(),
            'impuestos_totales': forms.HiddenInput(),
            'total_orden': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        # Configurar datos por empresa
        if self.empresa:
            self.fields['proveedor'].queryset = Proveedor.objects.filter(empresa=self.empresa)
            self.fields['bodega'].queryset = Bodega.objects.filter(empresa=self.empresa)
        
        # Generar número de orden automáticamente SOLO para nuevas órdenes
        if not self.instance.pk and self.empresa:
            try:
                from empresas.models import ConfiguracionEmpresa
                configuracion = ConfiguracionEmpresa.objects.get(empresa=self.empresa)
                # NO incrementar el contador aquí, solo mostrar el próximo número
                numero_preview = f"{configuracion.prefijo_orden_compra}-{configuracion.siguiente_orden_compra:06d}"
                self.fields['numero_orden'].initial = numero_preview
                # NO guardamos numero_orden_generado aquí
            except Exception as e:
                print(f"Error obteniendo número de orden: {e}")
                # Fallback al método anterior si no hay configuración
                ultima_orden = OrdenCompra.objects.filter(empresa=self.empresa).order_by('-id').first()
                if ultima_orden:
                    try:
                        # Intentar extraer el número del formato OC-000001
                        if '-' in ultima_orden.numero_orden:
                            numero = int(ultima_orden.numero_orden.split('-')[-1]) + 1
                        else:
                            numero = int(ultima_orden.numero_orden) + 1
                    except ValueError:
                        numero = 1
                else:
                    numero = 1
                numero_formateado = f"OC-{numero:06d}"
                self.fields['numero_orden'].initial = numero_formateado


class ItemOrdenCompraForm(forms.ModelForm):
    """Formulario para items de orden de compra"""
    
    class Meta:
        model = ItemOrdenCompra
        fields = [
            'articulo', 'cantidad_solicitada', 'precio_unitario', 
            'descuento_porcentaje', 'impuesto_porcentaje', 'especificaciones', 'fecha_entrega_item'
        ]
        widgets = {
            'articulo': forms.Select(attrs={'class': 'form-select form-select-sm articulo-select'}),
            'cantidad_solicitada': forms.NumberInput(attrs={'class': 'form-control form-control-sm cantidad-input', 'min': '1'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control form-control-sm precio-input', 'min': '0'}),
            'descuento_porcentaje': forms.NumberInput(attrs={'class': 'form-control form-control-sm descuento-input', 'min': '0', 'max': '100', 'value': '0'}),
            'impuesto_porcentaje': forms.NumberInput(attrs={'class': 'form-control form-control-sm impuesto-input', 'min': '0', 'max': '100', 'value': '19'}),
            'especificaciones': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2}),
            'fecha_entrega_item': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Hacer impuesto_porcentaje opcional
        self.fields['impuesto_porcentaje'].required = False
        
        # Filtrar artículos por empresa - esto se hará en la vista
        # La empresa se pasará a través del contexto del template
    
    def clean_cantidad_solicitada(self):
        cantidad = self.cleaned_data.get('cantidad_solicitada')
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
        if descuento and (descuento < 0 or descuento > 100):
            raise ValidationError('El descuento debe estar entre 0 y 100%.')
        return descuento
    
    def clean_impuesto_porcentaje(self):
        impuesto = self.cleaned_data.get('impuesto_porcentaje')
        if impuesto and (impuesto < 0 or impuesto > 100):
            raise ValidationError('El impuesto debe estar entre 0 y 100%.')
        return impuesto


# Formset para manejar múltiples items
ItemOrdenCompraFormSet = inlineformset_factory(
    OrdenCompra,
    ItemOrdenCompra,
    form=ItemOrdenCompraForm,
    extra=1,
    can_delete=True,
    fields=[
        'articulo', 'cantidad_solicitada', 'precio_unitario', 
        'descuento_porcentaje', 'impuesto_porcentaje', 'especificaciones', 'fecha_entrega_item'
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
    
    ESTADO_ORDEN_CHOICES = [
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
    
    ESTADO_PAGO_CHOICES = [
        ('', 'Todos los estados de pago'),
        ('pagada', 'Pagada'),
        ('credito', 'Crédito'),
        ('parcial', 'Pago Parcial'),
        ('vencida', 'Vencida'),
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
            'class': 'form-control form-control-sm',
            'placeholder': 'Buscar por número, proveedor o artículo...'
        })
    )
    
    estado_orden = forms.ChoiceField(
        choices=ESTADO_ORDEN_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    
    prioridad = forms.ChoiceField(
        choices=PRIORIDAD_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )
