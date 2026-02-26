
import os
import django
import sys
import time
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
        
        # Simular request
        factory = RequestFactory()
        user = User.objects.filter(is_superuser=True).first()
        request = factory.get(f'/facturacion-electronica/dte/{dte_id}/ver-factura/')
        request.user = user
        request.session = MagicMock()
        request.session.get.return_value = dte.empresa.id
        request.empresa = dte.empresa
        
        print(f"Perfilando view para DTE {dte_id}...")
        pr = cProfile.Profile()
        pr.enable()
        
        response = ver_factura_electronica(request, dte_id)
        
        pr.disable()
        s = io.StringIO()
        sortby = 'cumulative'
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats(20)  # Top 20 slow calls
        print(s.getvalue())
        
        print(f"Status Code: {response.status_code}")
            
    except Exception as e:
        import traceback
        print(f"Excepción: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    test_view()
