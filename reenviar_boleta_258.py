#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para regenerar y enviar boleta folio 258
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.dirname(BASE_DIR))
django.setup()

from facturacion_electronica.dtebox_service import DTEBoxService
from facturacion_electronica.dte_generator import DTEXMLGenerator
from facturacion_electronica.models import DocumentoTributarioElectronico
from core.models import Empresa

print("=" * 80)
print("REENVÍO DE BOLETA FOLIO 258")
print("=" * 80)

# Buscar la boleta folio 258
dte = DocumentoTributarioElectronico.objects.filter(tipo_dte='39', folio=258).first()

if not dte:
    print("ERROR: No se encontró la boleta folio 258")
    # Listar boletas disponibles
    boletas = DocumentoTributarioElectronico.objects.filter(tipo_dte='39').order_by('-folio')[:5]
    print("\nBoletas disponibles:")
    for b in boletas:
        print(f"  - Folio {b.folio}, Estado: {b.estado_sii}")
    sys.exit(1)

print(f"\nBoleta encontrada:")
print(f"  Folio: {dte.folio}")
print(f"  Estado SII: {dte.estado_sii}")
print(f"  Empresa: {dte.empresa.nombre}")

# Obtener empresa
empresa = dte.empresa

# Verificar DTEBox configurado
if not empresa.dtebox_habilitado:
    print(f"\nERROR: DTEBox no está habilitado para {empresa.nombre}")
    sys.exit(1)

print(f"\nDTEBox configurado:")
print(f"  URL: {empresa.dtebox_url}")
print(f"  Ambiente: {empresa.dtebox_ambiente}")

# Regenerar XML con el generador corregido
print(f"\n{'='*80}")
print("REGENERANDO XML CON FORMATO CORRECTO...")
print(f"{'='*80}")

try:
    # Crear generador y regenerar XML
    generator = DTEXMLGenerator(dte, empresa)
    xml_nuevo = generator.generar_xml_desde_dte()
    
    print(f"XML regenerado exitosamente")
    print(f"Longitud: {len(xml_nuevo)} caracteres")
    print(f"\nPrimeros 1000 caracteres:")
    print("-" * 80)
    print(xml_nuevo[:1000])
    print("-" * 80)
    
    # Guardar el nuevo XML
    dte.xml_firmado = xml_nuevo
    dte.save()
    print(f"\n✅ XML guardado en el DTE")
    
except Exception as e:
    print(f"\n❌ Error regenerando XML: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Intentar envío a DTEBox
print(f"\n{'='*80}")
print("ENVIANDO A DTEBOX...")
print(f"{'='*80}")

try:
    service = DTEBoxService(empresa)
    resultado = service.timbrar_dte(dte.xml_firmado, '39')
    
    print(f"\nResultado del envío:")
    print(f"  Success: {resultado.get('success')}")
    print(f"  Estado: {resultado.get('estado')}")
    print(f"  Error: {resultado.get('error')}")
    print(f"  Track ID: {resultado.get('track_id')}")
    
    if resultado.get('success'):
        print(f"\n✅ BOLETA FOLIO 258 ENVIADA EXITOSAMENTE!")
        
        # Actualizar DTE
        dte.estado_sii = 'enviado'
        dte.track_id = resultado.get('track_id')
        if resultado.get('ted'):
            dte.timbre_electronico = resultado.get('ted')
        dte.save()
        print(f"✅ DTE actualizado en la base de datos")
    else:
        print(f"\n❌ ERROR EN ENVÍO: {resultado.get('error')}")
        
except Exception as e:
    print(f"\n❌ EXCEPCIÓN: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
