from django.core.management.base import BaseCommand
from articulos.models import Articulo
from empresas.models import Sucursal
from articulos.models import StockArticulo
from decimal import Decimal

class Command(BaseCommand):
    help = 'Crear stock inicial para todos los artículos'

    def handle(self, *args, **options):
        # Obtener todas las empresas
        from empresas.models import Empresa
        empresas = Empresa.objects.all()
        
        for empresa in empresas:
            self.stdout.write(f'Procesando empresa: {empresa.nombre}')
            
            # Obtener o crear sucursal principal
            from datetime import time
            sucursal, created = Sucursal.objects.get_or_create(
                empresa=empresa,
                nombre='Sucursal Principal',
                defaults={
                    'codigo': 'PRINCIPAL',
                    'direccion': 'Dirección Principal',
                    'comuna': 'Santiago',
                    'ciudad': 'Santiago',
                    'region': 'Metropolitana',
                    'telefono': '123456789',
                    'email': f'principal@{empresa.nombre.lower().replace(" ", "")}.com',
                    'es_principal': True,
                    'horario_apertura': time(9, 0),  # 9:00 AM
                    'horario_cierre': time(18, 0),   # 6:00 PM
                    'estado': 'activa'
                }
            )
            
            if created:
                self.stdout.write(f'  Creada sucursal: {sucursal.nombre}')
            
            # Obtener todos los artículos de la empresa
            articulos = Articulo.objects.filter(empresa=empresa, activo=True)
            
            for articulo in articulos:
                # Crear stock inicial de 100 unidades
                stock_obj, created = StockArticulo.objects.get_or_create(
                    articulo=articulo,
                    sucursal=sucursal,
                    defaults={
                        'cantidad_disponible': Decimal('100.00')
                    }
                )
                
                if created:
                    self.stdout.write(f'  Creado stock para: {articulo.nombre} - 100 unidades')
                else:
                    self.stdout.write(f'  Stock ya existe para: {articulo.nombre}')
        
        self.stdout.write(self.style.SUCCESS('Stock inicial creado exitosamente'))
