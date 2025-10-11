from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Articulo, CategoriaArticulo, UnidadMedida, StockArticulo, ImpuestoEspecifico, ListaPrecio, PrecioArticulo


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
            )
            self.fields['unidad_medida'].queryset = UnidadMedida.objects.filter(
                empresa=empresa, activa=True
            )
        
    
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
        fields = ['nombre', 'descripcion', 'exenta_iva', 'impuesto_especifico', 'activa']
        widgets = {
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
