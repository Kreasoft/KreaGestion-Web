from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Articulo, CategoriaArticulo, UnidadMedida, StockArticulo, ImpuestoEspecifico, ListaPrecio, PrecioArticulo, HomologacionCodigo, KitOferta, KitOfertaItem
from proveedores.models import Proveedor


class ArticuloForm(forms.ModelForm):
    """Formulario para crear y editar artículos"""
    
    
    class Meta:
        model = Articulo
        fields = [
            'categoria', 'unidad_medida', 'codigo', 'codigo_barras', 'nombre', 'descripcion', 'logo',
            'precio_costo', 'precio_venta', 'precio_final', 'margen_porcentaje', 'impuesto_especifico',
            'control_stock', 'stock_minimo', 'stock_maximo', 'tipo_articulo', 'activo'
        ]
        widgets = {
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'unidad_medida': forms.Select(attrs={'class': 'form-select'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_barras': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese código de barras (opcional)'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'precio_costo': forms.TextInput(attrs={'class': 'form-control'}),
            'precio_venta': forms.TextInput(attrs={'class': 'form-control'}),
            'precio_final': forms.TextInput(attrs={'class': 'form-control'}),
            'margen_porcentaje': forms.TextInput(attrs={'class': 'form-control'}),
            'impuesto_especifico': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'control_stock': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control'}),
            'stock_maximo': forms.NumberInput(attrs={'class': 'form-control'}),
            'tipo_articulo': forms.Select(attrs={'class': 'form-select'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrar categorías y unidades por empresa
        empresa = None
        
        # Obtener empresa de initial (para formularios nuevos)
        if 'initial' in kwargs and isinstance(kwargs['initial'], dict) and 'empresa' in kwargs['initial']:
            empresa = kwargs['initial']['empresa']
        # Obtener empresa de la instancia (para formularios de edición)
        elif hasattr(self, 'instance') and self.instance and getattr(self.instance, 'empresa', None):
            empresa = self.instance.empresa
        
        if empresa is not None:
            self.fields['categoria'].queryset = CategoriaArticulo.objects.filter(
                empresa=empresa, activa=True
            ).order_by('nombre')
            self.fields['unidad_medida'].queryset = UnidadMedida.objects.filter(
                empresa=empresa, activa=True
            ).order_by('nombre')
        
        # Asegurar que el label del campo categoría sea "Familia"
        self.fields['categoria'].label = 'Familia'
        self.fields['categoria'].label_suffix = ''
        
    
    def clean_codigo(self):
        codigo = self.cleaned_data['codigo']
        if len(codigo.strip()) < 3:
            raise ValidationError('El código debe tener al menos 3 caracteres.')
        
        # Verificar que el código sea único
        if Articulo.objects.filter(codigo=codigo.strip()).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise ValidationError('Este código ya está siendo usado por otro artículo.')
        
        return codigo.strip().upper()
    
    def clean_nombre(self):
        nombre = self.cleaned_data['nombre']
        if len(nombre.strip()) < 3:
            raise ValidationError('El nombre debe tener al menos 3 caracteres.')
        return nombre.strip()
    
    def clean_precio_costo(self):
        precio_costo = self.cleaned_data.get('precio_costo')
        if precio_costo:
            # Solo validar que no esté vacío
            return str(precio_costo).strip()
        return '0.00'
    
    def clean_precio_venta(self):
        precio_venta = self.cleaned_data.get('precio_venta')
        if precio_venta:
            # Solo validar que no esté vacío
            return str(precio_venta).strip()
        return '0.00'
    
    def clean_margen_porcentaje(self):
        margen = self.cleaned_data.get('margen_porcentaje')
        if margen:
            # Convertir a string y limpiar
            margen_str = str(margen).strip()
            # Si está vacío, usar valor por defecto
            if not margen_str:
                return '30.00'
            return margen_str
        return '30.00'
    
    
    def clean_impuesto_especifico(self):
        impuesto = self.cleaned_data.get('impuesto_especifico')
        # Siempre retornar un valor, nunca None
        if impuesto is None or impuesto == '':
            return '0.00'
        
        # Convertir a string y limpiar
        impuesto_str = str(impuesto).strip()
        # Si está vacío, usar valor por defecto
        if not impuesto_str:
            return '0.00'
        
        # Validar que sea un número válido
        try:
            float(impuesto_str.replace(',', '.'))
            return impuesto_str
        except (ValueError, AttributeError):
            return '0.00'
    
    def clean_stock_maximo(self):
        stock_maximo = self.cleaned_data.get('stock_maximo')
        if stock_maximo:
            return str(stock_maximo).strip()
        return '0.00'
    
    def clean(self):
        # Convertir valores de formato chileno a decimales antes de guardar
        cleaned_data = super().clean()
        
        # Convertir precios de formato chileno a decimal
        if 'precio_costo' in cleaned_data and cleaned_data['precio_costo']:
            cleaned_data['precio_costo'] = self._string_to_decimal(cleaned_data['precio_costo'])
        
        if 'precio_venta' in cleaned_data and cleaned_data['precio_venta']:
            cleaned_data['precio_venta'] = self._string_to_decimal(cleaned_data['precio_venta'])
        
        if 'precio_final' in cleaned_data and cleaned_data['precio_final']:
            cleaned_data['precio_final'] = self._string_to_decimal(cleaned_data['precio_final'])
        
        if 'margen_porcentaje' in cleaned_data and cleaned_data['margen_porcentaje']:
            cleaned_data['margen_porcentaje'] = self._string_to_decimal(cleaned_data['margen_porcentaje'])
        
        if 'impuesto_especifico' in cleaned_data and cleaned_data['impuesto_especifico']:
            cleaned_data['impuesto_especifico'] = self._string_to_decimal(cleaned_data['impuesto_especifico'])
        
        return cleaned_data
    
    def _string_to_decimal(self, value):
        """Convierte string a Decimal manejando formato chileno"""
        if not value:
            return Decimal('0')
        
        try:
            # Convertir formato chileno a decimal
            value_str = str(value).replace('.', '').replace(',', '.')
            return Decimal(value_str)
        except:
            return Decimal('0')


class CategoriaArticuloForm(forms.ModelForm):
    """Formulario para categorías de artículos"""
    
    class Meta:
        model = CategoriaArticulo
        fields = ['codigo', 'nombre', 'descripcion', 'exenta_iva', 'impuesto_especifico', 'activa']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: ACC, AMB, etc.'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'exenta_iva': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'impuesto_especifico': forms.Select(attrs={'class': 'form-select'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre'].required = True
        
        # Filtrar impuestos específicos por empresa
        empresa = None
        
        # Obtener empresa de initial (para formularios nuevos)
        if 'initial' in kwargs and isinstance(kwargs['initial'], dict) and 'empresa' in kwargs['initial']:
            empresa = kwargs['initial']['empresa']
        # Obtener empresa de la instancia (para formularios de edición)
        elif hasattr(self, 'instance') and self.instance and getattr(self.instance, 'empresa', None):
            empresa = self.instance.empresa
        
        if empresa:
            self.fields['impuesto_especifico'].queryset = self.fields['impuesto_especifico'].queryset.filter(
                empresa=empresa, activa=True
            )
    
    def clean_nombre(self):
        nombre = self.cleaned_data['nombre']
        if len(nombre.strip()) < 3:
            raise ValidationError('El nombre debe tener al menos 3 caracteres.')
        return nombre.strip()




class UnidadMedidaForm(forms.ModelForm):
    """Formulario para unidades de medida"""
    
    class Meta:
        model = UnidadMedida
        fields = ['nombre', 'simbolo', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'simbolo': forms.TextInput(attrs={'class': 'form-control'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre'].required = True
        self.fields['simbolo'].required = True
    
    def clean_nombre(self):
        nombre = self.cleaned_data['nombre']
        if len(nombre.strip()) < 2:
            raise ValidationError('El nombre debe tener al menos 2 caracteres.')
        return nombre.strip()
    
    def clean_simbolo(self):
        simbolo = self.cleaned_data['simbolo']
        if len(simbolo.strip()) < 1:
            raise ValidationError('El símbolo debe tener al menos 1 carácter.')
        return simbolo.strip()


class ImpuestoEspecificoForm(forms.ModelForm):
    """Formulario para impuestos específicos"""
    
    class Meta:
        model = ImpuestoEspecifico
        fields = ['nombre', 'descripcion', 'porcentaje', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'porcentaje': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre'].required = True
        self.fields['porcentaje'].required = True
        
        # Obtener empresa de initial (para formularios nuevos)
        if 'initial' in kwargs and isinstance(kwargs['initial'], dict) and 'empresa' in kwargs['initial']:
            empresa = kwargs['initial']['empresa']
            # No hay campos que filtrar por empresa en este formulario
            # pero podemos usar la empresa para validaciones si es necesario
    
    def clean_nombre(self):
        nombre = self.cleaned_data['nombre']
        if len(nombre.strip()) < 3:
            raise ValidationError('El nombre debe tener al menos 3 caracteres.')
        return nombre.strip()
    
    def clean_porcentaje(self):
        porcentaje = self.cleaned_data.get('porcentaje')
        if porcentaje:
            try:
                # Convertir formato chileno a decimal
                valor = str(porcentaje).replace('.', '').replace(',', '.')
                valor_decimal = Decimal(valor)
                if valor_decimal < 0:
                    raise ValidationError('El porcentaje no puede ser negativo.')
                if valor_decimal > 100:
                    raise ValidationError('El porcentaje no puede ser mayor a 100%.')
                return str(porcentaje).strip()
            except:
                raise ValidationError('Ingrese un porcentaje válido.')
        return '0.00'


class ListaPrecioForm(forms.ModelForm):
    """Formulario para crear y editar listas de precios"""
    
    class Meta:
        model = ListaPrecio
        fields = ['nombre', 'descripcion', 'activa', 'es_predeterminada']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Precio Mayorista'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción de la lista de precios'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'es_predeterminada': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PrecioArticuloForm(forms.ModelForm):
    """Formulario para asignar precios a artículos en listas"""
    
    class Meta:
        model = PrecioArticulo
        fields = ['articulo', 'lista_precio', 'precio']
        widgets = {
            'articulo': forms.Select(attrs={'class': 'form-select'}),
            'lista_precio': forms.Select(attrs={'class': 'form-select'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }
    
    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if empresa:
            self.fields['articulo'].queryset = Articulo.objects.filter(empresa=empresa, activo=True)
            self.fields['lista_precio'].queryset = ListaPrecio.objects.filter(empresa=empresa, activa=True)


class HomologacionCodigoForm(forms.ModelForm):
    """Formulario para homologación de códigos por proveedor"""
    
    class Meta:
        model = HomologacionCodigo
        fields = [
            'proveedor', 'codigo_proveedor', 'descripcion_proveedor',
            'precio_compra', 'es_principal', 'activo', 'observaciones'
        ]
        widgets = {
            'proveedor': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'codigo_proveedor': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Código del proveedor'
            }),
            'descripcion_proveedor': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Descripción según proveedor (opcional)'
            }),
            'precio_compra': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm text-end',
                'min': '0',
                'step': '1'
            }),
            'es_principal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 2,
                'placeholder': 'Observaciones adicionales (opcional)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if empresa:
            self.fields['proveedor'].queryset = Proveedor.objects.filter(empresa=empresa, estado='activo')
    
    def clean(self):
        cleaned_data = super().clean()
        es_principal = cleaned_data.get('es_principal')
        articulo = self.instance.articulo if self.instance.pk else None
        
        # Si se marca como principal, desmarcar otros
        if es_principal and articulo:
            HomologacionCodigo.objects.filter(
                articulo=articulo,
                es_principal=True
            ).exclude(pk=self.instance.pk).update(es_principal=False)
        
        return cleaned_data


class KitOfertaForm(forms.ModelForm):
    """Formulario para crear y editar kits de ofertas"""
    
    class Meta:
        model = KitOferta
        fields = [
            'codigo', 'nombre', 'descripcion', 'imagen', 'precio_kit',
            'descuento_porcentaje', 'fecha_inicio', 'fecha_fin',
            'stock_disponible', 'activo', 'destacado', 'observaciones'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Código del kit'
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Nombre del kit'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 3,
                'placeholder': 'Descripción del kit'
            }),
            'imagen': forms.FileInput(attrs={
                'class': 'form-control form-control-sm'
            }),
            'precio_kit': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm text-end',
                'min': '0',
                'step': '1'
            }),
            'descuento_porcentaje': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm text-end',
                'min': '0',
                'max': '100',
                'step': '0.01'
            }),
            'fecha_inicio': forms.DateInput(attrs={
                'class': 'form-control form-control-sm',
                'type': 'date'
            }),
            'fecha_fin': forms.DateInput(attrs={
                'class': 'form-control form-control-sm',
                'type': 'date'
            }),
            'stock_disponible': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm text-center',
                'min': '0'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'destacado': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 2,
                'placeholder': 'Observaciones adicionales'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')
        
        if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
            raise ValidationError('La fecha de inicio no puede ser posterior a la fecha de fin')
        
        return cleaned_data


class KitOfertaItemForm(forms.ModelForm):
    """Formulario para items de kit de oferta"""
    
    class Meta:
        model = KitOfertaItem
        fields = ['articulo', 'cantidad', 'orden', 'observaciones']
        widgets = {
            'articulo': forms.Select(attrs={
                'class': 'form-select form-select-sm'
            }),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm text-center',
                'min': '1',
                'value': '1'
            }),
            'orden': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm text-center',
                'min': '0',
                'value': '0'
            }),
            'observaciones': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Observaciones (opcional)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        if empresa:
            self.fields['articulo'].queryset = Articulo.objects.filter(
                empresa=empresa,
                activo=True
            ).order_by('nombre')
