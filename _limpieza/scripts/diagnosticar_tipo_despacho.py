"""
Script de diagnóstico para rastrear el flujo del tipo_despacho
Desde el frontend hasta la base de datos
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from ventas.models import Venta
from facturacion_electronica.models import DocumentoTributarioElectronico

def diagnosticar_tipo_despacho():
    """Diagnostica el flujo del tipo_despacho"""
    
    print("=" * 80)
    print("DIAGNÓSTICO: FLUJO DE tipo_despacho")
    print("=" * 80)
    
    # 1. Verificar últimas ventas con tipo guía
    print("\n1. ÚLTIMAS VENTAS DE TIPO GUÍA:")
    print("-" * 80)
    
    ventas_guia = Venta.objects.filter(
        tipo_documento='guia'
    ).order_by('-id')[:10]
    
    if not ventas_guia:
        print("  ⚠️  No hay ventas de tipo guía en el sistema")
    else:
        for venta in ventas_guia:
            print(f"\n  Venta ID: {venta.id}")
            print(f"    Número: {venta.numero_venta}")
            print(f"    Cliente: {venta.cliente.nombre if venta.cliente else 'Sin cliente'}")
            print(f"    tipo_documento: {venta.tipo_documento}")
            print(f"    tipo_despacho: {venta.tipo_despacho if hasattr(venta, 'tipo_despacho') else 'CAMPO NO EXISTE'}")
            print(f"    Estado: {venta.estado}")
            print(f"    Fecha: {venta.fecha}")
    
    # 2. Verificar DTEs de tipo 52
    print("\n\n2. ÚLTIMOS DTEs DE TIPO 52 (GUÍAS):")
    print("-" * 80)
    
    dtes_guia = DocumentoTributarioElectronico.objects.filter(
        tipo_dte='52'
    ).order_by('-id')[:10]
    
    if not dtes_guia:
        print("  ⚠️  No hay DTEs de tipo 52 en el sistema")
    else:
        for dte in dtes_guia:
            print(f"\n  DTE ID: {dte.id}")
            print(f"    Folio: {dte.folio}")
            print(f"    Receptor: {dte.razon_social_receptor}")
            print(f"    tipo_traslado (DTE): {dte.tipo_traslado}")
            
            if dte.venta:
                print(f"    Venta asociada ID: {dte.venta.id}")
                print(f"    tipo_despacho (Venta): {dte.venta.tipo_despacho if hasattr(dte.venta, 'tipo_despacho') else 'CAMPO NO EXISTE'}")
            else:
                print(f"    Venta asociada: Ninguna")
            
            # Verificar XML
            if dte.xml_dte:
                import re
                match = re.search(r'<IndTraslado>(\d+)</IndTraslado>', dte.xml_dte)
                if match:
                    valor_xml = match.group(1)
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
                    print(f"    IndTraslado en XML: {valor_xml} ({tipos.get(valor_xml, 'Desconocido')})")
                else:
                    print(f"    IndTraslado en XML: NO ENCONTRADO")
    
    # 3. Verificar modelo Venta
    print("\n\n3. VERIFICACIÓN DEL MODELO VENTA:")
    print("-" * 80)
    
    from django.db import connection
    
    # Verificar si la columna existe en la tabla
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'ventas_venta' AND COLUMN_NAME = 'tipo_despacho'
        """)
        resultado = cursor.fetchone()
        
        if resultado:
            print(f"  ✓ Campo 'tipo_despacho' EXISTE en la tabla ventas_venta")
            print(f"    Tipo de dato: {resultado[1]}")
            print(f"    Permite NULL: {resultado[2]}")
            print(f"    Valor por defecto: {resultado[3] or 'NULL'}")
        else:
            print(f"  ✗ Campo 'tipo_despacho' NO EXISTE en la tabla ventas_venta")
            print(f"    ¡ESTE ES EL PROBLEMA! Necesitas ejecutar las migraciones.")
    
    # 4. Verificar modelo DocumentoTributarioElectronico
    print("\n\n4. VERIFICACIÓN DEL MODELO DocumentoTributarioElectronico:")
    print("-" * 80)
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'facturacion_electronica_documentotributarioelectronico' 
            AND COLUMN_NAME = 'tipo_traslado'
        """)
        resultado = cursor.fetchone()
        
        if resultado:
            print(f"  ✓ Campo 'tipo_traslado' EXISTE en la tabla")
            print(f"    Tipo de dato: {resultado[1]}")
            print(f"    Permite NULL: {resultado[2]}")
            print(f"    Valor por defecto: {resultado[3] or 'NULL'}")
        else:
            print(f"  ✗ Campo 'tipo_traslado' NO EXISTE en la tabla")
    
    # 5. Análisis del problema
    print("\n\n" + "=" * 80)
    print("ANÁLISIS DEL PROBLEMA:")
    print("=" * 80)
    
    # Contar ventas con tipo_despacho NULL
    ventas_null = Venta.objects.filter(
        tipo_documento='guia',
        tipo_despacho__isnull=True
    ).count()
    
    ventas_con_valor = Venta.objects.filter(
        tipo_documento='guia',
        tipo_despacho__isnull=False
    ).count()
    
    print(f"\nVentas de tipo guía:")
    print(f"  Con tipo_despacho NULL: {ventas_null}")
    print(f"  Con tipo_despacho definido: {ventas_con_valor}")
    
    if ventas_null > 0 and ventas_con_valor == 0:
        print("\n❌ PROBLEMA CONFIRMADO:")
        print("   TODAS las guías tienen tipo_despacho en NULL")
        print("\nPosibles causas:")
        print("  1. El formulario no está enviando el valor")
        print("  2. El backend no está guardando el valor")
        print("  3. El campo se está sobrescribiendo después de guardarse")
    
    # 6. Recomendaciones
    print("\n\n" + "=" * 80)
    print("RECOMENDACIONES:")
    print("=" * 80)
    
    print("\n1. Verificar que el dropdown esté enviando el valor:")
    print("   - Abrir DevTools del navegador")
    print("   - Ir a Network > XHR")
    print("   - Crear una guía y verificar el payload JSON")
    print("   - Buscar el campo 'tipo_despacho' en el request")
    
    print("\n2. Verificar que el backend esté recibiendo el valor:")
    print("   - Revisar los logs del servidor cuando se crea una guía")
    print("   - Buscar: [DEBUG] tipo_despacho recibido:")
    
    print("\n3. Verificar que se esté guardando en la BD:")
    print("   - Después de crear una guía, ejecutar:")
    print("   - SELECT id, numero_venta, tipo_despacho FROM ventas_venta")
    print("     WHERE tipo_documento='guia' ORDER BY id DESC LIMIT 1;")

if __name__ == '__main__':
    diagnosticar_tipo_despacho()
