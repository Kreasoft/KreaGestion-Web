from django import forms
from .models import ArchivoCAF, DocumentoTributarioElectronico


class ArchivoCAFForm(forms.ModelForm):
    """Formulario para cargar archivos CAF"""
    
    folio_inicial = forms.IntegerField(
        required=False,
        label='Folio Inicial (Opcional)',
        help_text='Si ya has usado folios de este CAF, indica desde qué número empezar. Dejar vacío para comenzar desde el primer folio.',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 15 (si ya usaste hasta el 14)',
            'min': '1'
        })
    )
    
    class Meta:
        model = ArchivoCAF
        fields = [
            'tipo_documento',
            'archivo_xml',
        ]
        widgets = {
            'tipo_documento': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'archivo_xml': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.xml',
                'required': True
            }),
        }
        labels = {
            'tipo_documento': 'Tipo de Documento Tributario',
            'archivo_xml': 'Archivo CAF (XML)',
        }
        help_texts = {
            'archivo_xml': 'Suba el archivo XML del CAF descargado desde el sitio del SII.',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer que los campos sean obligatorios, excepto el folio inicial
        for field_name, field_object in self.fields.items():
            if field_name != 'folio_inicial':
                field_object.required = True

