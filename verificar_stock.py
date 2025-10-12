"""
Script para verificar el stock cargado

Uso:
    python verificar_stock.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from articulos.models import Articulo
from inventario.models import Stock
from bodegas.models import Bodega
from empresas.models import Empresa

# ============================================================================
# CONFIGURACIÓN
# ============================================================================
EMPRESA_ID = 1
BODEGA_ID = None  # None = todas las bodegas
# ============================================================================


def verificar_stock(empresa_id, bodega_id=None):
    """Verifica el stock actual de los productos"""
    
    try:
        empresa = Empresa.objects.get(id=empresa_id)
        
        print("\n" + "="*80)
        print("VERIFICACIÓN DE STOCK")
        print("="*80)
        print(f"📦 Empresa: {empresa.nombre}")
        
        if bodega_id:
            bodega = Bodega.objects.get(id=bodega_id, empresa=empresa)
            print(f"🏢 Bodega: {bodega.nombre}")
            bodegas = [bodega]
        else:
            bodegas = Bodega.objects.filter(empresa=empresa, activa=True)
            print(f"🏢 Bodegas: Todas ({bodegas.count()})")
        
        print("="*80 + "\n")
        
        # Estadísticas generales
        total_articulos = Articulo.objects.filter(empresa=empresa, activo=True).count()
        total_con_stock = Stock.objects.filter(empresa=empresa, cantidad__gt=0).values('articulo').distinct().count()
        total_sin_stock = total_articulos - total_con_stock
        
        print("📊 RESUMEN GENERAL")
        print("-" * 80)
        print(f"Total de artículos activos: {total_articulos}")
        print(f"Artículos con stock: {total_con_stock}")
        print(f"Artículos sin stock: {total_sin_stock}")
        print()
        
        # Por bodega
        for bodega in bodegas:
            print(f"\n🏢 BODEGA: {bodega.nombre}")
            print("-" * 80)
            
            stocks = Stock.objects.filter(
                empresa=empresa,
                bodega=bodega
            ).select_related('articulo').order_by('-cantidad')
            
            total_items = stocks.count()
            con_stock = stocks.filter(cantidad__gt=0).count()
            sin_stock = total_items - con_stock
            valor_total = sum(float(s.cantidad * s.precio_promedio) for s in stocks)
            
            print(f"Items registrados: {total_items}")
            print(f"Con stock (>0): {con_stock}")
            print(f"Sin stock (=0): {sin_stock}")
            print(f"Valor total estimado: ${valor_total:,.2f}")
            
            # Top 10 con más stock
            print(f"\n📈 TOP 10 CON MÁS STOCK:")
            for i, stock in enumerate(stocks[:10], 1):
                print(f"  {i:2}. {stock.articulo.codigo:15} {stock.articulo.nombre[:40]:40} → {float(stock.cantidad):>8.0f}")
            
            # Artículos con stock bajo
            stock_bajo = stocks.filter(
                cantidad__gt=0,
                cantidad__lte=stock.stock_minimo
            )
            
            if stock_bajo.exists():
                print(f"\n⚠️  STOCK BAJO ({stock_bajo.count()} artículos):")
                for stock in stock_bajo[:10]:
                    print(f"  • {stock.articulo.codigo:15} {stock.articulo.nombre[:40]:40} → {float(stock.cantidad):>6.0f} (mín: {float(stock.stock_minimo)})")
                if stock_bajo.count() > 10:
                    print(f"  ... y {stock_bajo.count() - 10} más")
            
            # Artículos sin stock
            sin_stock_list = Stock.objects.filter(
                empresa=empresa,
                bodega=bodega,
                cantidad=0
            ).select_related('articulo')[:10]
            
            if sin_stock_list.exists():
                print(f"\n❌ SIN STOCK (primeros 10):")
                for stock in sin_stock_list:
                    print(f"  • {stock.articulo.codigo:15} {stock.articulo.nombre[:40]}")
        
        # Artículos sin registro de stock
        articulos_sin_registro = Articulo.objects.filter(
            empresa=empresa,
            activo=True
        ).exclude(
            id__in=Stock.objects.filter(empresa=empresa).values_list('articulo_id', flat=True)
        )
        
        if articulos_sin_registro.exists():
            print(f"\n⚠️  ARTÍCULOS SIN REGISTRO DE STOCK ({articulos_sin_registro.count()}):")
            for art in articulos_sin_registro[:10]:
                print(f"  • {art.codigo:15} {art.nombre[:40]}")
            if articulos_sin_registro.count() > 10:
                print(f"  ... y {articulos_sin_registro.count() - 10} más")
        
        print("\n" + "="*80 + "\n")
        
    except Empresa.DoesNotExist:
        print(f"\n❌ ERROR: Empresa con ID {empresa_id} no encontrada.\n")
    except Bodega.DoesNotExist:
        print(f"\n❌ ERROR: Bodega con ID {bodega_id} no encontrada.\n")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}\n")
        import traceback
        traceback.print_exc()


def exportar_reporte_csv(empresa_id, bodega_id=None, archivo='reporte_stock.csv'):
    """Exporta reporte de stock a CSV"""
    import csv
    
    try:
        empresa = Empresa.objects.get(id=empresa_id)
        
        if bodega_id:
            bodega = Bodega.objects.get(id=bodega_id, empresa=empresa)
            stocks = Stock.objects.filter(empresa=empresa, bodega=bodega)
        else:
            stocks = Stock.objects.filter(empresa=empresa)
        
        stocks = stocks.select_related('articulo', 'bodega').order_by('articulo__codigo')
        
        with open(archivo, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Código',
                'Nombre',
                'Bodega',
                'Cantidad',
                'Stock Mínimo',
                'Stock Máximo',
                'Precio Promedio',
                'Valor Total'
            ])
            
            for stock in stocks:
                valor_total = float(stock.cantidad * stock.precio_promedio)
                writer.writerow([
                    stock.articulo.codigo,
                    stock.articulo.nombre,
                    stock.bodega.nombre,
                    float(stock.cantidad),
                    float(stock.stock_minimo),
                    float(stock.stock_maximo),
                    float(stock.precio_promedio),
                    valor_total
                ])
        
        print(f"\n✅ Reporte exportado: {archivo}")
        print(f"   Total de registros: {stocks.count()}\n")
        
    except Exception as e:
        print(f"\n❌ ERROR al exportar: {str(e)}\n")


def menu():
    """Menú principal"""
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║         VERIFICACIÓN DE STOCK                             ║
    ║                 GestionCloud                               ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    print("\nOpciones:")
    print("1. Ver resumen de stock")
    print("2. Ver resumen de stock por bodega específica")
    print("3. Exportar reporte a CSV")
    print("4. Salir")
    
    opcion = input("\nSeleccione una opción: ").strip()
    
    if opcion == '1':
        verificar_stock(EMPRESA_ID)
        input("\nPresione Enter para continuar...")
        menu()
    
    elif opcion == '2':
        empresa = Empresa.objects.get(id=EMPRESA_ID)
        bodegas = Bodega.objects.filter(empresa=empresa, activa=True)
        
        print("\nBodegas disponibles:")
        for bodega in bodegas:
            print(f"  {bodega.id}. {bodega.nombre}")
        
        bodega_id = input("\nIngrese ID de bodega: ").strip()
        verificar_stock(EMPRESA_ID, int(bodega_id))
        input("\nPresione Enter para continuar...")
        menu()
    
    elif opcion == '3':
        archivo = input("Nombre del archivo (default: reporte_stock.csv): ").strip() or 'reporte_stock.csv'
        exportar_reporte_csv(EMPRESA_ID, BODEGA_ID, archivo)
        input("\nPresione Enter para continuar...")
        menu()
    
    elif opcion == '4':
        print("\n👋 ¡Hasta luego!\n")
    
    else:
        print("\n❌ Opción no válida")
        menu()


if __name__ == '__main__':
    try:
        menu()
    except KeyboardInterrupt:
        print("\n\n👋 ¡Hasta luego!\n")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}\n")
