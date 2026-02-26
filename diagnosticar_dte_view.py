
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
from facturacion_electronica.pdf417_generator import PDF417Generator
from unittest.mock import MagicMock

def test_view():
    dte_id = 131
    try:
        dte = DocumentoTributarioElectronico.objects.get(pk=dte_id)
        print(f"Probando DTE {dte.id} - Folio {dte.folio}")
        print(f"Tipo DTE: {dte.tipo_dte}")
        print(f"Longitud TED: {len(dte.timbre_electronico) if dte.timbre_electronico else 0}")
        
        has_timbre = bool(dte.timbre_pdf417)
        timbre_size = dte.timbre_pdf417.size if has_timbre else 0
        print(f"Tiene timbre: {has_timbre}, Tamaño: {timbre_size}")

        if dte.timbre_electronico:
            print("Probando tiempo de generación de PDF417...")
            t0 = time.time()
            # Simulamos lo que hace la vista
            data = dte.timbre_electronico
            # Generar imagen bytes
            img = PDF417Generator.generar_imagen_pdf417(data)
            t1 = time.time()
            print(f"Generación PDF417 manual exitosa: {len(img)} bytes en {t1 - t0:.2f} s")

        # Simular request
        factory = RequestFactory()
        user = User.objects.filter(is_superuser=True).first()
        request = factory.get(f'/facturacion-electronica/dte/{dte_id}/ver-factura/')
        request.user = user
        request.session = MagicMock()
        request.session.get.return_value = dte.empresa.id
        request.empresa = dte.empresa
        
        print("\nLlamando a la vista ver_factura_electronica...")
        start_time = time.time()
        response = ver_factura_electronica(request, dte_id)
        end_time = time.time()
        
        print(f"Vista finalizada en {end_time - start_time:.2f} segundos")
        print(f"Status Code: {response.status_code}")
            
    except Exception as e:
        import traceback
        print(f"Excepción: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    test_view()
