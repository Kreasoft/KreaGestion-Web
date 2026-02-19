"""
Script para regenerar el XML de un DTE existente con las correcciones aplicadas
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dte_generator import DTEXMLGenerator

def regenerar_xml_dte(dte_id):
    """Regenera el XML de un DTE existente"""
    
    print("=" * 80)
    print(f"REGENERANDO XML PARA DTE ID: {dte_id}")
    print("=" * 80)
    
    try:
        # Obtener el DTE
        dte = DocumentoTributarioElectronico.objects.get(id=dte_id)
        
        print(f"\n✓ DTE encontrado:")
        print(f"  Tipo: {dte.get_tipo_dte_display()}")
        print(f"  Folio: {dte.folio}")
        print(f"  Receptor: {dte.razon_social_receptor}")
        print(f"  Total: ${dte.monto_total}")
        print(f"  Estado: {dte.estado_sii}")
        
        # Verificar si tiene venta asociada
        if not dte.venta:
            print("\n✗ Este DTE no tiene venta asociada")
            print("  No se puede regenerar automáticamente")
            return False
        
        print(f"\n✓ Venta asociada: ID {dte.venta.id}")
        print(f"  tipo_despacho: {dte.venta.tipo_despacho if hasattr(dte.venta, 'tipo_despacho') else 'N/A'}")
        
        # Generar nuevo XML usando DTEXMLGenerator
        print("\n" + "=" * 80)
        print("GENERANDO NUEVO XML CON CORRECCIONES...")
        print("=" * 80)
        
        generator = DTEXMLGenerator(
            empresa=dte.empresa,
            documento=dte,  # Pasamos el DTE directamente
            tipo_dte=dte.tipo_dte,
            folio=dte.folio,
            caf=dte.caf_utilizado
        )
        
        xml_nuevo = generator.generar_xml()
        
        print(f"\n✓ XML regenerado exitosamente!")
        print(f"  Tamaño anterior: {len(dte.xml_dte)} caracteres")
        print(f"  Tamaño nuevo: {len(xml_nuevo)} caracteres")
        
        # Mostrar primeras líneas del XML nuevo
        print("\n" + "=" * 80)
        print("PRIMERAS 50 LÍNEAS DEL XML NUEVO:")
        print("=" * 80)
        lines = xml_nuevo.split('\n')
        for i, line in enumerate(lines[:50], 1):
            print(f"{i:3}: {line}")
        
        # Verificar elementos críticos
        print("\n" + "=" * 80)
        print("VERIFICACIÓN:")
        print("=" * 80)
        
        checks = {
            '<IndTraslado>': 'IndTraslado presente',
            '<RznSoc>': 'RznSoc (correcto)',
            '<GiroEmis>': 'GiroEmis (correcto)',
            '<Transporte>': 'Transporte (NO debería estar)',
        }
        
        for elemento, descripcion in checks.items():
            if elemento in xml_nuevo:
                if elemento == '<Transporte>':
                    print(f"  ✗ {descripcion}: ENCONTRADO")
                else:
                    print(f"  ✓ {descripcion}: OK")
            else:
                if elemento == '<Transporte>':
                    print(f"  ✓ {descripcion}: AUSENTE (correcto)")
                else:
                    print(f"  ✗ {descripcion}: NO ENCONTRADO")
        
        # Preguntar si actualizar
        print("\n" + "=" * 80)
        print("¿ACTUALIZAR EL DTE EN LA BASE DE DATOS?")
        print("=" * 80)
        print("\nEsto actualizará el campo xml_dte del DTE.")
        print("El xml_firmado y timbre_electronico NO se actualizarán automáticamente.")
        print("\nOpciones:")
        print("  1. Actualizar solo xml_dte (sin firmar)")
        print("  2. NO actualizar (solo mostrar el XML)")
        
        opcion = input("\nIngresa tu opción (1 o 2): ").strip()
        
        if opcion == '1':
            dte.xml_dte = xml_nuevo
            dte.save(update_fields=['xml_dte'])
            print("\n✓ DTE actualizado en la base de datos")
            print("  IMPORTANTE: Debes regenerar la firma y el TED para este DTE")
            print("  Usa la opción 'Regenerar DTE' en la interfaz web")
        else:
            print("\n✓ DTE NO actualizado")
            print("  El XML generado se guardó en: logs/dtebox_debug/dte_{dte_id}_regenerado.xml")
            
            # Guardar XML en archivo
            output_file = f'logs/dtebox_debug/dte_{dte_id}_regenerado.xml'
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', encoding='ISO-8859-1') as f:
                f.write(xml_nuevo)
            print(f"  Archivo guardado: {output_file}")
        
        return True
        
    except DocumentoTributarioElectronico.DoesNotExist:
        print(f"\n✗ No se encontró el DTE con ID {dte_id}")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        dte_id = int(sys.argv[1])
    else:
        dte_id = 76  # DTE por defecto
    
    regenerar_xml_dte(dte_id)
