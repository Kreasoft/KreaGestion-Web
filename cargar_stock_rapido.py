"""
Script rápido para cargar stock inicial

Uso rápido:
    python cargar_stock_rapido.py

Edite las variables EMPRESA_ID, BODEGA_ID y STOCK_DEFAULT según sus necesidades
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from decimal import Decimal
from django.db import transaction
from articulos.models import Articulo
from inventario.models import Stock, Inventario
from bodegas.models import Bodega
from empresas.models import Empresa
from django.contrib.auth.models import User

# ============================================================================
# CONFIGURACIÓN - EDITE ESTOS VALORES
# ============================================================================

EMPRESA_ID = 3          # ID de la empresa (Kreasoft spa)
BODEGA_ID = 2           # ID de la bodega (BODEGA CENTRAL)
STOCK_DEFAULT = 100     # Cantidad de stock por defecto para todos los productos
SOBRESCRIBIR = False    # True = sobrescribe stock existente, False = solo crea nuevos

# ============================================================================

def main():
    print("\n" + "="*70)
    print("CARGA RÁPIDA DE STOCK INICIAL")
    print("="*70)
    
    try:
        # Obtener empresa y bodega
        empresa = Empresa.objects.get(id=EMPRESA_ID)
        bodega = Bodega.objects.get(id=BODEGA_ID, empresa=empresa)
        usuario = User.objects.filter(is_superuser=True).first() or User.objects.first()
        
        print(f"\n📦 Empresa: {empresa.nombre}")
        print(f"🏢 Bodega: {bodega.nombre}")
        print(f"📊 Stock por defecto: {STOCK_DEFAULT}")
        print(f"♻️  Sobrescribir: {'Sí' if SOBRESCRIBIR else 'No'}")
        
        # Obtener artículos
        articulos = Articulo.objects.filter(empresa=empresa, activo=True).order_by('codigo')
        total = articulos.count()
        
        print(f"\n📋 Total de artículos: {total}")
        
        if total == 0:
            print("\n⚠️  No hay artículos para procesar.")
            return
        
        # Confirmar
        print("\n" + "="*70)
        respuesta = input("¿Desea continuar con la carga? (s/n): ").lower()
        if respuesta != 's':
            print("❌ Operación cancelada.")
            return
        
        print("\n🔄 Procesando...\n")
        
        creados = 0
        actualizados = 0
        omitidos = 0
        errores = 0
        
        with transaction.atomic():
            for i, articulo in enumerate(articulos, 1):
                try:
                    # Verificar stock existente
                    stock_obj = Stock.objects.filter(
                        empresa=empresa,
                        bodega=bodega,
                        articulo=articulo
                    ).first()
                    
                    if stock_obj and not SOBRESCRIBIR:
                        omitidos += 1
                        if i % 10 == 0:  # Mostrar cada 10
                            print(f"[{i}/{total}] Procesando... (Omitidos: {omitidos})")
                        continue
                    
                    # Crear o actualizar
                    stock_obj, created = Stock.objects.get_or_create(
                        empresa=empresa,
                        bodega=bodega,
                        articulo=articulo,
                        defaults={
                            'cantidad': Decimal(str(STOCK_DEFAULT)),
                            'stock_minimo': Decimal(str(articulo.stock_minimo or 10)),
                            'stock_maximo': Decimal(str(articulo.stock_maximo or 1000)),
                            'precio_promedio': Decimal(str(articulo.precio_costo or 0)),
                            'actualizado_por': usuario
                        }
                    )
                    
                    if not created:
                        stock_obj.cantidad = Decimal(str(STOCK_DEFAULT))
                        stock_obj.actualizado_por = usuario
                        stock_obj.save()
                        actualizados += 1
                    else:
                        creados += 1
                    
                    # Crear movimiento
                    Inventario.objects.create(
                        empresa=empresa,
                        bodega_destino=bodega,
                        articulo=articulo,
                        tipo_movimiento='entrada',
                        cantidad=Decimal(str(STOCK_DEFAULT)),
                        precio_unitario=Decimal(str(articulo.precio_costo or 0)),
                        descripcion='Carga inicial automática',
                        estado='completado',
                        creado_por=usuario
                    )
                    
                    if i % 10 == 0:  # Mostrar progreso cada 10
                        print(f"[{i}/{total}] Procesando... (Creados: {creados}, Actualizados: {actualizados})")
                    
                except Exception as e:
                    errores += 1
                    print(f"❌ Error en {articulo.codigo}: {str(e)}")
        
        # Resumen final
        print("\n" + "="*70)
        print("✅ CARGA COMPLETADA")
        print("="*70)
        print(f"✅ Creados: {creados}")
        print(f"✏️  Actualizados: {actualizados}")
        print(f"⏭️  Omitidos: {omitidos}")
        print(f"❌ Errores: {errores}")
        print("="*70 + "\n")
        
    except Empresa.DoesNotExist:
        print(f"\n❌ ERROR: Empresa con ID {EMPRESA_ID} no encontrada.")
        print("💡 Verifique el ID en la configuración del script.\n")
    except Bodega.DoesNotExist:
        print(f"\n❌ ERROR: Bodega con ID {BODEGA_ID} no encontrada.")
        print("💡 Verifique el ID en la configuración del script.\n")
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {str(e)}\n")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
