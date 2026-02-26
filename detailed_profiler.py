
import os
import django
import sys
import cProfile
import pstats
import io

# Configurar entorno Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from django.test import RequestFactory
from django.contrib.auth.models import User
from facturacion_electronica.views_dte import ver_factura_electronica
from unittest.mock import MagicMock

def test_view():
    dte_id = 131
    try:
        dte = DocumentoTributarioElectronico.objects.get(pk=dte_id)
        factory = RequestFactory()
        user = User.objects.filter(is_superuser=True).first()
        request = factory.get(f'/facturacion-electronica/dte/{dte_id}/ver-factura/')
        request.user = user
        request.session = MagicMock()
        request.session.get.return_value = dte.empresa.id
        request.empresa = dte.empresa
        
        print(f"Perfilando renderizado para DTE {dte_id}...")
        pr = cProfile.Profile()
        pr.enable()
        
        response = ver_factura_electronica(request, dte_id)
        # Forzar el render para capturar el tiempo real de procesamiento del template
        if hasattr(response, 'render'):
            response.render()
        
        pr.disable()
        
        # Guardar resultados en archivo para análisis completo
        with open('profile_results.txt', 'w') as f:
            ps = pstats.Stats(pr, stream=f).sort_stats('cumulative')
            ps.print_stats(100)
            
        print("Perfilado completado. Resultados guardados en profile_results.txt")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_view()
