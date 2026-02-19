#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Diagnóstico completo de DTEs en el sistema vs DTEBox"""

import os
import django
import sys

sys.path.append(r'c:\PROJECTOS-WEB\GestionCloud')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from empresas.models import Empresa
from datetime import datetime, timedelta
from django.db import models

print("=" * 80)
print("DIAGNÓSTICO COMPLETO DE DTEs")
print("=" * 80)

# Obtener empresa
empresa = Empresa.objects.first()
if not empresa:
    print("❌ No hay empresas en el sistema")
    sys.exit(1)

print(f"\n📋 Empresa: {empresa.nombre}")
print(f"📋 RUT: {empresa.rut}")

# 1. CONTAR TODOS LOS DTEs
print("\n" + "=" * 80)
print("1. DTEs EN LA BASE DE DATOS")
print("=" * 80)

todos_dtes = DocumentoTributarioElectronico.objects.filter(empresa=empresa)
print(f"\nTotal DTEs en BD: {todos_dtes.count()}")

# Por tipo
print("\nPor tipo de documento:")
tipos = todos_dtes.values('tipo_dte').annotate(total=models.Count('id')).order_by('tipo_dte')
for tipo in tipos:
    tipo_nombre = dict(DocumentoTributarioElectronico.TIPO_DTE_CHOICES).get(tipo['tipo_dte'], tipo['tipo_dte'])
    print(f"  • Tipo {tipo['tipo_dte']} ({tipo_nombre}): {tipo['total']}")

# Por estado
print("\nPor estado SII:")
estados = todos_dtes.values('estado_sii').annotate(total=models.Count('id')).order_by('estado_sii')
for estado in estados:
    print(f"  • {estado['estado_sii'] or 'Sin estado'}: {estado['total']}")

# 2. DTEs DEL MES ACTUAL
print("\n" + "=" * 80)
print("2. DTEs DEL MES ACTUAL (Diciembre 2025)")
print("=" * 80)

hoy = datetime.now().date()
primer_dia_mes = hoy.replace(day=1)

dtes_mes = todos_dtes.filter(fecha_emision__gte=primer_dia_mes, fecha_emision__lte=hoy)
print(f"\nDTEs del mes actual: {dtes_mes.count()}")

if dtes_mes.exists():
    print("\nDetalle:")
    for dte in dtes_mes.order_by('-fecha_emision', '-folio'):
        tipo_nombre = dict(DocumentoTributarioElectronico.TIPO_DTE_CHOICES).get(dte.tipo_dte, dte.tipo_dte)
        print(f"  • ID:{dte.id} | Tipo:{dte.tipo_dte} ({tipo_nombre}) | Folio:{dte.folio} | Fecha:{dte.fecha_emision} | Estado:{dte.estado_sii}")

# 3. BUSCAR GUÍA 54 ESPECÍFICAMENTE
print("\n" + "=" * 80)
print("3. BÚSQUEDA DE GUÍA DE DESPACHO #54")
print("=" * 80)

guia_54 = DocumentoTributarioElectronico.objects.filter(
    empresa=empresa,
    tipo_dte='52',
    folio=54
).first()

if guia_54:
    print(f"\n✅ ENCONTRADA - Guía #54:")
    print(f"  • ID: {guia_54.id}")
    print(f"  • Fecha emisión: {guia_54.fecha_emision}")
    print(f"  • Estado SII: {guia_54.estado_sii}")
    print(f"  • RUT Receptor: {guia_54.rut_receptor}")
    print(f"  • Razón Social Receptor: {guia_54.razon_social_receptor}")
    print(f"  • Monto Total: ${guia_54.monto_total}")
else:
    print("\n❌ NO ENCONTRADA - La Guía #54 NO está en la base de datos")

# 4. TODAS LAS GUÍAS DE DESPACHO
print("\n" + "=" * 80)
print("4. TODAS LAS GUÍAS DE DESPACHO (Tipo 52)")
print("=" * 80)

guias = todos_dtes.filter(tipo_dte='52').order_by('-folio')
print(f"\nTotal guías en BD: {guias.count()}")

if guias.exists():
    print("\nListado de guías:")
    for guia in guias:
        print(f"  • Folio:{guia.folio} | Fecha:{guia.fecha_emision} | Estado:{guia.estado_sii} | Cliente:{guia.razon_social_receptor}")

# 5. RECOMENDACIONES
print("\n" + "=" * 80)
print("5. RECOMENDACIONES")
print("=" * 80)

print("\n📌 PROBLEMA IDENTIFICADO:")
print("   Hay una desincronización entre DTEBox y tu base de datos local.")

print("\n💡 SOLUCIONES POSIBLES:")
print("\n   A) Si los documentos están en DTEBox pero NO en tu BD:")
print("      → Necesitas sincronizar/importar desde DTEBox")
print("      → Ejecuta: python manage.py sincronizar_documentos_recibidos")

print("\n   B) Si los documentos están en tu BD pero NO aparecen en la vista:")
print("      → Verifica los filtros de fecha en la vista")
print("      → Verifica que el campo 'empresa' esté correctamente asignado")

print("\n   C) Si la Guía #54 está en DTEBox pero NO en tu BD:")
print("      → Fue emitida desde otro sistema (VB6, GDExpress, etc.)")
print("      → Necesitas importarla manualmente o vía sincronización")

print("\n" + "=" * 80)
