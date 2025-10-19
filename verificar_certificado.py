import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa

print("=== TODAS LAS EMPRESAS ===")
for empresa in Empresa.objects.all():
    print(f"\nEmpresa: {empresa.nombre} (ID: {empresa.id})")
    print(f"Certificado: {empresa.certificado_digital}")
    if empresa.certificado_digital:
        print(f"Certificado existe: {os.path.exists(empresa.certificado_digital.path)}")
        print(f"Ruta: {empresa.certificado_digital.path}")
    print(f"Password guardado: {'Sí' if empresa.password_certificado else 'No'}")
    print(f"Password: {empresa.password_certificado}")
    print(f"FE activada: {empresa.facturacion_electronica}")
