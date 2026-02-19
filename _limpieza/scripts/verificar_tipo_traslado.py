"""
Script URGENTE para verificar el tipo de traslado guardado en los DTEs
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico

def verificar_tipo_traslado():
    print("=" * 80)
    print("VERIFICACIÓN URGENTE: TIPO DE TRASLADO EN DTEs")
    print("=" * 80)
    
    # Verificar DTEs 73, 76, 77
    dtes_ids = [73, 76, 77]
    
    for dte_id in dtes_ids:
        try:
            dte = DocumentoTributarioElectronico.objects.get(id=dte_id)
            
            print(f"\n{'='*80}")
            print(f"DTE ID: {dte_id}")
            print(f"{'='*80}")
            print(f"Folio: {dte.folio}")
            print(f"Tipo DTE: {dte.get_tipo_dte_display()}")
            print(f"Receptor: {dte.razon_social_receptor}")
            print(f"\n📋 TIPO DE TRASLADO:")
            print(f"  dte.tipo_traslado: {dte.tipo_traslado}")
            
            if dte.tipo_traslado:
                tipos = {
                    '1': '❌ VENTA (genera obligación tributaria)',
                    '2': 'Venta por efectuar (anticipada)',
                    '3': 'Consignación',
                    '4': 'Devolución',
                    '5': '✅ TRASLADO INTERNO (sin obligación tributaria)',
                    '6': 'Transformación de productos',
                    '7': 'Entrega gratuita',
                    '8': 'Otros',
                }
                print(f"  Significado: {tipos.get(dte.tipo_traslado, 'Desconocido')}")
            else:
                print(f"  ⚠️  NULL - Se usará valor por defecto '1' (VENTA)")
            
            # Verificar venta asociada
            if dte.venta:
                print(f"\n📦 VENTA ASOCIADA:")
                print(f"  venta.id: {dte.venta.id}")
                print(f"  venta.tipo_despacho: {dte.venta.tipo_despacho if hasattr(dte.venta, 'tipo_despacho') else 'N/A'}")
                
                if hasattr(dte.venta, 'tipo_despacho') and dte.venta.tipo_despacho:
                    tipos = {
                        '1': '❌ VENTA',
                        '2': 'Venta por efectuar',
                        '3': 'Consignación',
                        '4': 'Devolución',
                        '5': '✅ TRASLADO INTERNO',
                        '6': 'Transformación',
                        '7': 'Entrega gratuita',
                        '8': 'Otros',
                    }
                    print(f"  Significado: {tipos.get(dte.venta.tipo_despacho, 'Desconocido')}")
                else:
                    print(f"  ⚠️  NULL - No se guardó el tipo de despacho")
            else:
                print(f"\n📦 VENTA ASOCIADA: Ninguna")
            
            # Verificar XML
            if dte.xml_dte:
                import re
                match = re.search(r'<IndTraslado>(\d+)</IndTraslado>', dte.xml_dte)
                if match:
                    valor_xml = match.group(1)
                    print(f"\n📄 XML GUARDADO:")
                    print(f"  IndTraslado en XML: {valor_xml}")
                    tipos = {
                        '1': '❌ VENTA',
                        '2': 'Venta por efectuar',
                        '3': 'Consignación',
                        '4': 'Devolución',
                        '5': '✅ TRASLADO INTERNO',
                        '6': 'Transformación',
                        '7': 'Entrega gratuita',
                        '8': 'Otros',
                    }
                    print(f"  Significado: {tipos.get(valor_xml, 'Desconocido')}")
                else:
                    print(f"\n📄 XML GUARDADO: No tiene IndTraslado")
            
        except DocumentoTributarioElectronico.DoesNotExist:
            print(f"\n❌ DTE {dte_id} no encontrado")
    
    print("\n" + "=" * 80)
    print("RESUMEN:")
    print("=" * 80)
    print("Si los DTEs muestran 'VENTA' pero deberían ser 'TRASLADO INTERNO',")
    print("significa que el tipo de guía NO se está guardando correctamente.")
    print("\nEsto es CRÍTICO porque:")
    print("  - Guías de VENTA (1) generan obligación tributaria")
    print("  - Guías de TRASLADO INTERNO (5) NO generan obligación tributaria")

if __name__ == '__main__':
    verificar_tipo_traslado()
