#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico, ArchivoCAF
from empresas.models import Empresa

# Buscar la empresa Kreasoft
empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()

if not empresa:
    print("ERROR: No se encontró la empresa Kreasoft")
    exit(1)

print(f"=== EMPRESA: {empresa.nombre} (ID: {empresa.id}) ===\n")

print("=== ÚLTIMOS 10 DTEs GENERADOS ===")
dtes = DocumentoTributarioElectronico.objects.filter(empresa=empresa).order_by('-id')[:10]
for dte in dtes:
    print(f"ID: {dte.id:3} | Folio: {dte.folio:5} | Tipo: {dte.tipo_dte} | "
          f"Fecha: {dte.fecha_emision} | Estado: {dte.estado_sii:10}")

print("\n=== CAFs ACTIVOS ===")
cafs = ArchivoCAF.objects.filter(empresa=empresa, estado='activo')
for caf in cafs:
    print(f"ID: {caf.id} | Tipo: {caf.tipo_documento} | "
          f"Rango: {caf.folio_desde:5}-{caf.folio_hasta:5} | "
          f"Actual: {caf.folio_actual:5} | Usados: {caf.folios_utilizados:3} | "
          f"Sucursal: {caf.sucursal.nombre if caf.sucursal else 'N/A'}")

print("\n=== TODOS LOS CAFs (Activos e Inactivos) ===")
todos_cafs = ArchivoCAF.objects.filter(empresa=empresa, tipo_documento=33).order_by('id')
for caf in todos_cafs:
    print(f"ID: {caf.id} | Estado: {caf.estado:10} | Tipo: {caf.tipo_documento} | "
          f"Rango: {caf.folio_desde:5}-{caf.folio_hasta:5} | "
          f"Actual: {caf.folio_actual:5} | Usados: {caf.folios_utilizados:3} | "
          f"Sucursal: {caf.sucursal.nombre if caf.sucursal else 'N/A'}")

# Buscar específicamente el DTE folio 18
print("\n=== BUSCANDO DTE FOLIO 18 ===")
dte_18 = DocumentoTributarioElectronico.objects.filter(
    empresa=empresa, 
    tipo_dte=33, 
    folio=18
).first()

if dte_18:
    print(f"ENCONTRADO DTE Folio 18:")
    print(f"  - ID: {dte_18.id}")
    print(f"  - Fecha emisión: {dte_18.fecha_emision}")
    print(f"  - Estado SII: {dte_18.estado_sii}")
    
    # Buscar si hay un CAF que cubra el folio 18
    caf_18 = ArchivoCAF.objects.filter(
        empresa=empresa,
        tipo_documento=33,
        folio_desde__lte=18,
        folio_hasta__gte=18
    ).first()
    
    if caf_18:
        print(f"\n  CAF que cubre folio 18:")
        print(f"    - ID: {caf_18.id}")
        print(f"    - Rango: {caf_18.folio_desde}-{caf_18.folio_hasta}")
        print(f"    - Activo: {caf_18.activo}")
        print(f"    - Sucursal: {caf_18.sucursal.nombre if caf_18.sucursal else 'N/A'}")
    else:
        print(f"\n  PROBLEMA: No hay CAF que cubra el folio 18!")
else:
    print("No se encontró DTE con folio 18")

