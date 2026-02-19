"""
Script para cargar stock inicial a productos existentes

Uso:
    python cargar_stock_inicial.py

Este script permite:
1. Cargar stock inicial a todos los productos de una empresa
2. Especificar la cantidad de stock por defecto
3. Crear los movimientos de inventario correspondientes
"""

import os
import django
import sys
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.db import transaction
from articulos.models import Articulo
from inventario.models import Stock, Inventario
from bodegas.models import Bodega
from empresas.models import Empresa
from django.contrib.auth.models import User


def listar_empresas():
    """Lista todas las empresas disponibles"""
    empresas = Empresa.objects.all()
    print("\n" + "="*60)
    print("EMPRESAS DISPONIBLES")
    print("="*60)
    for empresa in empresas:
        print(f"ID: {empresa.id} - {empresa.nombre}")
    print("="*60 + "\n")
    return empresas


def listar_bodegas(empresa):
    """Lista todas las bodegas de una empresa"""
    bodegas = Bodega.objects.filter(empresa=empresa, activa=True)
    print("\n" + "="*60)
    print(f"BODEGAS DISPONIBLES EN {empresa.nombre}")
    print("="*60)
    for bodega in bodegas:
        print(f"ID: {bodega.id} - {bodega.nombre}")
    print("="*60 + "\n")
    return bodegas


def obtener_usuario_admin():
    """Obtiene el primer usuario administrador"""
    usuario = User.objects.filter(is_superuser=True).first()
    if not usuario:
        usuario = User.objects.first()
    return usuario


def cargar_stock_masivo(empresa_id, bodega_id, stock_default=100, sobrescribir=False):
    """
    Carga stock inicial a todos los productos de una empresa
    
    Args:
        empresa_id: ID de la empresa
        bodega_id: ID de la bodega
        stock_default: Cantidad de stock por defecto
        sobrescribir: Si True, sobrescribe el stock existente
    """
    try:
        empresa = Empresa.objects.get(id=empresa_id)
        bodega = Bodega.objects.get(id=bodega_id, empresa=empresa)
        usuario = obtener_usuario_admin()
        
        print(f"\n{'='*60}")
        print(f"CARGANDO STOCK INICIAL")
        print(f"{'='*60}")
        print(f"Empresa: {empresa.nombre}")
        print(f"Bodega: {bodega.nombre}")
        print(f"Stock por defecto: {stock_default}")
        print(f"Sobrescribir existente: {'Sí' if sobrescribir else 'No'}")
        print(f"{'='*60}\n")
        
        # Obtener todos los artículos activos de la empresa
        articulos = Articulo.objects.filter(empresa=empresa, activo=True).order_by('codigo')
        total_articulos = articulos.count()
        
        print(f"Total de artículos a procesar: {total_articulos}\n")
        
        if total_articulos == 0:
            print("⚠️  No hay artículos para procesar.")
            return
        
        # Confirmar acción
        respuesta = input("¿Desea continuar? (s/n): ").lower()
        if respuesta != 's':
            print("❌ Operación cancelada.")
            return
        
        procesados = 0
        creados = 0
        actualizados = 0
        omitidos = 0
        errores = 0
        
        with transaction.atomic():
            for i, articulo in enumerate(articulos, 1):
                try:
                    # Verificar si ya existe stock
                    stock_existente = Stock.objects.filter(
                        empresa=empresa,
                        bodega=bodega,
                        articulo=articulo
                    ).first()
                    
                    if stock_existente and not sobrescribir:
                        print(f"[{i}/{total_articulos}] ⏭️  {articulo.codigo} - {articulo.nombre[:40]} (Ya tiene stock: {stock_existente.cantidad})")
                        omitidos += 1
                        continue
                    
                    # Crear o actualizar stock
                    stock, created = Stock.objects.get_or_create(
                        empresa=empresa,
                        bodega=bodega,
                        articulo=articulo,
                        defaults={
                            'cantidad': Decimal(str(stock_default)),
                            'stock_minimo': Decimal(str(articulo.stock_minimo)) if articulo.stock_minimo else Decimal('10'),
                            'stock_maximo': Decimal(str(articulo.stock_maximo)) if articulo.stock_maximo else Decimal('1000'),
                            'precio_promedio': Decimal(str(articulo.precio_costo)) if articulo.precio_costo else Decimal('0'),
                            'actualizado_por': usuario
                        }
                    )
                    
                    if not created and sobrescribir:
                        stock.cantidad = Decimal(str(stock_default))
                        stock.actualizado_por = usuario
                        stock.save()
                        actualizados += 1
                        print(f"[{i}/{total_articulos}] ✏️  {articulo.codigo} - {articulo.nombre[:40]} (Actualizado)")
                    else:
                        creados += 1
                        print(f"[{i}/{total_articulos}] ✅ {articulo.codigo} - {articulo.nombre[:40]} (Creado)")
                    
                    # Crear movimiento de inventario
                    Inventario.objects.create(
                        empresa=empresa,
                        bodega_destino=bodega,
                        articulo=articulo,
                        tipo_movimiento='entrada',
                        cantidad=Decimal(str(stock_default)),
                        precio_unitario=Decimal(str(articulo.precio_costo)) if articulo.precio_costo else Decimal('0'),
                        descripcion='Carga inicial de inventario (script automático)',
                        estado='completado',
                        creado_por=usuario
                    )
                    
                    procesados += 1
                    
                except Exception as e:
                    errores += 1
                    print(f"[{i}/{total_articulos}] ❌ Error en {articulo.codigo}: {str(e)}")
        
        # Resumen
        print(f"\n{'='*60}")
        print("RESUMEN DE CARGA")
        print(f"{'='*60}")
        print(f"Total procesados: {procesados}")
        print(f"Creados: {creados}")
        print(f"Actualizados: {actualizados}")
        print(f"Omitidos: {omitidos}")
        print(f"Errores: {errores}")
        print(f"{'='*60}\n")
        
        if errores == 0:
            print("✅ Carga completada exitosamente!")
        else:
            print(f"⚠️  Carga completada con {errores} errores.")
        
    except Empresa.DoesNotExist:
        print(f"❌ Error: Empresa con ID {empresa_id} no encontrada.")
    except Bodega.DoesNotExist:
        print(f"❌ Error: Bodega con ID {bodega_id} no encontrada o no pertenece a la empresa.")
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")
        import traceback
        traceback.print_exc()


def cargar_stock_personalizado(empresa_id, bodega_id, datos_stock):
    """
    Carga stock personalizado desde un diccionario
    
    Args:
        empresa_id: ID de la empresa
        bodega_id: ID de la bodega
        datos_stock: Diccionario con formato {codigo_articulo: cantidad}
    
    Ejemplo:
        datos = {
            'ART001': 50,
            'ART002': 100,
            'ART003': 75,
        }
        cargar_stock_personalizado(1, 1, datos)
    """
    try:
        empresa = Empresa.objects.get(id=empresa_id)
        bodega = Bodega.objects.get(id=bodega_id, empresa=empresa)
        usuario = obtener_usuario_admin()
        
        print(f"\n{'='*60}")
        print(f"CARGANDO STOCK PERSONALIZADO")
        print(f"{'='*60}")
        print(f"Empresa: {empresa.nombre}")
        print(f"Bodega: {bodega.nombre}")
        print(f"Artículos a cargar: {len(datos_stock)}")
        print(f"{'='*60}\n")
        
        procesados = 0
        errores = 0
        errores_detalle = []
        
        with transaction.atomic():
            for codigo, cantidad in datos_stock.items():
                try:
                    # Buscar artículo por código
                    articulo = Articulo.objects.get(
                        codigo=codigo,
                        empresa=empresa,
                        activo=True
                    )
                    
                    # Crear o actualizar stock
                    stock, created = Stock.objects.get_or_create(
                        empresa=empresa,
                        bodega=bodega,
                        articulo=articulo,
                        defaults={
                            'cantidad': Decimal(str(cantidad)),
                            'stock_minimo': Decimal(str(articulo.stock_minimo)) if articulo.stock_minimo else Decimal('10'),
                            'stock_maximo': Decimal(str(articulo.stock_maximo)) if articulo.stock_maximo else Decimal('1000'),
                            'precio_promedio': Decimal(str(articulo.precio_costo)) if articulo.precio_costo else Decimal('0'),
                            'actualizado_por': usuario
                        }
                    )
                    
                    if not created:
                        stock.cantidad = Decimal(str(cantidad))
                        stock.actualizado_por = usuario
                        stock.save()
                    
                    # Crear movimiento de inventario
                    Inventario.objects.create(
                        empresa=empresa,
                        bodega_destino=bodega,
                        articulo=articulo,
                        tipo_movimiento='entrada',
                        cantidad=Decimal(str(cantidad)),
                        precio_unitario=Decimal(str(articulo.precio_costo)) if articulo.precio_costo else Decimal('0'),
                        descripcion='Carga inicial de inventario (script personalizado)',
                        estado='completado',
                        creado_por=usuario
                    )
                    
                    procesados += 1
                    print(f"✅ {codigo} - {articulo.nombre[:40]} - Stock: {cantidad}")
                    
                except Articulo.DoesNotExist:
                    errores += 1
                    error_msg = f"Artículo con código '{codigo}' no encontrado"
                    errores_detalle.append(error_msg)
                    print(f"❌ {error_msg}")
                except Exception as e:
                    errores += 1
                    error_msg = f"Error en {codigo}: {str(e)}"
                    errores_detalle.append(error_msg)
                    print(f"❌ {error_msg}")
        
        # Resumen
        print(f"\n{'='*60}")
        print("RESUMEN DE CARGA")
        print(f"{'='*60}")
        print(f"Procesados: {procesados}")
        print(f"Errores: {errores}")
        print(f"{'='*60}\n")
        
        if errores > 0:
            print("Detalle de errores:")
            for error in errores_detalle:
                print(f"  - {error}")
        
    except Empresa.DoesNotExist:
        print(f"❌ Error: Empresa con ID {empresa_id} no encontrada.")
    except Bodega.DoesNotExist:
        print(f"❌ Error: Bodega con ID {bodega_id} no encontrada.")
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")


def menu_principal():
    """Menú principal del script"""
    print("\n" + "="*60)
    print("SCRIPT DE CARGA INICIAL DE STOCK")
    print("="*60)
    print("1. Cargar stock masivo (misma cantidad para todos)")
    print("2. Cargar stock personalizado (cantidad por artículo)")
    print("3. Ver empresas disponibles")
    print("4. Ver bodegas de una empresa")
    print("5. Salir")
    print("="*60)
    
    opcion = input("\nSeleccione una opción: ").strip()
    
    if opcion == '1':
        # Cargar stock masivo
        listar_empresas()
        empresa_id = input("Ingrese ID de la empresa: ").strip()
        
        try:
            empresa = Empresa.objects.get(id=empresa_id)
            listar_bodegas(empresa)
            bodega_id = input("Ingrese ID de la bodega: ").strip()
            stock_default = input("Ingrese cantidad de stock por defecto (default: 100): ").strip() or "100"
            sobrescribir = input("¿Sobrescribir stock existente? (s/n, default: n): ").strip().lower() == 's'
            
            cargar_stock_masivo(
                empresa_id=int(empresa_id),
                bodega_id=int(bodega_id),
                stock_default=float(stock_default),
                sobrescribir=sobrescribir
            )
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    elif opcion == '2':
        # Cargar stock personalizado
        print("\n⚠️  Para usar esta opción, edite el script y agregue sus datos en la sección correspondiente.")
        print("Ejemplo:")
        print("  datos_stock = {")
        print("      'ART001': 50,")
        print("      'ART002': 100,")
        print("  }")
        
    elif opcion == '3':
        # Ver empresas
        listar_empresas()
        input("\nPresione Enter para continuar...")
        menu_principal()
    
    elif opcion == '4':
        # Ver bodegas
        listar_empresas()
        empresa_id = input("Ingrese ID de la empresa: ").strip()
        try:
            empresa = Empresa.objects.get(id=empresa_id)
            listar_bodegas(empresa)
            input("\nPresione Enter para continuar...")
            menu_principal()
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    elif opcion == '5':
        print("\n👋 ¡Hasta luego!")
        sys.exit(0)
    
    else:
        print("❌ Opción no válida")
        menu_principal()


if __name__ == '__main__':
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║         SCRIPT DE CARGA INICIAL DE STOCK                  ║
    ║                 GestionCloud                               ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    # MODO 1: Menú interactivo (recomendado)
    menu_principal()
    
    # MODO 2: Carga directa (descomente y configure según necesite)
    # cargar_stock_masivo(
    #     empresa_id=1,
    #     bodega_id=1,
    #     stock_default=100,
    #     sobrescribir=False
    # )
    
    # MODO 3: Carga personalizada (descomente y configure según necesite)
    # datos_stock = {
    #     'ART001': 50,
    #     'ART002': 100,
    #     'ART003': 75,
    #     'ART004': 200,
    # }
    # cargar_stock_personalizado(
    #     empresa_id=1,
    #     bodega_id=1,
    #     datos_stock=datos_stock
    # )
