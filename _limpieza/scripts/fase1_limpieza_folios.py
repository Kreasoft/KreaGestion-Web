#!/usr/bin/env python
"""
FASE 1: LIMPIEZA Y CORRECCIÓN DE DATOS CORRUPTOS
Elimina DTEs inválidos y corrige el estado de los CAFs
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.db import transaction
from facturacion_electronica.models import DocumentoTributarioElectronico, ArchivoCAF
from empresas.models import Empresa

print("=" * 80)
print("FASE 1: LIMPIEZA Y CORRECCIÓN DE DATOS CORRUPTOS")
print("=" * 80)

# Buscar empresa
empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
if not empresa:
    print("ERROR: No se encontró la empresa")
    exit(1)

print(f"\nEmpresa: {empresa.nombre} (ID: {empresa.id})")

# ============================================================================
# PASO 1: IDENTIFICAR Y ELIMINAR DTEs CON FOLIOS FUERA DE RANGO
# ============================================================================
print("\n" + "=" * 80)
print("PASO 1: IDENTIFICAR DTEs CON FOLIOS FUERA DE RANGO")
print("=" * 80)

dtes_problematicos = []

# Obtener todos los DTEs
dtes = DocumentoTributarioElectronico.objects.filter(empresa=empresa).order_by('tipo_dte', 'folio')

for dte in dtes:
    # Buscar si existe un CAF que cubra este folio
    caf_valido = ArchivoCAF.objects.filter(
        empresa=empresa,
        tipo_documento=dte.tipo_dte,
        folio_desde__lte=dte.folio,
        folio_hasta__gte=dte.folio
    ).first()
    
    if not caf_valido:
        dtes_problematicos.append(dte)
        print(f"\n[X] DTE PROBLEMATICO ENCONTRADO:")
        print(f"   ID: {dte.id}")
        print(f"   Tipo: {dte.tipo_dte} ({dte.get_tipo_dte_display()})")
        print(f"   Folio: {dte.folio}")
        print(f"   Fecha: {dte.fecha_emision}")
        print(f"   Estado: {dte.estado_sii}")
        print(f"   CAF usado: {dte.caf_utilizado_id if hasattr(dte, 'caf_utilizado_id') else 'N/A'}")
        print(f"   PROBLEMA: No existe CAF que cubra el folio {dte.folio}")

if not dtes_problematicos:
    print("\n[OK] No se encontraron DTEs con folios fuera de rango")
else:
    print(f"\n[!] TOTAL DTEs PROBLEMATICOS: {len(dtes_problematicos)}")
    
    # Respuesta automática: SI (para automatizar)
    respuesta = 'si'
    print(f"\n¿Desea ELIMINAR estos DTEs? (si/no): {respuesta}")
    
    if respuesta in ['si', 's', 'yes', 'y']:
        with transaction.atomic():
            for dte in dtes_problematicos:
                print(f"   Eliminando DTE ID {dte.id} (Folio {dte.folio})...")
                dte.delete()
            print(f"\n[OK] {len(dtes_problematicos)} DTEs eliminados exitosamente")
    else:
        print("\n[!] Operacion cancelada por el usuario")
        exit(0)

# ============================================================================
# PASO 2: VERIFICAR Y CORREGIR ESTADO DE CAFs
# ============================================================================
print("\n" + "=" * 80)
print("PASO 2: VERIFICAR Y CORREGIR ESTADO DE CAFs")
print("=" * 80)

cafs = ArchivoCAF.objects.filter(empresa=empresa).order_by('tipo_documento', 'id')

cafs_corregidos = []

for caf in cafs:
    print(f"\n--- CAF ID: {caf.id} ---")
    print(f"Tipo: {caf.tipo_documento}")
    print(f"Rango autorizado: {caf.folio_desde} - {caf.folio_hasta}")
    print(f"Folio actual (BD): {caf.folio_actual}")
    print(f"Folios utilizados (BD): {caf.folios_utilizados}")
    print(f"Estado: {caf.estado}")
    
    # Verificar si folio_actual está dentro del rango
    problema_folio_actual = False
    if caf.folio_actual < (caf.folio_desde - 1):
        print(f"[!] PROBLEMA: folio_actual ({caf.folio_actual}) es menor que folio_desde-1 ({caf.folio_desde - 1})")
        problema_folio_actual = True
    elif caf.folio_actual > caf.folio_hasta:
        print(f"[!] PROBLEMA: folio_actual ({caf.folio_actual}) es mayor que folio_hasta ({caf.folio_hasta})")
        problema_folio_actual = True
    
    # Contar DTEs reales que usan este CAF
    dtes_reales = DocumentoTributarioElectronico.objects.filter(
        empresa=empresa,
        caf_utilizado=caf
    ).count()
    
    print(f"DTEs reales asociados: {dtes_reales}")
    
    # Verificar discrepancia
    discrepancia_folios = False
    if dtes_reales != caf.folios_utilizados:
        print(f"[!] DISCREPANCIA: folios_utilizados en BD ({caf.folios_utilizados}) != DTEs reales ({dtes_reales})")
        discrepancia_folios = True
    
    # Determinar el folio_actual correcto basándose en DTEs reales
    if dtes_reales > 0:
        ultimo_dte = DocumentoTributarioElectronico.objects.filter(
            empresa=empresa,
            caf_utilizado=caf
        ).order_by('-folio').first()
        
        folio_actual_correcto = ultimo_dte.folio
        print(f"Ultimo DTE real: Folio {folio_actual_correcto}")
        
        if caf.folio_actual != folio_actual_correcto:
            print(f"[!] PROBLEMA: folio_actual deberia ser {folio_actual_correcto}")
            problema_folio_actual = True
    else:
        folio_actual_correcto = caf.folio_desde - 1
        if caf.folio_actual != folio_actual_correcto:
            print(f"[!] PROBLEMA: No hay DTEs, folio_actual deberia ser {folio_actual_correcto}")
            problema_folio_actual = True
    
    # Si hay problemas, preparar corrección
    if problema_folio_actual or discrepancia_folios:
        cafs_corregidos.append({
            'caf': caf,
            'folio_actual_nuevo': folio_actual_correcto,
            'folios_utilizados_nuevo': dtes_reales
        })
        print(f"\n[FIX] CORRECCION PROPUESTA:")
        print(f"   folio_actual: {caf.folio_actual} -> {folio_actual_correcto}")
        print(f"   folios_utilizados: {caf.folios_utilizados} -> {dtes_reales}")
    else:
        print("[OK] CAF esta correcto")

# Aplicar correcciones
if cafs_corregidos:
    print(f"\n[!] TOTAL CAFs A CORREGIR: {len(cafs_corregidos)}")
    
    # Respuesta automática: SI (para automatizar)
    respuesta = 'si'
    print(f"\n¿Desea APLICAR estas correcciones? (si/no): {respuesta}")
    
    if respuesta in ['si', 's', 'yes', 'y']:
        with transaction.atomic():
            for correccion in cafs_corregidos:
                caf = correccion['caf']
                caf.folio_actual = correccion['folio_actual_nuevo']
                caf.folios_utilizados = correccion['folios_utilizados_nuevo']
                
                # Actualizar estado si está agotado
                if caf.folios_utilizados >= caf.cantidad_folios:
                    caf.estado = 'agotado'
                elif caf.estado == 'agotado' and caf.folios_utilizados < caf.cantidad_folios:
                    caf.estado = 'activo'
                
                caf.save()
                print(f"   [OK] CAF ID {caf.id} corregido")
            
            print(f"\n[OK] {len(cafs_corregidos)} CAFs corregidos exitosamente")
    else:
        print("\n[!] Correcciones canceladas por el usuario")
else:
    print("\n[OK] Todos los CAFs estan correctos")

# ============================================================================
# PASO 3: RESUMEN FINAL
# ============================================================================
print("\n" + "=" * 80)
print("RESUMEN FINAL")
print("=" * 80)

print("\nCAFs ACTIVOS DESPUÉS DE LA LIMPIEZA:")
cafs_activos = ArchivoCAF.objects.filter(empresa=empresa, estado='activo').order_by('tipo_documento', 'id')
for caf in cafs_activos:
    print(f"\nID: {caf.id} | Tipo: {caf.tipo_documento} | Sucursal: {caf.sucursal.nombre if caf.sucursal else 'N/A'}")
    print(f"  Rango: {caf.folio_desde}-{caf.folio_hasta}")
    print(f"  Folio actual: {caf.folio_actual}")
    print(f"  Folios utilizados: {caf.folios_utilizados}/{caf.cantidad_folios}")
    print(f"  Próximo folio a asignar: {caf.folio_actual + 1}")

print("\nÚLTIMOS 10 DTEs:")
ultimos_dtes = DocumentoTributarioElectronico.objects.filter(
    empresa=empresa
).order_by('-id')[:10]

for dte in ultimos_dtes:
    caf = ArchivoCAF.objects.filter(
        empresa=empresa,
        tipo_documento=dte.tipo_dte,
        folio_desde__lte=dte.folio,
        folio_hasta__gte=dte.folio
    ).first()
    
    estado_caf = "[OK]" if caf else "[X] SIN CAF"
    print(f"ID: {dte.id:3} | Folio: {dte.folio:5} | Tipo: {dte.tipo_dte} | "
          f"Estado: {dte.estado_sii:10} | CAF: {estado_caf}")

print("\n" + "=" * 80)
print("FASE 1 COMPLETADA")
print("=" * 80)

