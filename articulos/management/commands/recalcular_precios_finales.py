from django.core.management.base import BaseCommand
from articulos.models import Articulo
from decimal import Decimal

class Command(BaseCommand):
    help = 'Recalcular precios finales de artículos con impuesto específico'

    def handle(self, *args, **options):
        # Buscar artículos con categoría que tenga impuesto específico
        articulos = Articulo.objects.filter(
            categoria__impuesto_especifico__isnull=False
        ).select_related('categoria', 'categoria__impuesto_especifico')
        
        self.stdout.write(f"\nEncontrados {articulos.count()} artículos con impuesto específico\n")
        
        actualizados = 0
        
        for articulo in articulos:
            precio_venta = Decimal(str(articulo.precio_venta).replace(',', '.'))
            precio_final_anterior = Decimal(str(articulo.precio_final).replace(',', '.'))
            
            # Recalcular precio final
            precio_final_nuevo = articulo.calcular_precio_final()
            
            # Verificar si cambió
            if abs(precio_final_anterior - precio_final_nuevo) > Decimal('0.01'):
                self.stdout.write(f"\n--- {articulo.nombre} ---")
                self.stdout.write(f"Precio Venta: ${precio_venta}")
                self.stdout.write(f"Precio Final ANTES: ${precio_final_anterior}")
                self.stdout.write(f"Precio Final DESPUÉS: ${precio_final_nuevo}")
                
                # Guardar
                articulo.save()
                actualizados += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ {actualizados} artículos actualizados'))
