"""
Formularios para el módulo de usuarios
"""
from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm
from .models import PerfilUsuario
from empresas.models import Empresa


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
        label='Grupo/Rol',
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
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'empresa', 'grupo', 'is_staff']
        
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
        
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_staff = self.cleaned_data.get('is_staff', False)
        
        if commit:
            user.save()
            
            # Crear o actualizar perfil asociado a la empresa
            # Usamos get_or_create porque la señal post_save puede haber creado el perfil
            perfil, created = PerfilUsuario.objects.get_or_create(
                usuario=user,
                defaults={'empresa': self.cleaned_data['empresa']}
            )
            
            # Si el perfil ya existía, actualizamos la empresa
            if not created:
                perfil.empresa = self.cleaned_data['empresa']
                perfil.save()
            
            # Asignar grupo si se especificó
            grupo = self.cleaned_data.get('grupo')
            if grupo:
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
        label='Grupo/Rol',
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
                
    def save(self, commit=True):
        user = super().save(commit=False)
        
        if commit:
            user.save()
            
            # Actualizar el perfil
            if hasattr(user, 'perfil'):
                user.perfil.es_activo = user.is_active
                user.perfil.save()
            
            # Actualizar grupo
            user.groups.clear()
            grupo = self.cleaned_data.get('grupo')
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

