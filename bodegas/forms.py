from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from .models import Bodega
from empresas.models import Sucursal
from django.core.exceptions import ValidationError

class BodegaForm(forms.ModelForm):
    class Meta:
        model = Bodega
        fields = ['codigo', 'nombre', 'sucursal', 'activa']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Código único'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la bodega'}),
            'sucursal': forms.Select(attrs={'class': 'form-select'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar sucursales por empresa
        if self.request and self.request.empresa:
            self.fields['sucursal'].queryset = Sucursal.objects.filter(
                empresa=self.request.empresa,
                estado='activa'
            ).order_by('nombre')
            self.fields['sucursal'].empty_label = "Sin sucursal asignada"
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'codigo',
            'nombre',
            'sucursal',
            'activa',
            HTML('<hr>'),
            Div(
                Submit('submit', 'Guardar', css_class='btn btn-primary me-2'),
                HTML('<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>'),
                css_class='d-flex justify-content-end mt-3'
            )
        )

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if self.request and self.request.empresa:
            # Verificar si ya existe una bodega con el mismo código para la misma empresa
            qs = Bodega.objects.filter(empresa=self.request.empresa, codigo__iexact=codigo)
            if self.instance.pk:  # Si estamos editando una bodega existente
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Ya existe una bodega con este código para su empresa.")
        return codigo

class BodegaFilterForm(forms.Form):
    """Formulario simple para filtrar bodegas"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Buscar por código o nombre...'})
    )
    activa = forms.ChoiceField(
        choices=[('', 'Todas'), ('true', 'Activas'), ('false', 'Inactivas')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.layout = Layout(
            Row(
                Column('search', css_class='form-group col-md-8 mb-0'),
                Column('activa', css_class='form-group col-md-4 mb-0'),
                css_class='form-row'
            ),
            HTML('<div class="text-center mt-3">'),
            Submit('submit', 'Filtrar', css_class='btn btn-primary me-2'),
            HTML('<a href="." class="btn btn-outline-secondary">Limpiar</a>'),
            HTML('</div>')
        )