"""
Script para probar el envío del DTE 74 a DTEBox
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dtebox_service import DTEBoxService

def probar_envio_dtebox(dte_id):
    """Prueba el envío de un DTE a DTEBox"""
    
    print("=" * 80)
    print(f"PRUEBA DE ENVÍO A DTEBOX - DTE ID: {dte_id}")
    print("=" * 80)
    
    try:
        # 1. Obtener el DTE
        dte = DocumentoTributarioElectronico.objects.get(id=dte_id)
        
        print(f"\n✓ DTE encontrado:")
        print(f"  Tipo: {dte.get_tipo_dte_display()}")
        print(f"  Folio: {dte.folio}")
        print(f"  Receptor: {dte.razon_social_receptor}")
        print(f"  Total: ${dte.monto_total}")
        print(f"  Estado actual: {dte.estado_sii}")
        
        # 2. Verificar que tiene XML firmado
        if not dte.xml_firmado:
            print("\n✗ El DTE no tiene XML firmado")
            return False
        
        print(f"\n✓ XML firmado disponible: {len(dte.xml_firmado)} caracteres")
        
        # 3. Mostrar primeras líneas del XML que se enviará
        print("\n" + "=" * 80)
        print("XML QUE SE ENVIARÁ (primeras 50 líneas):")
        print("=" * 80)
        lines = dte.xml_firmado.split('\n')
        for i, line in enumerate(lines[:50], 1):
            print(f"{i:3}: {line}")
        
        # 4. Verificar elementos críticos en el XML
        print("\n" + "=" * 80)
        print("VERIFICACIÓN FINAL DEL XML:")
        print("=" * 80)
        
        import re
        
        checks = [
            (r'<Documento ID="F\d+T52"', 'ID del documento correcto'),
            (r'<IndTraslado>\d+</IndTraslado>', 'IndTraslado presente'),
            (r'<RznSoc>', 'RznSoc (correcto)'),
            (r'<GiroEmis>', 'GiroEmis (correcto)'),
            (r'<CiudadRecep>[^<]+</CiudadRecep>', 'CiudadRecep presente'),
        ]
        
        all_ok = True
        for pattern, descripcion in checks:
            if re.search(pattern, dte.xml_firmado):
                print(f"  ✓ {descripcion}")
            else:
                print(f"  ✗ {descripcion} - NO ENCONTRADO")
                all_ok = False
        
        # Verificar que NO tenga Transporte
        if '<Transporte>' in dte.xml_firmado:
            print(f"  ✗ Transporte presente (NO debería estar)")
            all_ok = False
        else:
            print(f"  ✓ Transporte ausente (correcto)")
        
        if not all_ok:
            print("\n⚠️  ADVERTENCIA: El XML tiene problemas estructurales")
            print("¿Deseas continuar con el envío de todos modos? (s/n): ", end='')
            respuesta = input().strip().lower()
            if respuesta != 's':
                print("\nEnvío cancelado")
                return False
        
        # 5. Inicializar servicio DTEBox
        print("\n" + "=" * 80)
        print("ENVIANDO A DTEBOX...")
        print("=" * 80)
        
        dtebox = DTEBoxService(dte.empresa)
        
        print(f"\n✓ Servicio DTEBox inicializado")
        print(f"  Ambiente: {dtebox.ambiente}")

        
        # 6. Enviar a DTEBox
        print(f"\nEnviando DTE {dte.folio} a DTEBox...")
        print("(Esto puede tomar unos segundos...)\n")
        
        resultado = dtebox.timbrar_dte(dte.xml_firmado)
        
        # 7. Mostrar resultado
        print("\n" + "=" * 80)
        print("RESULTADO DEL ENVÍO:")
        print("=" * 80)
        
        if resultado['success']:
            print("\n✅ ¡ÉXITO! El DTE fue aceptado por DTEBox")
            print(f"\n  TED recibido: {len(resultado.get('ted', ''))} caracteres")
            print(f"  XML respuesta: {len(resultado.get('xml_respuesta', ''))} caracteres")
            
            # Mostrar respuesta XML si está disponible
            if resultado.get('xml_respuesta'):
                print("\n" + "-" * 80)
                print("RESPUESTA DE DTEBOX (primeras 30 líneas):")
                print("-" * 80)
                resp_lines = resultado['xml_respuesta'].split('\n')
                for i, line in enumerate(resp_lines[:30], 1):
                    print(f"{i:3}: {line}")
            
            print("\n" + "=" * 80)
            print("✅ EL PROBLEMA ESTÁ RESUELTO")
            print("=" * 80)
            print("\nEl DTE se envió correctamente a DTEBox.")
            print("Ahora puedes crear nuevas Guías de Despacho sin problemas.")
            
        else:
            print("\n❌ ERROR: DTEBox rechazó el DTE")
            print(f"\n  Error: {resultado.get('error', 'Error desconocido')}")
            
            # Mostrar detalles del error
            if resultado.get('xml_respuesta'):
                print("\n" + "-" * 80)
                print("RESPUESTA DE ERROR DE DTEBOX:")
                print("-" * 80)
                print(resultado['xml_respuesta'])
            
            print("\n" + "=" * 80)
            print("ANÁLISIS DEL ERROR:")
            print("=" * 80)
            
            error_msg = resultado.get('error', '').lower()
            
            if '500' in error_msg or 'internal' in error_msg:
                print("\n⚠️  Error HTTP 500 - Error interno del servidor")
                print("\nPosibles causas:")
                print("  1. Campo faltante u obligatorio en el XML")
                print("  2. Formato incorrecto de algún dato")
                print("  3. Problema temporal del servidor DTEBox")
                print("\nRecomendación:")
                print("  - Revisa el XML completo guardado en logs/dtebox_debug/")
                print("  - Compara con el XML de ejemplo que funciona")
                print("  - Contacta a soporte de DTEBox si persiste")
            
        return resultado['success']
        
    except DocumentoTributarioElectronico.DoesNotExist:
        print(f"\n✗ No se encontró el DTE con ID {dte_id}")
        return False
    except Exception as e:
        print(f"\n✗ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        dte_id = int(sys.argv[1])
    else:
        dte_id = 74  # DTE por defecto
    
    exito = probar_envio_dtebox(dte_id)
    
    if exito:
        print("\n✅ Prueba exitosa")
        sys.exit(0)
    else:
        print("\n❌ Prueba fallida")
        sys.exit(1)
