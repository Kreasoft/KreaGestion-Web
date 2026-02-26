
import os
import django
import sys
import time

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
        
        print("\n--- PROFILING CON FILTROS MOCKEADOS ---")
        
        # Mocking format_miles
        from ventas.templatetags import format_filters
        format_filters.format_miles = lambda x: str(x)
        format_filters.format_precio = lambda x: str(x)
        format_filters.format_moneda = lambda x: f"${x}"
        
        # Re-registrarlos si es necesario (Django los cachea)
        # Pero aquí estamos en el mismo proceso, debería funcionar si se importan después
        
        t0 = time.time()
        response = ver_factura_electronica(request, dte_id)
        # Forzar el render ya que es lo que medimos
        response.render()
        t_total = time.time() - t0
        
        print(f"--- FIN PROFILING: {t_total:.2f} s total ---")
            
    except Exception as e:
        import traceback
        print(f"Excepción: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    test_view()
