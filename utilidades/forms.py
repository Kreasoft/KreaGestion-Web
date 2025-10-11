from django import forms


class ConexionMySQLForm(forms.Form):
    """Formulario para conectar a base de datos MySQL"""
    host = forms.CharField(
        label='Host',
        max_length=255,
        initial='localhost',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'localhost o IP del servidor'
        })
    )
    
    puerto = forms.IntegerField(
        label='Puerto',
        initial=3306,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '3306'
        })
    )
    
    base_datos = forms.CharField(
        label='Nombre de la Base de Datos',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'nombre_base_datos'
        })
    )
    
    usuario = forms.CharField(
        label='Usuario',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'root'
        })
    )
    
    contrasena = forms.CharField(
        label='Contraseña',
        max_length=255,
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contraseña (opcional)'
        })
    )


class SeleccionTablaForm(forms.Form):
    """Formulario para seleccionar qué importar"""
    OPCIONES = [
        ('clientes', 'Clientes'),
        ('proveedores', 'Proveedores'),
        ('articulos', 'Artículos'),
        ('familias', 'Familias de Artículos'),
    ]
    
    tipo_importacion = forms.ChoiceField(
        label='¿Qué deseas importar?',
        choices=OPCIONES,
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        })
    )
    
    tabla_origen = forms.CharField(
        label='Nombre de la tabla en MySQL',
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: clientes, tbl_clientes, etc.'
        })
    )
