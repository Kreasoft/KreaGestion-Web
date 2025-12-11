from django import forms
from django.core.exceptions import ValidationError
from .models import Cliente, ContactoCliente
from empresas.models import Empresa


class ClienteForm(forms.ModelForm):
    """Formulario para clientes con validaciones"""
    
    class Meta:
        model = Cliente
        fields = [
            'rut', 'nombre', 'tipo_cliente', 'giro',
            'direccion', 'comuna', 'ciudad', 'region', 'telefono', 'email', 'sitio_web',
            'limite_credito', 'plazo_pago', 'descuento_porcentaje', 'ruta', 'estado', 'observaciones'
        ]
        widgets = {
            'rut': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12.345.678-9 o 12345678-9', 'id': 'rut-input'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del cliente'}),
            'tipo_cliente': forms.Select(attrs={'class': 'form-control'}),
            'giro': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Giro comercial'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Dirección completa'}),
            'comuna': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Comuna'}),
            'ciudad': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ciudad'}),
            'region': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Región'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+56 9 1234 5678'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'sitio_web': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'www.ejemplo.cl o https://www.ejemplo.cl'}),
            'limite_credito': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'plazo_pago': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '30'}),
            'descuento_porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'ruta': forms.Select(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Observaciones adicionales'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar rutas por empresa si está disponible
        if self.empresa:
            from pedidos.models_rutas import Ruta
            self.fields['ruta'].queryset = Ruta.objects.filter(empresa=self.empresa, activo=True).order_by('codigo')
        else:
            from pedidos.models_rutas import Ruta
            self.fields['ruta'].queryset = Ruta.objects.filter(activo=True).order_by('codigo')
        
        # Hacer campo ruta opcional
        self.fields['ruta'].required = False
        self.fields['ruta'].empty_label = 'Sin ruta asignada'
        
        # Hacer campos requeridos
        self.fields['rut'].required = True
        self.fields['nombre'].required = True
        self.fields['direccion'].required = True
        self.fields['comuna'].required = True
        self.fields['ciudad'].required = True
        # region no es requerido
        self.fields['region'].required = False
        self.fields['telefono'].required = True
    
    def clean_rut(self):
        rut = self.cleaned_data.get('rut', '')
        if not rut:
            raise ValidationError('El RUT es obligatorio.')
        
        # Limpiar el RUT (quitar puntos y guiones)
        rut_limpio = rut.strip().replace('.', '').replace('-', '')
        
        # Validar longitud
        if len(rut_limpio) < 8 or len(rut_limpio) > 9:
            raise ValidationError('El RUT debe tener entre 8 y 9 dígitos.')
        
        # Validar que solo contenga números y K
        if not rut_limpio[:-1].isdigit() or rut_limpio[-1] not in '0123456789Kk':
            raise ValidationError('El RUT contiene caracteres inválidos.')
        
        # Validar dígito verificador
        if not self.validar_digito_verificador(rut_limpio):
            raise ValidationError('El dígito verificador del RUT es inválido.')
        
        # Verificar que el RUT sea único para la empresa
        queryset = Cliente.objects.filter(empresa=self.empresa, rut__icontains=rut_limpio)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise ValidationError('Este RUT ya está siendo usado por otro cliente.')
        
        # Retornar RUT formateado
        return self.formatear_rut(rut_limpio)
    
    def validar_digito_verificador(self, rut_limpio):
        """Valida el dígito verificador del RUT chileno"""
        numero = rut_limpio[:-1]
        dv = rut_limpio[-1].upper()
        
        # Calcular dígito verificador
        suma = 0
        multiplicador = 2
        
        for digito in reversed(numero):
            suma += int(digito) * multiplicador
            multiplicador = multiplicador + 1 if multiplicador < 7 else 2
        
        resto = suma % 11
        dv_calculado = 11 - resto
        
        if dv_calculado == 11:
            dv_calculado = '0'
        elif dv_calculado == 10:
            dv_calculado = 'K'
        else:
            dv_calculado = str(dv_calculado)
        
        return dv == dv_calculado
    
    def formatear_rut(self, rut_limpio):
        """Formatea el RUT con puntos y guión"""
        numero = rut_limpio[:-1]
        dv = rut_limpio[-1].upper()
        
        if len(numero) == 7:
            numero_formateado = f"{numero[0]}.{numero[1:4]}.{numero[4:7]}"
        elif len(numero) == 8:
            numero_formateado = f"{numero[0:2]}.{numero[2:5]}.{numero[5:8]}"
        else:
            return rut_limpio
        
        return f"{numero_formateado}-{dv}"
    
    def clean_nombre(self):
        nombre = self.cleaned_data['nombre']
        if len(nombre.strip()) < 3:
            raise ValidationError('El nombre debe tener al menos 3 caracteres.')
        return nombre.strip()
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        if email:
            # Verificar que el email sea único para la empresa
            queryset = Cliente.objects.filter(empresa=self.empresa, email=email)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise ValidationError('Este email ya está siendo usado por otro cliente.')
        
        return email
    
    def clean_limite_credito(self):
        limite = self.cleaned_data.get('limite_credito')
        if limite is not None and limite < 0:
            raise ValidationError('El límite de crédito no puede ser negativo.')
        return limite or 0
    
    def clean_plazo_pago(self):
        plazo = self.cleaned_data.get('plazo_pago')
        if plazo is not None and plazo < 0:
            raise ValidationError('El plazo de pago no puede ser negativo.')
        return plazo or 30
    
    def clean_descuento_porcentaje(self):
        descuento = self.cleaned_data.get('descuento_porcentaje')
        if descuento is not None:
            if descuento < 0:
                raise ValidationError('El descuento no puede ser negativo.')
            if descuento > 100:
                raise ValidationError('El descuento no puede ser mayor al 100%.')
        return descuento or 0


class ContactoClienteForm(forms.ModelForm):
    """Formulario para contactos de clientes"""
    
    class Meta:
        model = ContactoCliente
        fields = ['nombre', 'cargo', 'tipo_contacto', 'telefono', 'celular', 'email', 'observaciones', 'es_contacto_principal']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del contacto'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cargo o posición'}),
            'tipo_contacto': forms.Select(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+56 2 1234 5678'}),
            'celular': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+56 9 1234 5678'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observaciones del contacto'}),
            'es_contacto_principal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre'].required = True
    
    def clean_nombre(self):
        nombre = self.cleaned_data['nombre']
        if len(nombre.strip()) < 2:
            raise ValidationError('El nombre debe tener al menos 2 caracteres.')
        return nombre.strip()
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        if email:
            # Verificar que el email sea único para el cliente
            if self.instance.pk and self.instance.cliente:
                queryset = ContactoCliente.objects.filter(
                    cliente=self.instance.cliente, 
                    email=email
                ).exclude(pk=self.instance.pk)
                
                if queryset.exists():
                    raise ValidationError('Este email ya está siendo usado por otro contacto del mismo cliente.')
        
        return email


class ContactoClienteInlineFormSet(forms.BaseInlineFormSet):
    """FormSet para manejar múltiples contactos"""
    
    def clean(self):
        if any(self.errors):
            return
        
        contactos_principales = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                if form.cleaned_data.get('es_contacto_principal'):
                    contactos_principales += 1
        
        if contactos_principales > 1:
            raise ValidationError('Solo puede haber un contacto principal por cliente.')
        
        if contactos_principales == 0 and len([f for f in self.forms if f.cleaned_data and not f.cleaned_data.get('DELETE', False)]) > 0:
            raise ValidationError('Debe seleccionar al menos un contacto como principal.')
