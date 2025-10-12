"""
Script para cargar stock desde archivo CSV

Formato del CSV:
    codigo,cantidad
    ART001,100
    ART002,50
    ART003,75

Uso:
    python cargar_stock_desde_csv.py archivo.csv

O editar las variables y ejecutar directamente
"""

import os
import django
import sys
import csv
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.db import transaction
from articulos.models import Articulo
from inventario.models import Stock, Inventario
from bodegas.models import Bodega
from empresas.models import Empresa
from django.contrib.auth.models import User

# ============================================================================
# CONFIGURACIÓN
# ============================================================================
EMPRESA_ID = 1
BODEGA_ID = 1
ARCHIVO_CSV = 'stock_inicial.csv'  # Cambiar por tu archivo
# ============================================================================


def cargar_desde_csv(archivo_csv, empresa_id, bodega_id):
    """Carga stock desde archivo CSV"""
    
    try:
        empresa = Empresa.objects.get(id=empresa_id)
        bodega = Bodega.objects.get(id=bodega_id, empresa=empresa)
        usuario = User.objects.filter(is_superuser=True).first() or User.objects.first()
        
        print("\n" + "="*70)
        print("CARGA DE STOCK DESDE CSV")
        print("="*70)
        print(f"📦 Empresa: {empresa.nombre}")
        print(f"🏢 Bodega: {bodega.nombre}")
        print(f"📄 Archivo: {archivo_csv}")
        print("="*70 + "\n")
        
        # Leer CSV
        if not os.path.exists(archivo_csv):
            print(f"❌ Error: Archivo '{archivo_csv}' no encontrado.")
            print("\n💡 Cree un archivo CSV con el formato:")
            print("   codigo,cantidad")
            print("   ART001,100")
            print("   ART002,50")
            return
        
        datos = []
        with open(archivo_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                datos.append({
                    'codigo': row['codigo'].strip(),
                    'cantidad': float(row['cantidad'])
                })
        
        total = len(datos)
        print(f"📋 Total de registros en CSV: {total}\n")
        
        if total == 0:
            print("⚠️  El archivo CSV está vacío.")
            return
        
        # Mostrar primeros 5 registros
        print("Vista previa (primeros 5):")
        for i, item in enumerate(datos[:5], 1):
            print(f"  {i}. {item['codigo']} → {item['cantidad']}")
        if total > 5:
            print(f"  ... y {total - 5} más")
        
        # Confirmar
        print("\n" + "="*70)
        respuesta = input("¿Desea continuar con la carga? (s/n): ").lower()
        if respuesta != 's':
            print("❌ Operación cancelada.")
            return
        
        print("\n🔄 Procesando...\n")
        
        procesados = 0
        errores = 0
        errores_detalle = []
        
        with transaction.atomic():
            for i, item in enumerate(datos, 1):
                try:
                    codigo = item['codigo']
                    cantidad = item['cantidad']
                    
                    # Buscar artículo
                    articulo = Articulo.objects.get(
                        codigo=codigo,
                        empresa=empresa,
                        activo=True
                    )
                    
                    # Crear o actualizar stock
                    stock_obj, created = Stock.objects.get_or_create(
                        empresa=empresa,
                        bodega=bodega,
                        articulo=articulo,
                        defaults={
                            'cantidad': Decimal(str(cantidad)),
                            'stock_minimo': Decimal(str(articulo.stock_minimo or 10)),
                            'stock_maximo': Decimal(str(articulo.stock_maximo or 1000)),
                            'precio_promedio': Decimal(str(articulo.precio_costo or 0)),
                            'actualizado_por': usuario
                        }
                    )
                    
                    if not created:
                        stock_obj.cantidad = Decimal(str(cantidad))
                        stock_obj.actualizado_por = usuario
                        stock_obj.save()
                    
                    # Crear movimiento
                    Inventario.objects.create(
                        empresa=empresa,
                        bodega_destino=bodega,
                        articulo=articulo,
                        tipo_movimiento='entrada',
                        cantidad=Decimal(str(cantidad)),
                        precio_unitario=Decimal(str(articulo.precio_costo or 0)),
                        descripcion=f'Carga desde CSV: {os.path.basename(archivo_csv)}',
                        estado='completado',
                        creado_por=usuario
                    )
                    
                    procesados += 1
                    print(f"[{i}/{total}] ✅ {codigo} - {articulo.nombre[:40]} → {cantidad}")
                    
                except Articulo.DoesNotExist:
                    errores += 1
                    error_msg = f"Artículo '{codigo}' no encontrado"
                    errores_detalle.append(error_msg)
                    print(f"[{i}/{total}] ❌ {error_msg}")
                    
                except Exception as e:
                    errores += 1
                    error_msg = f"Error en {codigo}: {str(e)}"
                    errores_detalle.append(error_msg)
                    print(f"[{i}/{total}] ❌ {error_msg}")
        
        # Resumen
        print("\n" + "="*70)
        print("✅ CARGA COMPLETADA")
        print("="*70)
        print(f"✅ Procesados: {procesados}")
        print(f"❌ Errores: {errores}")
        print("="*70)
        
        if errores > 0:
            print("\nDetalle de errores:")
            for error in errores_detalle[:10]:  # Mostrar máximo 10
                print(f"  - {error}")
            if len(errores_detalle) > 10:
                print(f"  ... y {len(errores_detalle) - 10} errores más")
        
        print()
        
    except Empresa.DoesNotExist:
        print(f"\n❌ ERROR: Empresa con ID {empresa_id} no encontrada.\n")
    except Bodega.DoesNotExist:
        print(f"\n❌ ERROR: Bodega con ID {bodega_id} no encontrada.\n")
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {str(e)}\n")
        import traceback
        traceback.print_exc()


def crear_csv_ejemplo():
    """Crea un archivo CSV de ejemplo"""
    archivo = 'stock_inicial_ejemplo.csv'
    
    with open(archivo, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['codigo', 'cantidad'])
        writer.writerow(['ART001', '100'])
        writer.writerow(['ART002', '50'])
        writer.writerow(['ART003', '75'])
        writer.writerow(['PROD001', '200'])
    
    print(f"\n✅ Archivo de ejemplo creado: {archivo}")
    print("\nContenido:")
    with open(archivo, 'r', encoding='utf-8') as f:
        print(f.read())


if __name__ == '__main__':
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║         CARGA DE STOCK DESDE CSV                          ║
    ║                 GestionCloud                               ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    # Si se pasa archivo como argumento
    if len(sys.argv) > 1:
        archivo = sys.argv[1]
        cargar_desde_csv(archivo, EMPRESA_ID, BODEGA_ID)
    
    # Si no, usar el configurado
    elif os.path.exists(ARCHIVO_CSV):
        cargar_desde_csv(ARCHIVO_CSV, EMPRESA_ID, BODEGA_ID)
    
    # Si no existe, ofrecer crear ejemplo
    else:
        print(f"\n⚠️  Archivo '{ARCHIVO_CSV}' no encontrado.")
        print("\nOpciones:")
        print("1. Crear archivo CSV de ejemplo")
        print("2. Especificar ruta de archivo")
        print("3. Salir")
        
        opcion = input("\nSeleccione una opción: ").strip()
        
        if opcion == '1':
            crear_csv_ejemplo()
            print("\n💡 Edite el archivo y vuelva a ejecutar el script.")
        elif opcion == '2':
            archivo = input("Ingrese la ruta del archivo CSV: ").strip()
            if os.path.exists(archivo):
                cargar_desde_csv(archivo, EMPRESA_ID, BODEGA_ID)
            else:
                print(f"\n❌ Archivo '{archivo}' no encontrado.")
        else:
            print("\n👋 ¡Hasta luego!")
