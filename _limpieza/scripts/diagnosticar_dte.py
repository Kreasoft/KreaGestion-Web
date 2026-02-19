"""
Script de diagnóstico completo para DTEs
Verifica el estado real en BD, GDExpress y SII
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from empresas.models import Empresa
from django.db.models import Q

def diagnosticar_dtes():
    """Diagnóstico completo de DTEs"""
    
    # Obtener la empresa
    empresa = Empresa.objects.get(id=6)  # Kreasoft spa
    
    print("\n" + "="*80)
    print("🔍 DIAGNÓSTICO DE DOCUMENTOS TRIBUTARIOS ELECTRÓNICOS")
    print("="*80)
    print(f"\n📌 Empresa: {empresa.nombre}")
    print(f"📌 RUT: {empresa.rut}")
    print(f"📌 Ambiente SII: {empresa.ambiente_sii}")
    print(f"📌 DTEBox habilitado: {empresa.dtebox_habilitado}")
    
    # Buscar DTEs recientes (últimos 50)
    dtes = DocumentoTributarioElectronico.objects.filter(
        empresa=empresa
    ).order_by('-fecha_emision')[:50]
    
    print(f"\n📊 Total de DTEs encontrados: {dtes.count()}")
    print("\n" + "-"*80)
    
    # Estadísticas por estado
    estados = {}
    for dte in dtes:
        estado = dte.estado_sii or 'sin_estado'
        estados[estado] = estados.get(estado, 0) + 1
    
    print("\n📈 ESTADÍSTICAS POR ESTADO:")
    print("-"*80)
    for estado, cantidad in sorted(estados.items()):
        print(f"  {estado:20s} : {cantidad:3d} documentos")
    
    # Buscar guías específicas mencionadas en el error
    print("\n" + "="*80)
    print("🔎 DETALLE DE GUÍAS PROBLEMÁTICAS (folios 67, 93, 94)")
    print("="*80)
    
    folios_problematicos = [67, 93, 94]
    for folio in folios_problematicos:
        guias = DocumentoTributarioElectronico.objects.filter(
            empresa=empresa,
            tipo_dte='52',
            folio=folio
        )
        
        if guias.exists():
            for guia in guias:
                print(f"\n📄 GUÍA FOLIO {guia.folio}")
                print(f"   ID: {guia.id}")
                print(f"   Fecha Emisión: {guia.fecha_emision}")
                print(f"   Estado SII: {guia.estado_sii}")
                print(f"   Track ID: {guia.track_id or 'NO TIENE'}")
                print(f"   Fecha Envío SII: {guia.fecha_envio_sii or 'NO ENVIADO'}")
                print(f"   Fecha Respuesta SII: {guia.fecha_respuesta_sii or 'SIN RESPUESTA'}")
                print(f"   Tiene XML firmado: {'✅ SÍ' if guia.xml_firmado else '❌ NO'}")
                print(f"   Tiene TED: {'✅ SÍ' if guia.timbre_electronico else '❌ NO'}")
                print(f"   Glosa SII: {guia.glosa_sii or 'N/A'}")
                print(f"   Error Envío: {guia.error_envio or 'N/A'}")
                
                # Diagnóstico
                print(f"\n   🔍 DIAGNÓSTICO:")
                if not guia.xml_firmado:
                    print(f"      ❌ PROBLEMA: No tiene XML firmado - NO se puede enviar")
                elif not guia.timbre_electronico:
                    print(f"      ⚠️  ADVERTENCIA: No tiene TED (timbre) - Puede causar problemas")
                elif not guia.track_id:
                    print(f"      ❌ PROBLEMA: No tiene Track ID - NO fue enviado al SII")
                    print(f"         → ACCIÓN: Debe enviar al SII primero")
                elif guia.estado_sii in ['generado', 'firmado', 'pendiente']:
                    print(f"      ⚠️  ADVERTENCIA: Estado '{guia.estado_sii}' - Debe enviar al SII")
                    print(f"         → ACCIÓN: Usar botón 'Enviar al SII'")
                elif guia.estado_sii == 'enviado':
                    print(f"      ⏳ PENDIENTE: Enviado pero no confirmado por SII")
                    print(f"         → ACCIÓN: Consultar estado en SII")
                elif guia.estado_sii == 'aceptado':
                    print(f"      ✅ OK: Documento aceptado por SII")
                    print(f"         → PDF debería estar disponible en GDExpress")
                elif guia.estado_sii == 'rechazado':
                    print(f"      ❌ RECHAZADO: El SII rechazó este documento")
                    print(f"         → Motivo: {guia.glosa_sii}")
        else:
            print(f"\n📄 GUÍA FOLIO {folio}: ❌ NO ENCONTRADA EN BASE DE DATOS")
    
    # Mostrar DTEs con estado enviado o aceptado (candidatos para PDF)
    print("\n" + "="*80)
    print("📋 DOCUMENTOS CANDIDATOS PARA PDF (Enviados o Aceptados)")
    print("="*80)
    
    candidatos = DocumentoTributarioElectronico.objects.filter(
        empresa=empresa,
        estado_sii__in=['enviado', 'aceptado']
    ).order_by('-fecha_emision')[:10]
    
    if candidatos.exists():
        for dte in candidatos:
            tipo_nombre = dte.get_tipo_dte_display()
            print(f"\n  {tipo_nombre} Folio {dte.folio}")
            print(f"     Estado: {dte.estado_sii}")
            print(f"     Track ID: {dte.track_id}")
            print(f"     Fecha Envío: {dte.fecha_envio_sii}")
            print(f"     ¿PDF disponible?: {'✅ Probablemente SÍ' if dte.estado_sii == 'aceptado' else '⚠️ Puede que NO (solo enviado)'}")
    else:
        print("\n  ❌ No hay documentos enviados o aceptados")
    
    # Recomendaciones finales
    print("\n" + "="*80)
    print("💡 RECOMENDACIONES")
    print("="*80)
    
    sin_track = DocumentoTributarioElectronico.objects.filter(
        empresa=empresa,
        track_id='',
        estado_sii__in=['generado', 'firmado', 'pendiente']
    ).count()
    
    enviados_sin_confirmar = DocumentoTributarioElectronico.objects.filter(
        empresa=empresa,
        estado_sii='enviado'
    ).count()
    
    if sin_track > 0:
        print(f"\n  ⚠️  Tienes {sin_track} documentos que NO han sido enviados al SII")
        print(f"     → ACCIÓN: Usa el botón 'Enviar al SII' en el listado de DTEs")
    
    if enviados_sin_confirmar > 0:
        print(f"\n  ⏳ Tienes {enviados_sin_confirmar} documentos enviados pero sin confirmación")
        print(f"     → ACCIÓN: Consulta su estado en el SII para actualizarlo")
    
    aceptados = DocumentoTributarioElectronico.objects.filter(
        empresa=empresa,
        estado_sii='aceptado'
    ).count()
    
    if aceptados > 0:
        print(f"\n  ✅ Tienes {aceptados} documentos ACEPTADOS por el SII")
        print(f"     → Estos SÍ deberían tener PDF disponible en GDExpress")
    
    print("\n" + "="*80)
    print("✅ DIAGNÓSTICO COMPLETO")
    print("="*80 + "\n")


if __name__ == '__main__':
    diagnosticar_dtes()
