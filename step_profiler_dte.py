
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
        
        print("\n--- INICIO PROFILING PASO A PASO ---")
        
        t0 = time.time()
        # Mocking the render function to see how long it takes to prepare context vs render
        from django.shortcuts import render as original_render
        
        def mock_render(req, template, context):
            tr0 = time.time()
            print(f"[PROGRESS] Iniciando render de {template}...")
            res = original_render(req, template, context)
            tr1 = time.time()
            print(f"[PROGRESS] Render finalizado en {tr1 - tr0:.2f} s")
            return res
            
        import facturacion_electronica.views_dte
        facturacion_electronica.views_dte.render = mock_render
        
        response = ver_factura_electronica(request, dte_id)
        t_total = time.time() - t0
        
        print(f"--- FIN PROFILING: {t_total:.2f} s total ---")
            
    except Exception as e:
        import traceback
        print(f"Excepción: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    test_view()
