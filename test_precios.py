"""
Script de prueba para verificar que los precios se están guardando correctamente
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from articulos.models import ListaPrecio, PrecioArticulo, Articulo

# Obtener la primera lista de precios
lista = ListaPrecio.objects.first()
if lista:
    print(f"\n=== Lista de Precios: {lista.nombre} ===")
    print(f"ID: {lista.id}")
    print(f"Empresa: {lista.empresa.nombre}")
    
    # Obtener precios de esta lista
    precios = PrecioArticulo.objects.filter(lista_precio=lista).select_related('articulo')
    print(f"\nTotal de precios en esta lista: {precios.count()}")
    
    if precios.exists():
        print("\nPrecios guardados:")
        for precio in precios[:10]:  # Mostrar solo los primeros 10
            print(f"  - {precio.articulo.codigo} | {precio.articulo.nombre}: ${precio.precio}")
    else:
        print("\n⚠️ No hay precios guardados en esta lista")
        
    # Verificar artículos activos
    articulos_activos = Articulo.objects.filter(empresa=lista.empresa, activo=True).count()
    print(f"\nTotal de artículos activos en la empresa: {articulos_activos}")
else:
    print("⚠️ No hay listas de precios en la base de datos")
