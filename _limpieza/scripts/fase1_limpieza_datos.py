#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico, ArchivoCAF
from empresas.models import Empresa

print("="*80)
print("LIMPIEZA DE DATOS CORRUPTOS - FASE 1")
print("="*80)

# Buscar la empresa Kreasoft
empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()

if not empresa:
    print("ERROR: No se encontro la empresa Kreasoft")
    exit(1)

print(f"\nEmpresa: {empresa.nombre} (ID: {empresa.id})")

# 1. Buscar el DTE folio 18 invalido
print("\n" + "="*80)
print("1. BUSCANDO DTE FOLIO 18 (INVALIDO)")
print("="*80)

dte_18 = DocumentoTributarioElectronico.objects.filter(
    empresa=empresa,
    tipo_dte=33,
    folio=18
).first()

if dte_18:
    print(f"\nDTE Folio 18 encontrado:")
    print(f"  - ID: {dte_18.id}")
    print(f"  - Fecha emision: {dte_18.fecha_emision}")
    print(f"  - Estado SII: {dte_18.estado_sii}")
    print(f"  - CAF utilizado: {dte_18.caf_utilizado.id if dte_18.caf_utilizado else 'N/A'}")
    
    if dte_18.caf_utilizado:
        print(f"  - Rango CAF: {dte_18.caf_utilizado.folio_desde}-{dte_18.caf_utilizado.folio_hasta}")
        print(f"\n  PROBLEMA: Folio 18 NO esta en el rango del CAF!")
    
    print(f"\nELIMINANDO DTE folio 18...")
    dte_18.delete()
    print("  [OK] DTE folio 18 eliminado")
else:
    print("\n  [INFO] No se encontro DTE con folio 18")

# 2. Buscar TODOS los DTEs con folios fuera de rango de sus CAFs
print("\n" + "="*80)
print("2. BUSCANDO OTROS DTEs INVALIDOS (FOLIOS FUERA DE RANGO CAF)")
print("="*80)

dtes_invalidos = []
todos_dtes = DocumentoTributarioElectronico.objects.filter(empresa=empresa, tipo_dte=33)

for dte in todos_dtes:
    if dte.caf_utilizado:
        if not (dte.caf_utilizado.folio_desde <= dte.folio <= dte.caf_utilizado.folio_hasta):
            dtes_invalidos.append(dte)
            print(f"\n  [INVALIDO] DTE ID {dte.id}, Folio {dte.folio}")
            print(f"    - CAF rango: {dte.caf_utilizado.folio_desde}-{dte.caf_utilizado.folio_hasta}")
            print(f"    - Estado: {dte.estado_sii}")
            print(f"    - Fecha: {dte.fecha_emision}")

if dtes_invalidos:
    print(f"\n  TOTAL DTEs INVALIDOS: {len(dtes_invalidos)}")
    print("\n  ELIMINANDO DTEs invalidos...")
    for dte in dtes_invalidos:
        print(f"    - Eliminando DTE ID {dte.id}, Folio {dte.folio}")
        dte.delete()
    print("  [OK] DTEs invalidos eliminados")
else:
    print("\n  [OK] No se encontraron otros DTEs invalidos")

# 3. Verificar estado del CAF activo
print("\n" + "="*80)
print("3. VERIFICANDO ESTADO DEL CAF ACTIVO")
print("="*80)

caf_activo = ArchivoCAF.objects.filter(
    empresa=empresa,
    tipo_documento=33,
    estado='activo'
).first()

if caf_activo:
    print(f"\nCAF Activo:")
    print(f"  - ID: {caf_activo.id}")
    print(f"  - Rango: {caf_activo.folio_desde}-{caf_activo.folio_hasta}")
    print(f"  - Folio actual: {caf_activo.folio_actual}")
    print(f"  - Folios utilizados: {caf_activo.folios_utilizados}")
    
    # Verificar DTEs reales asociados a este CAF
    dtes_reales = DocumentoTributarioElectronico.objects.filter(
        empresa=empresa,
        caf_utilizado=caf_activo,
        tipo_dte=33
    ).order_by('folio')
    
    print(f"\n  DTEs reales asociados a este CAF: {dtes_reales.count()}")
    for dte in dtes_reales:
        print(f"    - Folio {dte.folio}, Estado: {dte.estado_sii}, Fecha: {dte.fecha_emision}")
    
    # Calcular proximo folio correcto
    if dtes_reales.exists():
        ultimo_folio = dtes_reales.last().folio
        proximo_folio = ultimo_folio + 1
    else:
        proximo_folio = caf_activo.folio_desde
    
    print(f"\n  Proximo folio que deberia asignarse: {proximo_folio}")
    
    # Corregir folio_actual si es necesario
    if caf_activo.folio_actual != proximo_folio - 1:
        print(f"\n  [CORRIGIENDO] folio_actual de {caf_activo.folio_actual} a {proximo_folio - 1}")
        caf_activo.folio_actual = proximo_folio - 1
    
    # Corregir folios_utilizados
    folios_utilizados_real = dtes_reales.count()
    if caf_activo.folios_utilizados != folios_utilizados_real:
        print(f"  [CORRIGIENDO] folios_utilizados de {caf_activo.folios_utilizados} a {folios_utilizados_real}")
        caf_activo.folios_utilizados = folios_utilizados_real
    
    caf_activo.save()
    print("  [OK] CAF actualizado")
else:
    print("\n  [ERROR] No se encontro CAF activo para facturas (tipo 33)")

# 4. Resumen final
print("\n" + "="*80)
print("4. RESUMEN DE LIMPIEZA")
print("="*80)

print(f"\nDTEs eliminados: {1 if dte_18 else 0 + len(dtes_invalidos)}")
print(f"CAF activo verificado: {'SI' if caf_activo else 'NO'}")

if caf_activo:
    print(f"\nEstado final del CAF:")
    print(f"  - Rango autorizado: {caf_activo.folio_desde}-{caf_activo.folio_hasta}")
    print(f"  - Folios usados: {caf_activo.folios_utilizados}")
    print(f"  - Folios disponibles: {caf_activo.folio_hasta - caf_activo.folio_actual}")
    print(f"  - Proximo folio: {caf_activo.folio_actual + 1}")

print("\n" + "="*80)
print("[OK] LIMPIEZA COMPLETADA")
print("="*80)

