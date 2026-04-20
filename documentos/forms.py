from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import DocumentoCompra, ItemDocumentoCompra, HistorialPagoDocumento, FormaPagoPago
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
            'observaciones',
            'subtotal', 'descuento_porcentaje_1', 'descuento_porcentaje_2', 
            'descuento_porcentaje_3', 'descuento_monto_directo',
            'descuentos_totales', 'neto_ajustado', 'iva_ajustado', 
            'impuesto_especifico', 'impuestos_totales', 'total_documento'
        ]
        widgets = {
            'tipo_documento': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'proveedor': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'bodega': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'numero_documento': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Ej: 0001-00012345'}),
            'fecha_emision': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
            'fecha_vencimiento': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
            'estado_documento': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'estado_pago': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2, 'placeholder': 'Observaciones...'}),
            
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
            'total_documento': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end fw-bold'}),
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
        
        # Asegurar que los campos de fecha tengan los valores correctos al editar
        if self.instance.pk:
            if self.instance.fecha_emision:
                self.initial['fecha_emision'] = self.instance.fecha_emision
            if self.instance.fecha_vencimiento:
                self.initial['fecha_vencimiento'] = self.instance.fecha_vencimiento
    
    def clean_numero_documento(self):
        numero_documento = self.cleaned_data.get('numero_documento')
        tipo_documento = self.cleaned_data.get('tipo_documento')
        proveedor = self.cleaned_data.get('proveedor')
        empresa = self.empresa
        
        if numero_documento and tipo_documento and proveedor and empresa:
            # Verificar unicidad por empresa, proveedor, tipo y número
            queryset = DocumentoCompra.objects.filter(
                empresa=empresa,
                proveedor=proveedor,
                tipo_documento=tipo_documento,
                numero_documento=numero_documento
            )
            
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                tipo_dict = dict(DocumentoCompra.TIPO_DOCUMENTO_CHOICES)
                tipo_display = tipo_dict.get(tipo_documento, tipo_documento)
                raise ValidationError(f'Ya existe un documento de tipo "{tipo_display}" con el número {numero_documento} en esta empresa.')
        
        return numero_documento


class ItemDocumentoCompraForm(forms.ModelForm):
    """Formulario limpio y simple para items de documento de compra"""
    
    impuesto_porcentaje = forms.IntegerField(initial=19, widget=forms.HiddenInput(), required=False)
    
    class Meta:
        model = ItemDocumentoCompra
        fields = [
            'articulo', 'cantidad', 
            'precio_unitario', 'descuento_porcentaje', 'impuesto_porcentaje'
        ]
        widgets = {
            'articulo': forms.Select(attrs={'class': 'form-select form-select-sm articulo-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control form-control-sm cantidad-input', 'min': '1'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control form-control-sm precio-input', 'min': '0', 'placeholder': 'Precio sin decimales'}),
            'descuento_porcentaje': forms.NumberInput(attrs={'class': 'form-control form-control-sm descuento-input', 'min': '0', 'max': '100'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Establecer valores iniciales técnicos para que el formset detecte 
        # correctamente cuándo una fila no ha sido modificada (evita IntegrityError)
        if not self.instance.pk:
            self.initial['cantidad'] = 1
            self.initial['precio_unitario'] = 0
            self.initial['descuento_porcentaje'] = 0
            self.initial['impuesto_porcentaje'] = 19
        
        # Campos opcionales para permitir que el formset ignore filas vacías
        # que tienen valores iniciales (como el impuesto o descuento)
        self.fields['articulo'].required = False
        self.fields['cantidad'].required = False
        self.fields['precio_unitario'].required = False
        self.fields['descuento_porcentaje'].required = False
        self.fields['impuesto_porcentaje'].required = False
    
    def has_changed(self):
        """Forzar que el formset ignore la fila si no hay artículo seleccionado"""
        # Si no hay artículo en el POST de esta fila, no ha cambiado "útilmente"
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
        cantidad = cleaned_data.get('cantidad')
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
                    if field != 'id' and field != 'documento_compra':
                        cleaned_data.pop(field, None)
            return cleaned_data
            
        # Si tiene artículo, validar integridad obligatoria
        if not cantidad or cantidad < 1:
            self.add_error('cantidad', 'La cantidad debe ser mayor a 0.')
        if precio is None:
            self.add_error('precio_unitario', 'El precio es requerido.')
            
        return cleaned_data
    
    def clean_impuesto_porcentaje(self):
        empresa = None
        if self.instance and self.instance.pk:
            # Si la instancia ya está guardada, obtener empresa del documento padre
            try:
                if self.instance.documento_compra_id:
                    from .models import DocumentoCompra
                    documento = DocumentoCompra.objects.select_related('empresa').get(pk=self.instance.documento_compra_id)
                    empresa = documento.empresa
            except:
                pass
        
        # Recopilar TODOS los artículos que DEBEN estar en el queryset
        articulos_requeridos = set()
        
        # 1. Artículo de la instancia actual (si existe)
        if self.instance and self.instance.pk and self.instance.articulo_id:
            articulos_requeridos.add(self.instance.articulo_id)
        
        # 2. Artículo que viene en los datos del POST (CRÍTICO: antes de validar)
        if self.data:
            # Buscar TODOS los campos articulo en el POST
            for key, value in self.data.items():
                if key.endswith('-articulo') and value:
                    try:
                        articulo_id = int(value)
                        articulos_requeridos.add(articulo_id)
                    except (ValueError, TypeError):
                        pass
        
        # 3. También verificar el valor inicial del campo (por si viene del POST)
        if 'articulo' in self.initial and self.initial['articulo']:
            try:
                articulos_requeridos.add(int(self.initial['articulo']))
            except (ValueError, TypeError):
                pass
        
        # 4. Si hay datos POST, buscar el valor del campo usando el prefijo del formulario
        if self.data:
            # Intentar obtener el prefijo del formulario
            prefix = getattr(self, 'prefix', None)
            if prefix:
                campo_articulo = f"{prefix}-articulo"
                valor_articulo = self.data.get(campo_articulo)
                if valor_articulo:
                    try:
                        articulos_requeridos.add(int(valor_articulo))
                    except (ValueError, TypeError):
                        pass
            # También buscar sin prefijo por si acaso
            valor_articulo_sin_prefijo = self.data.get('articulo')
            if valor_articulo_sin_prefijo:
                try:
                    articulos_requeridos.add(int(valor_articulo_sin_prefijo))
                except (ValueError, TypeError):
                    pass
        
        # Configurar queryset: SIEMPRE incluir artículos requeridos
        # Si hay datos POST, ser más permisivo
        if self.data and articulos_requeridos:
            # Si hay POST y artículos requeridos, incluir TODOS los artículos requeridos sin restricción de empresa
            self.fields['articulo'].queryset = Articulo.objects.filter(pk__in=articulos_requeridos)
        elif articulos_requeridos:
            # Si hay empresa, incluir artículos de la empresa Y los requeridos
            if empresa:
                self.fields['articulo'].queryset = Articulo.objects.filter(
                    Q(empresa=empresa) | Q(pk__in=articulos_requeridos)
                )
            else:
                # Solo los artículos requeridos (sin filtro de empresa)
                self.fields['articulo'].queryset = Articulo.objects.filter(pk__in=articulos_requeridos)
        elif empresa:
            # Solo artículos de la empresa
            self.fields['articulo'].queryset = Articulo.objects.filter(empresa=empresa)
        else:
            # Queryset vacío (se configurará en la vista)
            self.fields['articulo'].queryset = Articulo.objects.none()
    
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
    
    def clean_articulo(self):
        """Asegurar que el artículo esté en el queryset - SIEMPRE permitir si viene del POST"""
        articulo = self.cleaned_data.get('articulo')
        
        if articulo:
            # Si hay datos POST, siempre permitir el artículo (ya viene validado)
            if self.data:
                # El artículo viene del POST, así que está bien
                return articulo
            
            # Si no hay POST pero el artículo no está en el queryset, expandirlo
            current_queryset = self.fields['articulo'].queryset
            if articulo not in current_queryset:
                # Expandir el queryset para incluir este artículo
                self.fields['articulo'].queryset = Articulo.objects.filter(
                    Q(pk__in=current_queryset.values_list('pk', flat=True)) | Q(pk=articulo.pk)
                )
        
        return articulo


# Formset para items del documento
ItemDocumentoCompraFormSet = inlineformset_factory(
    DocumentoCompra,
    ItemDocumentoCompra,
    form=ItemDocumentoCompraForm,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class HistorialPagoDocumentoForm(forms.ModelForm):
    """Formulario para registrar pagos de documentos"""
    
    class Meta:
        model = HistorialPagoDocumento
        fields = ['fecha_pago', 'monto_total_pagado', 'observaciones']
        widgets = {
            'fecha_pago': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'monto_total_pagado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def clean_monto_total_pagado(self):
        monto = self.cleaned_data.get('monto_total_pagado')
        if monto and monto <= 0:
            raise ValidationError('El monto debe ser mayor a 0.')
        return monto


class FormaPagoPagoForm(forms.ModelForm):
    """Formulario para formas de pago específicas"""
    
    class Meta:
        model = FormaPagoPago
        fields = ['forma_pago', 'monto', 'numero_cheque', 'banco_cheque', 'fecha_vencimiento_cheque', 
                 'numero_transferencia', 'banco_transferencia', 'numero_tarjeta', 'codigo_autorizacion', 'observaciones']
        widgets = {
            'forma_pago': forms.Select(attrs={'class': 'form-select'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'numero_cheque': forms.TextInput(attrs={'class': 'form-control'}),
            'banco_cheque': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_vencimiento_cheque': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'numero_transferencia': forms.TextInput(attrs={'class': 'form-control'}),
            'banco_transferencia': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_tarjeta': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_autorizacion': forms.TextInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


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
        ('activo', 'Activo'),
        ('anulado', 'Anulado'),
    ]
    
    ESTADO_PAGO_CHOICES = [
        ('', 'Todos los estados de pago'),
        ('pendiente', 'Pendiente'),
        ('credito', 'Crédito'),
        ('pagada', 'Pagada'),
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
