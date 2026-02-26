"""
Diagnóstico completo de certificado vs RUT empresa
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend
from cryptography import x509

def diagnosticar_certificado():
    empresa = Empresa.objects.get(pk=1)
    
    print("="*60)
    print("DIAGNÓSTICO DE CERTIFICADO VS RUT EMPRESA")
    print("="*60)
    print(f"\n📋 EMPRESA:")
    print(f"   Nombre: {empresa.nombre}")
    print(f"   RUT configurado: {empresa.rut}")
    print(f"   Certificado: {empresa.certificado_digital.path}")
    print()
    
    # Leer certificado
    with open(empresa.certificado_digital.path, 'rb') as f:
        pfx_data = f.read()
    
    private_key, certificate, additional = pkcs12.load_key_and_certificates(
        pfx_data,
        empresa.password_certificado.encode(),
        backend=default_backend()
    )
    
    # Extraer RUT del certificado (del SubjectAlternativeName)
    rut_certificado = None
    for ext in certificate.extensions:
        if ext.oid.dotted_string == '2.5.29.17':  # SubjectAlternativeName
            for name in ext.value:
                if hasattr(name, 'type_id') and name.type_id.dotted_string == '1.3.6.1.4.1.8321.1':
                    # Es el RUT
                    valor = name.value.decode('utf-8', errors='ignore')
                    # Limpiar el valor (viene con bytes adicionales)
                    import re
                    rut_match = re.search(r'[\d\.]+-\d', valor)
                    if rut_match:
                        rut_certificado = rut_match.group(0)
    
    print(f"📜 CERTIFICADO:")
    print(f"   Subject: {certificate.subject}")
    print(f"   Serial: {certificate.serial_number}")
    print(f"   Válido desde: {certificate.not_valid_before}")
    print(f"   Válido hasta: {certificate.not_valid_after}")
    print()
    
    if rut_certificado:
        print(f"   RUT en certificado: {rut_certificado}")
        print(f"   RUT en empresa: {empresa.rut}")
        print()
        
        # Normalizar RUTs para comparar
        rut_cert_limpio = rut_certificado.replace('.', '').replace('-', '').upper()
        rut_emp_limpio = empresa.rut.replace('.', '').replace('-', '').upper()
        
        if rut_cert_limpio == rut_emp_limpio:
            print("   ✅ RUT COINCIDE - El certificado es válido para esta empresa")
        else:
            print("   ❌ RUT NO COINCIDE - Este es el problema!")
            print()
            print("   El certificado pertenece a:")
            print(f"      RUT: {rut_certificado}")
            print()
            print("   Pero la empresa tiene configurado:")
            print(f"      RUT: {empresa.rut}")
            print()
            print("   SOLUCIÓN:")
            print("   1. Cambiar el RUT de la empresa a:", rut_certificado)
            print("   2. O usar un certificado del RUT:", empresa.rut)
    else:
        print("   ⚠️ No se pudo extraer el RUT del certificado")
        print("   Subject completo:")
        for attr in certificate.subject:
            print(f"      {attr.oid.dotted_string}: {attr.value}")

if __name__ == '__main__':
    diagnosticar_certificado()
