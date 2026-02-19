
import os
import django
import sys

# Setup Django environment
sys.path.append(r'c:\PROJECTOS-WEB\GestionCloud')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from empresas.models import Empresa

def check_dtes():
    # Obtener primera empresa (o la que se usa en las pruebas)
    empresa = Empresa.objects.first()
    if not empresa:
        print("No hay empresas")
        return

    print(f"Empresa actual: {empresa.nombre} RUT: {empresa.rut}")
    
    # Buscar DTEs de la empresa
    dtes = DocumentoTributarioElectronico.objects.filter(empresa=empresa)
    print(f"Total DTEs vinculados a la empresa: {dtes.count()}")
    
    # Verificar emisores
    emisores = dtes.values_list('rut_emisor', flat=True).distinct()
    print("\nRUTs Emisores encontrados en la tabla:")
    for rut in emisores:
        if not rut: continue
        rut_norm = rut.replace('.','').replace('-','').upper()
        empresa_rut_norm = empresa.rut.replace('.','').replace('-','').upper()
        es_propio = (rut_norm == empresa_rut_norm)
        print(f" - {rut} {'(PROPIO)' if es_propio else '(TERCERO - Probable Recibido)'}")
        
    # Contar cuántos de cada (aprox)
    # Nota: la comparación estricta puede fallar por puntos/guiones, pero veremos los outputs
    print(f"\nVerificando cuantos no coinciden con {empresa.rut} (Normalizado)")
    
    rut_empresa_norm = empresa.rut.replace('.','').replace('-','').upper()
    
    count_ajenos = 0
    for dte in dtes:
        rut_emisor_norm = dte.rut_emisor.replace('.','').replace('-','').upper()
        if rut_emisor_norm != rut_empresa_norm:
            count_ajenos += 1
            if count_ajenos <= 5:
                print(f"    AJENO! ID: {dte.id} Folio: {dte.folio} Emisor: {dte.rut_emisor} Receptor: {dte.rut_receptor}")

    print(f"Total Ajenos (RUT Emisor != Empresa): {count_ajenos}")

if __name__ == '__main__':
    check_dtes()
