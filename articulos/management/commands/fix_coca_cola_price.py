from django.core.management.base import BaseCommand
from articulos.models import Articulo
from decimal import Decimal

class Command(BaseCommand):
    help = 'Corregir precio de Coca Cola 350ml'

    def handle(self, *args, **options):
        try:
            coca = Articulo.objects.get(nombre__icontains='Coca Cola 350ml')
            
            self.stdout.write(f"\n=== COCA COLA 350ML - ESTADO ACTUAL ===")
            self.stdout.write(f"Precio Costo: {coca.precio_costo}")
            self.stdout.write(f"Precio Venta: {coca.precio_venta}")
            self.stdout.write(f"Precio Final: {coca.precio_final}")
            
            # Corregir: El precio final debería ser $1644
            # Precio Venta (neto) = $1200
            coca.precio_venta = '1200.00'
            coca.precio_final = '1644.00'
            coca.save()
            
            self.stdout.write(f"\n=== COCA COLA 350ML - CORREGIDO ===")
            self.stdout.write(f"Precio Venta: {coca.precio_venta}")
            self.stdout.write(f"Precio Final: {coca.precio_final}")
            
            self.stdout.write(self.style.SUCCESS('\n✓ Coca Cola corregida'))
            
        except Articulo.DoesNotExist:
            self.stdout.write(self.style.ERROR('Coca Cola no encontrada'))
