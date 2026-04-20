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
            'subtotal', 'descuento_porcentaje_1', 'descuento_porcentaje_2', 
            'descuento_porcentaje_3', 'descuento_monto_directo',
            'descuentos_totales', 'neto_ajustado', 'iva_ajustado', 
            'impuesto_especifico', 'impuestos_totales', 'total_orden'
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
            
            # Campos de Totales y Descuentos
            'subtotal': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'readonly': True}),
            'descuento_porcentaje_1': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-center', 'min': 0, 'max': 100}),
            'descuento_porcentaje_2': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-center', 'min': 0, 'max': 100}),
            'descuento_porcentaje_3': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-center', 'min': 0, 'max': 100}),
            'descuento_monto_directo': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'min': 0}),
            'descuentos_totales': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'readonly': True}),
            'neto_ajustado': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end'}),
            'iva_ajustado': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end'}),
            'impuesto_especifico': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end'}),
            'impuestos_totales': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'readonly': True}),
            'total_orden': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end fw-bold'}),
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
    
    impuesto_porcentaje = forms.IntegerField(initial=19, widget=forms.HiddenInput(), required=False)
    
    class Meta:
        model = ItemOrdenCompra
        fields = [
            'articulo', 'cantidad_solicitada', 'precio_unitario', 
            'descuento_porcentaje', 'impuesto_porcentaje', 'especificaciones', 'fecha_entrega_item'
        ]
        widgets = {
            'articulo': forms.Select(attrs={'class': 'form-select form-select-sm articulo-select'}),
            'cantidad_solicitada': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-center cantidad-input', 'min': '1'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end precio-unitario-input', 'min': '0', 'step': '1'}),
            'descuento_porcentaje': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-center descuento-input', 'min': '0', 'max': '100'}),
            'impuesto_porcentaje': forms.HiddenInput(attrs={'value': '19'}),
            'especificaciones': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2}),
            'fecha_entrega_item': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Establecer valores iniciales técnicos para que el formset detecte 
        # correctamente cuándo una fila no ha sido modificada (evita IntegrityError)
        if not self.instance.pk:
            self.initial['cantidad_solicitada'] = 1
            self.initial['precio_unitario'] = 0
            self.initial['descuento_porcentaje'] = 0
            self.initial['impuesto_porcentaje'] = 19
            
        # Hacer campos opcionales para permitir filas vacías (que tienen impuesto hidden)
        # La validación real se hace en clean()
        self.fields['impuesto_porcentaje'].required = False
        self.fields['articulo'].required = False
        self.fields['cantidad_solicitada'].required = False
        self.fields['precio_unitario'].required = False
        self.fields['descuento_porcentaje'].required = False
        self.fields['fecha_entrega_item'].required = False
        
        # La empresa se pasará a través del contexto del template
    
    def clean_impuesto_porcentaje(self):
        """Asegurar que el impuesto nunca sea nulo para evitar errores de BD"""
        impuesto = self.cleaned_data.get('impuesto_porcentaje')
        if impuesto is None or impuesto == '':
            return 19
        return impuesto
    
    def has_changed(self):
        """Forzar que el formset ignore la fila si no hay artículo seleccionado"""
        field_name = 'articulo'
        if self.prefix:
            field_name = f"{self.prefix}-{field_name}"
        
        articulo_id = self.data.get(field_name)
        if not articulo_id:
            return False
        return super().has_changed()

    def clean(self):
        """Validar integridad y asegurar que filas vacías no intenten guardarse sin artículo"""
        cleaned_data = super().clean()
        articulo = cleaned_data.get('articulo')
        cantidad = cleaned_data.get('cantidad_solicitada')
        precio = cleaned_data.get('precio_unitario')
        
        # Si NO hay artículo, esta fila NO debe guardarse.
        if not articulo:
            # Si tiene otros datos, reportamos error
            if (precio and precio > 0) or (cantidad and cantidad > 1):
                self.add_error('articulo', 'Este campo es requerido si el ítem tiene datos.')
            else:
                # Si está "vacío" (solo valores por defecto), 
                # forzamos que Django lo vea como no-modificado
                # borrando cualquier dato que pueda disparar el guardado
                for field in list(cleaned_data.keys()):
                    if field != 'id' and field != 'orden_compra':
                        cleaned_data.pop(field, None)
            return cleaned_data
            
        # Si tiene artículo, validar integridad
        if not cantidad or cantidad < 1:
            self.add_error('cantidad_solicitada', 'La cantidad debe ser mayor a 0.')
        if precio is None:
            self.add_error('precio_unitario', 'El precio es requerido.')
            
        return cleaned_data
    
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


# Formset personalizado para manejar múltiples items
class ItemOrdenCompraFormSetBase(forms.BaseInlineFormSet):
    """Formset personalizado que ignora items sin artículo"""
    
    def clean(self):
        """Validar y marcar como DELETE los items sin artículo"""
        if any(self.errors):
            return
        
        for form in self.forms:
            # Solo procesar forms que tienen cleaned_data (pasaron la validación básica)
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                articulo = form.cleaned_data.get('articulo')
                cantidad = form.cleaned_data.get('cantidad_solicitada')
                precio = form.cleaned_data.get('precio_unitario')
                
                # Si no hay artículo seleccionado Y no hay datos, marcar como DELETE
                # Esto permite ignorar items vacíos sin generar errores
                if not articulo and not cantidad and not precio:
                    # Marcar para eliminar (ignorar)
                    form.cleaned_data['DELETE'] = True
                    # Si el form tiene instancia, también marcar DELETE
                    if form.instance and form.instance.pk:
                        form.cleaned_data['DELETE'] = True
                # Si hay datos pero no hay artículo, el método clean() del form ya generó el error
    
    def save(self, commit=True):
        """Guardar solo los items que tienen artículo"""
        # Primero procesar los que están marcados para eliminar
        for form in self.forms:
            if form.cleaned_data and form.cleaned_data.get('DELETE', False):
                if form.instance.pk:
                    if commit:
                        form.instance.delete()
                    continue
        
        # Luego guardar solo los forms que tienen artículo
        instances = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                articulo = form.cleaned_data.get('articulo')
                
                # Solo guardar si tiene artículo seleccionado
                if articulo:
                    try:
                        instance = form.save(commit=commit)
                        if instance:
                            instances.append(instance)
                    except Exception as e:
                        # Si hay error al guardar, continuar con el siguiente
                        print(f"Error guardando item: {e}")
                        continue
        
        return instances


# Formset para manejar múltiples items
ItemOrdenCompraFormSet = inlineformset_factory(
    OrdenCompra,
    ItemOrdenCompra,
    form=ItemOrdenCompraForm,
    formset=ItemOrdenCompraFormSetBase,
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
