"""
Formularios para el módulo de usuarios
"""
from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password
from .models import PerfilUsuario
from empresas.models import Empresa, Sucursal


class UsuarioCreateForm(UserCreationForm):
    """Formulario para crear un nuevo usuario"""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'correo@ejemplo.com'
        })
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label='Nombre',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre del usuario'
        })
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        label='Apellido',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Apellido del usuario'
        })
    )
    empresa = forms.ModelChoiceField(
        queryset=Empresa.objects.all(),
        required=True,
        label='Empresa',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    grupo = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label='Grupo / Perfil de Permisos',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    tipo_usuario = forms.ChoiceField(
        choices=PerfilUsuario.TIPO_USUARIO_CHOICES,
        required=True,
        initial='administrador',
        label='Tipo de Usuario / Rol Principal',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    sucursal = forms.ModelChoiceField(
        queryset=Sucursal.objects.none(),
        required=False,
        label='Sucursal',
        help_text='Dejar en blanco para permitir acceso a todas las sucursales',
        empty_label='--------- (Todas las sucursales)',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    is_staff = forms.BooleanField(
        required=False,
        label='Acceso al panel de administración',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'empresa', 'tipo_usuario', 'grupo', 'sucursal', 'is_staff']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Nombre de usuario'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Contraseña'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirmar contraseña'
        })
        
        # Etiquetas en español
        self.fields['username'].label = 'Nombre de Usuario'
        self.fields['email'].label = 'Correo Electrónico'
        self.fields['password1'].label = 'Contraseña'
        self.fields['password2'].label = 'Confirmar Contraseña'
        
        # Filtrar sucursales según la empresa seleccionada
        if 'empresa' in self.data:
            try:
                empresa_id = int(self.data.get('empresa'))
                empresa = Empresa.objects.get(id=empresa_id)
                self.fields['sucursal'].queryset = empresa.sucursales.filter(estado='activa').order_by('nombre')
            except (ValueError, TypeError, Empresa.DoesNotExist):
                pass
        elif self.instance and self.instance.pk and hasattr(self.instance, 'perfil') and self.instance.perfil.empresa:
            self.fields['sucursal'].queryset = self.instance.perfil.empresa.sucursales.filter(estado='activa').order_by('nombre')
        else:
            self.fields['sucursal'].queryset = Sucursal.objects.none()
        
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        tipo = self.cleaned_data.get('tipo_usuario', 'administrador')
        grupo = self.cleaned_data.get('grupo')
        
        if grupo and 'admin' in grupo.name.lower():
            tipo = 'administrador'
            
        if tipo == 'administrador':
            user.is_staff = True
        else:
            user.is_staff = self.cleaned_data.get('is_staff', False)
        
        if commit:
            user.save()
            
            # Crear o actualizar perfil asociado a la empresa
            perfil, created = PerfilUsuario.objects.get_or_create(
                usuario=user,
                defaults={
                    'empresa': self.cleaned_data['empresa'],
                    'sucursal': self.cleaned_data.get('sucursal'),
                    'tipo_usuario': tipo
                }
            )
            
            # Actualizamos datos del perfil
            perfil.empresa = self.cleaned_data['empresa']
            perfil.sucursal = self.cleaned_data.get('sucursal')
            perfil.tipo_usuario = tipo
            perfil.save()
            
            # Asignar grupo si se especificó
            if grupo:
                user.groups.clear()
                user.groups.add(grupo)
                
        return user


class UsuarioUpdateForm(forms.ModelForm):
    """Formulario para editar un usuario existente"""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'correo@ejemplo.com'
        })
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label='Nombre',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre del usuario'
        })
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        label='Apellido',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Apellido del usuario'
        })
    )
    grupo = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label='Grupo / Perfil de Permisos',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    tipo_usuario = forms.ChoiceField(
        choices=PerfilUsuario.TIPO_USUARIO_CHOICES,
        required=True,
        label='Tipo de Usuario / Rol Principal',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    sucursal = forms.ModelChoiceField(
        queryset=Sucursal.objects.none(),
        required=False,
        label='Sucursal',
        help_text='Dejar en blanco para permitir acceso a todas las sucursales',
        empty_label='--------- (Todas las sucursales)',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    is_active = forms.BooleanField(
        required=False,
        label='Usuario activo',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    is_staff = forms.BooleanField(
        required=False,
        label='Acceso al panel de administración',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    password1 = forms.CharField(
        required=False,
        label='Nueva contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Dejar vacío para no cambiar',
            'autocomplete': 'new-password'
        })
    )
    password2 = forms.CharField(
        required=False,
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repetir la nueva contraseña',
            'autocomplete': 'new-password'
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Nombre de usuario',
            'readonly': True  # No permitir cambiar el username
        })
        
        # Etiquetas en español
        self.fields['username'].label = 'Nombre de Usuario'
        self.fields['email'].label = 'Correo Electrónico'
        
        # Precargar el grupo actual del usuario
        if self.instance.pk:
            grupo_actual = self.instance.groups.first()
            if grupo_actual:
                self.fields['grupo'].initial = grupo_actual
            
            # Precargar la sucursal y tipo_usuario actual del usuario
            if hasattr(self.instance, 'perfil') and self.instance.perfil:
                self.fields['sucursal'].initial = self.instance.perfil.sucursal
                self.fields['tipo_usuario'].initial = self.instance.perfil.tipo_usuario
                # Filtrar sucursales por la empresa del usuario
                if self.instance.perfil.empresa:
                    self.fields['sucursal'].queryset = self.instance.perfil.empresa.sucursales.filter(
                        estado='activa'
                    ).order_by('nombre')
        else:
            self.fields['sucursal'].queryset = Sucursal.objects.none()

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError('Las contraseñas no coinciden.')
            if password1:
                validate_password(password1, self.instance)
        return password2
                
    def save(self, commit=True):
        user = super().save(commit=False)
        nueva_password = self.cleaned_data.get('password1')
        if nueva_password:
            user.set_password(nueva_password)
            
        tipo = self.cleaned_data.get('tipo_usuario')
        grupo = self.cleaned_data.get('grupo')
        
        if grupo and 'admin' in grupo.name.lower():
            tipo = 'administrador'
            
        if tipo == 'administrador':
            user.is_staff = True
        
        if commit:
            user.save()
            
            # Actualizar o crear el perfil
            from empresas.models import Empresa
            empresa_default = Empresa.objects.first()
            perfil, _ = PerfilUsuario.objects.get_or_create(
                usuario=user,
                defaults={'empresa': empresa_default, 'tipo_usuario': tipo or 'administrador'}
            )
            perfil.es_activo = user.is_active
            perfil.sucursal = self.cleaned_data.get('sucursal')
            if tipo:
                perfil.tipo_usuario = tipo
            perfil.save()
            
            # Actualizar grupo
            user.groups.clear()
            if grupo:
                user.groups.add(grupo)
                
        return user


class GrupoForm(forms.ModelForm):
    """Formulario para crear/editar grupos"""
    name = forms.CharField(
        max_length=150,
        required=True,
        label='Nombre del Grupo/Rol',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: Administrador, Vendedor, Bodeguero, etc.'
        })
    )
    
    class Meta:
        model = Group
        fields = ['name']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].help_text = 'Nombre descriptivo para el rol/grupo de usuarios'

from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate, get_user_model

class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    """Formulario de login que permite usar nombre de usuario o correo electrónico"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Usuario o Correo Electrónico'
        self.fields['username'].widget.attrs.update({
            'placeholder': 'Ingresa tu usuario o email'
        })

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            # Primero intentar con el método estándar (username)
            self.user_cache = authenticate(self.request, username=username, password=password)
            
            if self.user_cache is None:
                # Si falla, intentar buscar el usuario por email
                UserModel = get_user_model()
                try:
                    # Buscar el usuario por el correo proporcionado
                    user = UserModel.objects.filter(email__iexact=username).first()
                    if user:
                        # Si encontramos el usuario por email, autenticar usando su username real
                        self.user_cache = authenticate(self.request, username=user.username, password=password)
                except Exception:
                    pass

            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data
