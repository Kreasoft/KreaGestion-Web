"""
Script para regenerar completamente un DTE con el código actualizado
Incluye todas las correcciones:
- CiudadRecep obligatorio
- IndTraslado en la ubicación correcta
- Tags corregidos (RznSoc, GiroEmis)
- Sin sección Transporte
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dte_generator import DTEXMLGenerator
from facturacion_electronica.firma_electronica import FirmadorDTE

def regenerar_dte_completo(dte_id):
    """Regenera completamente un DTE: XML, firma y TED"""
    
    print("=" * 80)
    print(f"REGENERACIÓN COMPLETA DE DTE ID: {dte_id}")
    print("=" * 80)
    
    try:
        # 1. Obtener el DTE
        dte = DocumentoTributarioElectronico.objects.get(id=dte_id)
        
        print(f"\n✓ DTE encontrado:")
        print(f"  Tipo: {dte.get_tipo_dte_display()}")
        print(f"  Folio: {dte.folio}")
        print(f"  Receptor: {dte.razon_social_receptor}")
        print(f"  Total: ${dte.monto_total}")
        print(f"  Estado: {dte.estado_sii}")
        
        # 2. Verificar venta asociada
        if not dte.venta:
            print("\n✗ Este DTE no tiene venta asociada")
            return False
        
        print(f"\n✓ Venta asociada: ID {dte.venta.id}")
        print(f"  Cliente: {dte.venta.cliente.nombre if dte.venta.cliente else 'Sin cliente'}")
        print(f"  Ciudad: {dte.venta.cliente.ciudad if dte.venta.cliente else 'N/A'}")
        print(f"  tipo_despacho actual: {dte.venta.tipo_despacho if hasattr(dte.venta, 'tipo_despacho') else 'N/A'}")
        
        # 3. PASO 1: Generar nuevo XML
        print("\n" + "=" * 80)
        print("PASO 1: GENERANDO NUEVO XML")
        print("=" * 80)
        
        generator = DTEXMLGenerator(
            empresa=dte.empresa,
            documento=dte,  # Pasamos el DTE que tiene acceso a la venta
            tipo_dte=dte.tipo_dte,
            folio=dte.folio,
            caf=dte.caf_utilizado
        )
        
        xml_nuevo = generator.generar_xml()
        
        print(f"\n✓ XML generado: {len(xml_nuevo)} caracteres")
        
        # Mostrar primeras líneas
        lines = xml_nuevo.split('\n')
        print("\nPrimeras 40 líneas del XML:")
        print("-" * 80)
        for i, line in enumerate(lines[:40], 1):
            print(f"{i:3}: {line}")
        
        # 4. Verificar elementos críticos
        print("\n" + "=" * 80)
        print("VERIFICACIÓN DE ESTRUCTURA:")
        print("=" * 80)
        
        import re
        
        checks = {
            '<IndTraslado>': 'IndTraslado presente',
            '<RznSoc>': 'RznSoc (correcto)',
            '<GiroEmis>': 'GiroEmis (correcto)',
            '<CiudadRecep>': 'CiudadRecep (OBLIGATORIO)',
            '<Transporte>': 'Transporte (NO debería estar)',
        }
        
        for elemento, descripcion in checks.items():
            if elemento in xml_nuevo:
                if elemento == '<Transporte>':
                    print(f"  ✗ {descripcion}: ENCONTRADO (ERROR)")
                else:
                    print(f"  ✓ {descripcion}: OK")
                    
                    # Extraer valor si es IndTraslado
                    if elemento == '<IndTraslado>':
                        match = re.search(r'<IndTraslado>(\d+)</IndTraslado>', xml_nuevo)
                        if match:
                            valor = match.group(1)
                            tipos = {
                                '1': 'Venta',
                                '2': 'Venta por efectuar',
                                '3': 'Consignación',
                                '4': 'Devolución',
                                '5': 'Traslado interno',
                                '6': 'Transformación',
                                '7': 'Entrega gratuita',
                                '8': 'Otros',
                            }
                            print(f"      Valor: {valor} ({tipos.get(valor, 'Desconocido')})")
                    
                    # Extraer valor si es CiudadRecep
                    if elemento == '<CiudadRecep>':
                        match = re.search(r'<CiudadRecep>([^<]+)</CiudadRecep>', xml_nuevo)
                        if match:
                            print(f"      Valor: '{match.group(1)}'")
            else:
                if elemento == '<Transporte>':
                    print(f"  ✓ {descripcion}: AUSENTE (correcto)")
                else:
                    print(f"  ✗ {descripcion}: NO ENCONTRADO (ERROR)")
        
        # 5. PASO 2: Firmar el XML
        print("\n" + "=" * 80)
        print("PASO 2: FIRMANDO XML")
        print("=" * 80)
        
        certificado_path = dte.empresa.certificado_digital.path
        password = dte.empresa.password_certificado
        
        firmador = FirmadorDTE(certificado_path, password)
        xml_firmado = firmador.firmar_xml(xml_nuevo)
        
        print(f"✓ XML firmado: {len(xml_firmado)} caracteres")
        
        # 6. PASO 3: Generar TED
        print("\n" + "=" * 80)
        print("PASO 3: GENERANDO TED (TIMBRE ELECTRÓNICO)")
        print("=" * 80)
        
        # Preparar datos del DTE para el TED
        dte_data = {
            'rut_emisor': dte.empresa.rut,
            'tipo_dte': dte.tipo_dte,
            'folio': dte.folio,
            'fecha_emision': dte.fecha_emision.strftime('%Y-%m-%d'),
            'rut_receptor': dte.rut_receptor,
            'razon_social_receptor': dte.razon_social_receptor,
            'monto_total': dte.monto_total,
            'item_1': 'Documento Tributario Electrónico',
        }
        
        # Parsear datos del CAF
        from lxml import etree
        caf = dte.caf_utilizado
        
        if caf.contenido_caf:
            content = caf.contenido_caf
        else:
            with open(caf.archivo_xml.path, 'r', encoding='ISO-8859-1') as f:
                content = f.read()
        
        if isinstance(content, str):
            content = content.encode('ISO-8859-1')
        
        root = etree.fromstring(content)
        rsapk = root.find('.//RSAPK')
        if rsapk is None:
            rsapk = root.find('.//{http://www.sii.cl/SiiDte}RSAPK')
        
        m = rsapk.find('M')
        if m is None: m = rsapk.find('{http://www.sii.cl/SiiDte}M')
        
        e = rsapk.find('E')
        if e is None: e = rsapk.find('{http://www.sii.cl/SiiDte}E')
        
        caf_data = {
            'rut_emisor': dte.empresa.rut,
            'razon_social': dte.empresa.razon_social_sii or dte.empresa.razon_social,
            'tipo_documento': dte.tipo_dte,
            'folio_desde': caf.folio_desde,
            'folio_hasta': caf.folio_hasta,
            'fecha_autorizacion': caf.fecha_autorizacion.strftime('%Y-%m-%d'),
            'modulo': m.text,
            'exponente': e.text,
            'firma': caf.firma_electronica,
        }
        
        ted_xml = firmador.generar_ted(dte_data, caf_data)
        
        print(f"✓ TED generado: {len(ted_xml)} caracteres")
        
        # 7. PASO 4: Generar PDF417
        print("\n" + "=" * 80)
        print("PASO 4: GENERANDO DATOS PDF417")
        print("=" * 80)
        
        pdf417_data = firmador.generar_datos_pdf417(ted_xml)
        
        print(f"✓ PDF417 generado: {len(pdf417_data)} caracteres")
        
        # 8. PASO 5: Actualizar DTE en la base de datos
        print("\n" + "=" * 80)
        print("PASO 5: ACTUALIZANDO DTE EN LA BASE DE DATOS")
        print("=" * 80)
        
        print("\n¿Deseas actualizar el DTE en la base de datos?")
        print("  1. SÍ - Actualizar XML, firma, TED y PDF417")
        print("  2. NO - Solo guardar en archivo para revisión")
        
        opcion = input("\nIngresa tu opción (1 o 2): ").strip()
        
        if opcion == '1':
            dte.xml_dte = xml_nuevo
            dte.xml_firmado = xml_firmado
            dte.timbre_electronico = ted_xml
            dte.datos_pdf417 = pdf417_data
            dte.save(update_fields=['xml_dte', 'xml_firmado', 'timbre_electronico', 'datos_pdf417'])
            
            print("\n✓ DTE actualizado en la base de datos")
            
            # Regenerar imagen PDF417
            print("\nRegenerando imagen PDF417...")
            from facturacion_electronica.pdf417_generator import PDF417Generator
            PDF417Generator.guardar_pdf417_en_dte(dte)
            print("✓ Imagen PDF417 regenerada")
            
            print("\n" + "=" * 80)
            print("✅ REGENERACIÓN COMPLETADA EXITOSAMENTE")
            print("=" * 80)
            print(f"\nEl DTE {dte_id} ha sido regenerado completamente.")
            print("Ahora puedes intentar enviarlo a DTEBox nuevamente.")
            
        else:
            # Guardar en archivos
            output_dir = 'logs/dtebox_debug'
            os.makedirs(output_dir, exist_ok=True)
            
            with open(f'{output_dir}/dte_{dte_id}_xml_nuevo.xml', 'w', encoding='ISO-8859-1') as f:
                f.write(xml_nuevo)
            
            with open(f'{output_dir}/dte_{dte_id}_xml_firmado.xml', 'w', encoding='ISO-8859-1') as f:
                f.write(xml_firmado)
            
            with open(f'{output_dir}/dte_{dte_id}_ted.xml', 'w', encoding='ISO-8859-1') as f:
                f.write(ted_xml)
            
            print("\n✓ Archivos guardados:")
            print(f"  - {output_dir}/dte_{dte_id}_xml_nuevo.xml")
            print(f"  - {output_dir}/dte_{dte_id}_xml_firmado.xml")
            print(f"  - {output_dir}/dte_{dte_id}_ted.xml")
            print("\nDTE NO actualizado en la base de datos.")
        
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
        dte_id = 74  # DTE por defecto
    
    regenerar_dte_completo(dte_id)
