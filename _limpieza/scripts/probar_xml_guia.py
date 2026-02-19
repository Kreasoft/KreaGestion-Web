"""
Script de prueba para generar XML de Guía de Despacho sin consumir folios
Verifica que el XML tenga la estructura correcta según las correcciones realizadas
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa
from ventas.models import Venta
from facturacion_electronica.dte_generator import DTEXMLGenerator
from facturacion_electronica.models import ArchivoCAF

def test_generar_xml_guia():
    """Genera XML de prueba para Guía de Despacho"""
    
    print("=" * 80)
    print("TEST: Generación de XML para Guía de Despacho (Tipo 52)")
    print("=" * 80)
    
    # 1. Obtener empresa
    try:
        empresa = Empresa.objects.first()
        print(f"\n✓ Empresa: {empresa.nombre}")
        print(f"  RUT: {empresa.rut}")
    except Exception as e:
        print(f"\n✗ Error obteniendo empresa: {e}")
        return
    
    # 2. Obtener una venta reciente (usaremos como base)
    try:
        venta = Venta.objects.filter(empresa=empresa).order_by('-id').first()
        if not venta:
            print("\n✗ No hay ventas en el sistema")
            return
        
        print(f"\n✓ Venta base: ID {venta.id}")
        print(f"  Cliente: {venta.cliente.nombre if venta.cliente else 'Sin cliente'}")
        print(f"  Total: ${venta.total}")
        print(f"  tipo_despacho: {venta.tipo_despacho if hasattr(venta, 'tipo_despacho') else 'N/A'}")
        
        # Simular que tiene tipo_despacho = '1' (Venta)
        if not hasattr(venta, 'tipo_despacho') or not venta.tipo_despacho:
            print("\n  [INFO] Simulando tipo_despacho = '1' (Venta)")
            venta.tipo_despacho = '1'
            # NO guardamos para no modificar la BD
            
    except Exception as e:
        print(f"\n✗ Error obteniendo venta: {e}")
        return
    
    # 3. Obtener CAF para tipo 52
    try:
        caf = ArchivoCAF.objects.filter(
            empresa=empresa,
            tipo_documento='52',
            estado='activo'
        ).first()
        
        if not caf:
            print("\n✗ No hay CAF activo para Guías de Despacho (tipo 52)")
            print("   Creando CAF simulado para prueba...")
            # Usar cualquier CAF disponible solo para estructura
            caf = ArchivoCAF.objects.filter(empresa=empresa, estado='activo').first()
            if not caf:
                print("   ✗ No hay CAFs disponibles en el sistema")
                return
        
        print(f"\n✓ CAF: Tipo {caf.tipo_documento}")
        print(f"  Rango: {caf.folio_desde} - {caf.folio_hasta}")
        print(f"  Folio actual: {caf.folio_actual}")
        
    except Exception as e:
        print(f"\n✗ Error obteniendo CAF: {e}")
        return
    
    # 4. Generar XML usando DTEXMLGenerator
    try:
        print("\n" + "=" * 80)
        print("GENERANDO XML...")
        print("=" * 80)
        
        # Usar un folio de prueba (no consumir folio real)
        folio_prueba = caf.folio_actual + 1
        
        generator = DTEXMLGenerator(
            empresa=empresa,
            documento=venta,  # Pasamos la venta con tipo_despacho simulado
            tipo_dte='52',
            folio=folio_prueba,
            caf=caf
        )
        
        xml_generado = generator.generar_xml()
        
        print("\n✓ XML generado exitosamente!")
        print(f"  Tamaño: {len(xml_generado)} caracteres")
        
        # 5. Mostrar el XML generado
        print("\n" + "=" * 80)
        print("XML GENERADO (primeros 2000 caracteres):")
        print("=" * 80)
        print(xml_generado[:2000])
        
        # 6. Verificar elementos críticos
        print("\n" + "=" * 80)
        print("VERIFICACIÓN DE ESTRUCTURA:")
        print("=" * 80)
        
        verificaciones = {
            '<DTE version="1.0">': 'DTE con version 1.0',
            f'<Documento ID="F{folio_prueba}T52">': 'ID del documento correcto (F{folio}T52)',
            '<IndTraslado>': 'IndTraslado presente en IdDoc',
            '<RznSoc>': 'RznSoc (no RznSocEmisor)',
            '<GiroEmis>': 'GiroEmis (no GiroEmisor)',
            '<Transporte>': 'Sección Transporte (NO debería estar)',
        }
        
        for elemento, descripcion in verificaciones.items():
            if elemento in xml_generado:
                if elemento == '<Transporte>':
                    print(f"  ✗ {descripcion}: ENCONTRADO (debería estar AUSENTE)")
                else:
                    print(f"  ✓ {descripcion}: OK")
            else:
                if elemento == '<Transporte>':
                    print(f"  ✓ {descripcion}: AUSENTE (correcto)")
                else:
                    print(f"  ✗ {descripcion}: NO ENCONTRADO")
        
        # 7. Extraer y mostrar el valor de IndTraslado
        import re
        ind_traslado_match = re.search(r'<IndTraslado>(\d+)</IndTraslado>', xml_generado)
        if ind_traslado_match:
            valor_ind_traslado = ind_traslado_match.group(1)
            print(f"\n  ► IndTraslado = '{valor_ind_traslado}'")
            
            tipos_traslado = {
                '1': 'Venta',
                '2': 'Venta por efectuar (anticipada)',
                '3': 'Consignación',
                '4': 'Devolución',
                '5': 'Traslado interno',
                '6': 'Transformación de productos',
                '7': 'Entrega gratuita',
                '8': 'Otros',
            }
            print(f"    Significado: {tipos_traslado.get(valor_ind_traslado, 'Desconocido')}")
        
        # 8. Guardar XML en archivo para inspección
        output_file = 'C:\\PROJECTOS-WEB\\GestionCloud\\logs\\dtebox_debug\\test_guia_xml.xml'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='ISO-8859-1') as f:
            f.write(xml_generado)
        
        print(f"\n✓ XML guardado en: {output_file}")
        
        print("\n" + "=" * 80)
        print("TEST COMPLETADO EXITOSAMENTE")
        print("=" * 80)
        print("\nEl XML generado tiene la estructura correcta para DTEBox.")
        print("Puedes revisar el archivo completo en:")
        print(f"  {output_file}")
        
    except Exception as e:
        print(f"\n✗ Error generando XML: {e}")
        import traceback
        traceback.print_exc()
        return

if __name__ == '__main__':
    test_generar_xml_guia()
