from django.core.management.base import BaseCommand
from articulos.models import CategoriaArticulo, UnidadMedida, Articulo, ImpuestoEspecifico
from empresas.models import Empresa
from decimal import Decimal

class Command(BaseCommand):
    help = 'Crea datos de ejemplo para el sistema'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Creando datos de ejemplo...'))
        
        # Obtener o crear empresa
        empresa, created = Empresa.objects.get_or_create(
            nombre='Empresa Demo',
            defaults={
                'rut': '12345678-9',
                'direccion': 'Dirección Demo',
                'telefono': '+56 9 1234 5678',
                'email': 'demo@empresa.com',
                'activa': True
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Empresa "{empresa.nombre}" creada'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Empresa "{empresa.nombre}" ya existe'))
        
        # Crear impuestos específicos más usados en Chile
        impuestos_data = [
            # Bebidas alcohólicas
            {'nombre': 'Vino, Cerveza y Sidra', 'descripcion': 'Impuesto específico a vino, cerveza y sidra', 'porcentaje': '20.50'},
            {'nombre': 'Licores y Destilados', 'descripcion': 'Impuesto específico a licores y destilados', 'porcentaje': '31.50'},
            
            # Bebidas analcohólicas
            {'nombre': 'Bebidas Alto Azúcar', 'descripcion': 'Bebidas con más de 15 grs. de azúcar por 240 ml', 'porcentaje': '18.00'},
            {'nombre': 'Bebidas Bajo Azúcar', 'descripcion': 'Bebidas con bajo contenido de azúcar', 'porcentaje': '10.00'},
            
            # Otros impuestos comunes
            {'nombre': 'Impuesto Verde', 'descripcion': 'Impuesto a productos contaminantes', 'porcentaje': '5.00'},
            {'nombre': 'Impuesto al Tabaco', 'descripcion': 'Impuesto específico a productos de tabaco', 'porcentaje': '15.00'},
        ]
        
        for imp_data in impuestos_data:
            impuesto, created = ImpuestoEspecifico.objects.get_or_create(
                nombre=imp_data['nombre'],
                empresa=empresa,
                defaults={
                    'descripcion': imp_data['descripcion'],
                    'porcentaje': imp_data['porcentaje'],
                    'activa': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Impuesto "{impuesto.nombre}" creado'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Impuesto "{impuesto.nombre}" ya existe'))
        
        # Crear categorías con impuestos específicos
        categorias_data = [
            # Bebidas alcohólicas
            {'nombre': 'Vinos', 'descripcion': 'Vinos y espumantes', 'impuesto': 'Vino, Cerveza y Sidra'},
            {'nombre': 'Cervezas', 'descripcion': 'Cervezas y sidras', 'impuesto': 'Vino, Cerveza y Sidra'},
            {'nombre': 'Licores', 'descripcion': 'Licores y destilados', 'impuesto': 'Licores y Destilados'},
            
            # Bebidas analcohólicas
            {'nombre': 'Gaseosas', 'descripcion': 'Bebidas gaseosas y refrescos', 'impuesto': 'Bebidas Alto Azúcar'},
            {'nombre': 'Jugos', 'descripcion': 'Jugos y néctares', 'impuesto': 'Bebidas Alto Azúcar'},
            {'nombre': 'Bebidas Energéticas', 'descripcion': 'Bebidas energéticas y isotónicas', 'impuesto': 'Bebidas Alto Azúcar'},
            {'nombre': 'Aguas Saborizadas', 'descripcion': 'Aguas saborizadas y vitaminadas', 'impuesto': 'Bebidas Bajo Azúcar'},
            {'nombre': 'Aguas Naturales', 'descripcion': 'Aguas minerales y naturales', 'impuesto': None},
            
            # Otras categorías
            {'nombre': 'Electrónicos', 'descripcion': 'Dispositivos electrónicos', 'impuesto': 'Impuesto Verde'},
            {'nombre': 'Tabaco', 'descripcion': 'Productos de tabaco', 'impuesto': 'Impuesto al Tabaco'},
            {'nombre': 'Libros', 'descripcion': 'Libros y publicaciones', 'impuesto': None},
            {'nombre': 'Ropa', 'descripcion': 'Vestimenta y accesorios', 'impuesto': None},
            {'nombre': 'Hogar', 'descripcion': 'Artículos para el hogar', 'impuesto': None},
        ]
        
        for cat_data in categorias_data:
            impuesto_especifico = None
            if cat_data['impuesto']:
                impuesto_especifico = ImpuestoEspecifico.objects.get(nombre=cat_data['impuesto'], empresa=empresa)
            
            categoria, created = CategoriaArticulo.objects.get_or_create(
                nombre=cat_data['nombre'],
                empresa=empresa,
                defaults={
                    'descripcion': cat_data['descripcion'],
                    'impuesto_especifico': impuesto_especifico,
                    'activa': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Categoría "{categoria.nombre}" creada'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Categoría "{categoria.nombre}" ya existe'))
        
        # Crear unidades de medida
        unidades_data = [
            {'nombre': 'Unidad', 'simbolo': 'u'},
            {'nombre': 'Kilogramo', 'simbolo': 'kg'},
            {'nombre': 'Litro', 'simbolo': 'L'},
            {'nombre': 'Metro', 'simbolo': 'm'},
        ]
        
        for uni_data in unidades_data:
            unidad, created = UnidadMedida.objects.get_or_create(
                nombre=uni_data['nombre'],
                empresa=empresa,
                defaults={
                    'simbolo': uni_data['simbolo'],
                    'activa': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Unidad "{unidad.nombre}" creada'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Unidad "{unidad.nombre}" ya existe'))
        
        # Crear artículos de ejemplo con impuestos específicos
        articulos_data = [
            # Bebidas alcohólicas
            {
                'codigo': 'VIN001',
                'nombre': 'Vino Tinto Reserva',
                'descripcion': 'Vino tinto reserva 750ml',
                'precio_costo': '8000',
                'precio_venta': '15000',
                'margen_porcentaje': '87.50',
                'categoria': 'Vinos',
                'unidad': 'Unidad'
            },
            {
                'codigo': 'CER001',
                'nombre': 'Cerveza Lager 330ml',
                'descripcion': 'Cerveza lager 330ml lata',
                'precio_costo': '1200',
                'precio_venta': '2500',
                'margen_porcentaje': '108.33',
                'categoria': 'Cervezas',
                'unidad': 'Unidad'
            },
            {
                'codigo': 'LIC001',
                'nombre': 'Whisky Premium',
                'descripcion': 'Whisky premium 750ml',
                'precio_costo': '25000',
                'precio_venta': '45000',
                'margen_porcentaje': '80.00',
                'categoria': 'Licores',
                'unidad': 'Unidad'
            },
            
            # Bebidas analcohólicas
            {
                'codigo': 'GAS001',
                'nombre': 'Coca-Cola 500ml',
                'descripcion': 'Bebida gaseosa 500ml',
                'precio_costo': '800',
                'precio_venta': '1500',
                'margen_porcentaje': '87.50',
                'categoria': 'Gaseosas',
                'unidad': 'Unidad'
            },
            {
                'codigo': 'JUG001',
                'nombre': 'Jugo de Naranja 1L',
                'descripcion': 'Jugo de naranja 100% natural 1L',
                'precio_costo': '1200',
                'precio_venta': '2200',
                'margen_porcentaje': '83.33',
                'categoria': 'Jugos',
                'unidad': 'Unidad'
            },
            {
                'codigo': 'ENE001',
                'nombre': 'Red Bull 250ml',
                'descripcion': 'Bebida energética 250ml',
                'precio_costo': '1500',
                'precio_venta': '2800',
                'margen_porcentaje': '86.67',
                'categoria': 'Bebidas Energéticas',
                'unidad': 'Unidad'
            },
            {
                'codigo': 'AGU001',
                'nombre': 'Agua Mineral 500ml',
                'descripcion': 'Agua mineral natural 500ml',
                'precio_costo': '400',
                'precio_venta': '800',
                'margen_porcentaje': '100.00',
                'categoria': 'Aguas Naturales',
                'unidad': 'Unidad'
            },
            
            # Otros productos
            {
                'codigo': 'ELE001',
                'nombre': 'Smartphone Samsung Galaxy',
                'descripcion': 'Teléfono inteligente de última generación',
                'precio_costo': '200000',
                'precio_venta': '350000',
                'margen_porcentaje': '75.00',
                'categoria': 'Electrónicos',
                'unidad': 'Unidad'
            },
            {
                'codigo': 'TAB001',
                'nombre': 'Cigarrillos Premium',
                'descripcion': 'Cigarrillos premium 20 unidades',
                'precio_costo': '3000',
                'precio_venta': '5500',
                'margen_porcentaje': '83.33',
                'categoria': 'Tabaco',
                'unidad': 'Unidad'
            }
        ]
        
        for art_data in articulos_data:
            categoria = CategoriaArticulo.objects.get(nombre=art_data['categoria'], empresa=empresa)
            unidad = UnidadMedida.objects.get(nombre=art_data['unidad'], empresa=empresa)
            
            articulo, created = Articulo.objects.get_or_create(
                codigo=art_data['codigo'],
                defaults={
                    'empresa': empresa,
                    'categoria': categoria,
                    'unidad_medida': unidad,
                    'nombre': art_data['nombre'],
                    'descripcion': art_data['descripcion'],
                    'precio_costo': art_data['precio_costo'],
                    'precio_venta': art_data['precio_venta'],
                    'margen_porcentaje': art_data['margen_porcentaje'],
                    'control_stock': True,
                    'stock_minimo': '10',
                    'stock_maximo': '100',
                    'activo': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Artículo "{articulo.nombre}" creado'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Artículo "{articulo.nombre}" ya existe'))
        
        self.stdout.write(self.style.SUCCESS('¡Datos de ejemplo creados exitosamente!'))
