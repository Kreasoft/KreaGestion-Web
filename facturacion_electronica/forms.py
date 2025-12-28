"""
Formularios para gestión de CAFs
"""
from django import forms
from facturacion_electronica.models import ArchivoCAF
from empresas.models import Sucursal
import xml.etree.ElementTree as ET
from datetime import datetime


class CargarCAFForm(forms.ModelForm):
    """Formulario para cargar un nuevo archivo CAF"""
    
    class Meta:
        model = ArchivoCAF
        fields = ['sucursal', 'tipo_documento', 'archivo_xml']
        widgets = {
            'sucursal': forms.Select(attrs={'class': 'form-select'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'archivo_xml': forms.FileInput(attrs={'class': 'form-control', 'accept': '.xml'}),
        }
    
    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop('empresa', None)
        super().__init__(*args, **kwargs)
        
        # Guardar empresa para validación
        self.empresa = empresa
        
        if empresa:
            # Filtrar sucursales por empresa
            self.fields['sucursal'].queryset = Sucursal.objects.filter(empresa=empresa)
        
        # Labels personalizados
        self.fields['sucursal'].label = 'Sucursal'
        self.fields['tipo_documento'].label = 'Tipo de Documento'
        self.fields['archivo_xml'].label = 'Archivo XML del CAF'
        
        # Help texts
        self.fields['sucursal'].help_text = 'Sucursal a la que pertenecerá este CAF'
        self.fields['archivo_xml'].help_text = 'Archivo XML con extensión .xml descargado del SII'
    
    def clean_archivo_xml(self):
        """Valida y procesa el archivo XML del CAF"""
        archivo = self.cleaned_data.get('archivo_xml')
        
        if not archivo:
            raise forms.ValidationError('Debe seleccionar un archivo XML')
        
        # Validar extensión
        if not archivo.name.endswith('.xml'):
            raise forms.ValidationError('El archivo debe tener extensión .xml')
        
        try:
            # Leer contenido del archivo - SII usa ISO-8859-1
            contenido_bytes = archivo.read()
            contenido = None
            
            # Intentar múltiples codificaciones
            for encoding in ['iso-8859-1', 'utf-8', 'windows-1252', 'latin-1']:
                try:
                    contenido = contenido_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if contenido is None:
                raise forms.ValidationError('No se pudo decodificar el archivo. Formato no soportado.')
            
            archivo.seek(0)  # Resetear puntero para guardarlo después
            
            # Parsear XML
            root = ET.fromstring(contenido)
            
            # Extraer datos del CAF
            # Buscar elemento CAF
            caf_element = root.find('.//CAF')
            if caf_element is None:
                caf_element = root.find('.//{http://www.sii.cl/SiiDte}CAF')
            
            if caf_element is None:
                raise forms.ValidationError('No se encontró elemento CAF en el XML')
            
            # Extraer DA (Datos de Autorización)
            da = caf_element.find('.//DA')
            if da is None:
                raise forms.ValidationError('No se encontró elemento DA en el CAF')
            
            # Extraer datos
            rng = da.find('.//RNG')
            if rng is None:
                raise forms.ValidationError('No se encontró rango de folios en el CAF')
            
            folio_desde = int(rng.findtext('D', '0'))
            folio_hasta = int(rng.findtext('H', '0'))
            
            if folio_desde == 0 or folio_hasta == 0:
                raise forms.ValidationError('Rango de folios inválido')
            
            # Extraer fecha de autorización
            fecha_aut_text = da.findtext('.//FA', '')
            try:
                fecha_autorizacion = datetime.strptime(fecha_aut_text, '%Y-%m-%d').date()
            except:
                raise forms.ValidationError('Fecha de autorización inválida en el CAF')
            
            # Extraer firma electrónica (FRMA)
            frma = caf_element.find('.//FRMA')
            if frma is None:
                raise forms.ValidationError('No se encontró firma electrónica en el CAF')
            
            firma_electronica = frma.text.strip() if frma.text else ''
            
            # Guardar datos extraídos en el formulario
            self.caf_data = {
                'folio_desde': folio_desde,
                'folio_hasta': folio_hasta,
                'cantidad_folios': folio_hasta - folio_desde + 1,
                'fecha_autorizacion': fecha_autorizacion,
                'firma_electronica': firma_electronica,
                'contenido_caf': contenido,
                'folio_actual': folio_desde - 1,  # Inicialmente sin uso
            }
            
            return archivo
            
        except ET.ParseError as e:
            raise forms.ValidationError(f'Error al parsear XML: {str(e)}')
        except Exception as e:
            raise forms.ValidationError(f'Error al procesar CAF: {str(e)}')
    
    def clean(self):
        """Validación adicional: verificar que no exista ya un CAF con el mismo rango"""
        cleaned_data = super().clean()
        
        if hasattr(self, 'caf_data') and self.empresa:
            tipo_documento = cleaned_data.get('tipo_documento')
            
            # Verificar si ya existe un CAF con este rango
            if tipo_documento:
                existe = ArchivoCAF.objects.filter(
                    empresa=self.empresa,
                    tipo_documento=tipo_documento,
                    folio_desde=self.caf_data['folio_desde'],
                    folio_hasta=self.caf_data['folio_hasta']
                ).exists()
                
                if existe:
                    raise forms.ValidationError(
                        f'Ya existe un CAF para {dict(ArchivoCAF.TIPO_DOCUMENTO_CHOICES).get(tipo_documento, tipo_documento)} '
                        f'con el rango de folios {self.caf_data["folio_desde"]}-{self.caf_data["folio_hasta"]}. '
                        f'Por favor, verifique los CAFs existentes.'
                    )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Guarda el CAF con los datos extraídos del XML"""
        instance = super().save(commit=False)
        
        # Asignar datos extraídos del XML
        if hasattr(self, 'caf_data'):
            for key, value in self.caf_data.items():
                setattr(instance, key, value)
        
        if commit:
            instance.save()
        
        return instance
