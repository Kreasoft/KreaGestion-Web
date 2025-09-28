from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from empresas.models import Empresa
from clientes.models import Cliente, ContactoCliente
from decimal import Decimal
import random


class Command(BaseCommand):
    help = 'Crea clientes de demostración con datos de prueba'

    def handle(self, *args, **options):
        # Obtener o crear empresa
        empresa, created = Empresa.objects.get_or_create(
            nombre='Empresa Demo',
            defaults={
                'rut': '12.345.678-9',
                'direccion': 'Av. Principal 123',
                'telefono': '+56 2 2345 6789',
                'email': 'info@empresademo.cl',
                'activa': True
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Empresa "{empresa.nombre}" creada exitosamente')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Empresa "{empresa.nombre}" ya existe')
            )

        # Obtener o crear usuario superusuario
        user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@empresademo.cl',
                'first_name': 'Administrador',
                'last_name': 'Sistema',
                'is_staff': True,
                'is_superuser': True
            }
        )
        
        if created:
            user.set_password('admin123')
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f'Usuario "{user.username}" creado exitosamente')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Usuario "{user.username}" ya existe')
            )

        # Datos de clientes de prueba
        clientes_data = [
            {
                'rut': '12.345.678-9',
                'nombre': 'Distribuidora El Sol S.A.',
                'tipo_cliente': 'contribuyente',
                'giro': 'Distribución de productos alimenticios',
                'direccion': 'Av. Libertador 1234',
                'comuna': 'Santiago',
                'ciudad': 'Santiago',
                'region': 'Metropolitana',
                'telefono': '+56 2 2345 6789',
                'email': 'ventas@elsol.cl',
                'sitio_web': 'www.elsol.cl',
                'limite_credito': Decimal('5000000.00'),
                'plazo_pago': 30,
                'descuento_porcentaje': Decimal('5.00'),
                'estado': 'activo',
                'observaciones': 'Cliente principal con excelente historial de pagos',
                'contactos': [
                    {
                        'nombre': 'María González',
                        'cargo': 'Gerente de Compras',
                        'tipo_contacto': 'comercial',
                        'telefono': '+56 2 2345 6790',
                        'celular': '+56 9 8765 4321',
                        'email': 'maria.gonzalez@elsol.cl',
                        'observaciones': 'Contacto principal para negociaciones',
                        'es_contacto_principal': True
                    },
                    {
                        'nombre': 'Carlos Rodríguez',
                        'cargo': 'Jefe de Almacén',
                        'tipo_contacto': 'logistica',
                        'telefono': '+56 2 2345 6791',
                        'celular': '+56 9 8765 4322',
                        'email': 'carlos.rodriguez@elsol.cl',
                        'observaciones': 'Contacto para temas de logística',
                        'es_contacto_principal': False
                    }
                ]
            },
            {
                'rut': '98.765.432-1',
                'nombre': 'Supermercado La Familia',
                'tipo_cliente': 'contribuyente',
                'giro': 'Comercio minorista de productos de consumo',
                'direccion': 'Calle Principal 567',
                'comuna': 'Providencia',
                'ciudad': 'Santiago',
                'region': 'Metropolitana',
                'telefono': '+56 2 3456 7890',
                'email': 'compras@lafamilia.cl',
                'sitio_web': 'www.lafamilia.cl',
                'limite_credito': Decimal('3000000.00'),
                'plazo_pago': 15,
                'descuento_porcentaje': Decimal('3.00'),
                'estado': 'activo',
                'observaciones': 'Cliente con compras regulares semanales',
                'contactos': [
                    {
                        'nombre': 'Ana Martínez',
                        'cargo': 'Encargada de Compras',
                        'tipo_contacto': 'comercial',
                        'telefono': '+56 2 3456 7891',
                        'celular': '+56 9 7654 3210',
                        'email': 'ana.martinez@lafamilia.cl',
                        'observaciones': 'Contacto principal para pedidos',
                        'es_contacto_principal': True
                    }
                ]
            },
            {
                'rut': '11.222.333-4',
                'nombre': 'Restaurante El Buen Sabor',
                'tipo_cliente': 'contribuyente',
                'giro': 'Servicios de alimentación',
                'direccion': 'Av. Costanera 890',
                'comuna': 'Las Condes',
                'ciudad': 'Santiago',
                'region': 'Metropolitana',
                'telefono': '+56 2 4567 8901',
                'email': 'pedidos@elbuensabor.cl',
                'sitio_web': 'www.elbuensabor.cl',
                'limite_credito': Decimal('1500000.00'),
                'plazo_pago': 7,
                'descuento_porcentaje': Decimal('2.00'),
                'estado': 'activo',
                'observaciones': 'Cliente con pedidos diarios de productos frescos',
                'contactos': [
                    {
                        'nombre': 'Roberto Silva',
                        'cargo': 'Chef Ejecutivo',
                        'tipo_contacto': 'comercial',
                        'telefono': '+56 2 4567 8902',
                        'celular': '+56 9 6543 2109',
                        'email': 'roberto.silva@elbuensabor.cl',
                        'observaciones': 'Contacto para pedidos especiales',
                        'es_contacto_principal': True
                    },
                    {
                        'nombre': 'Patricia López',
                        'cargo': 'Administradora',
                        'tipo_contacto': 'administrativo',
                        'telefono': '+56 2 4567 8903',
                        'celular': '+56 9 6543 2108',
                        'email': 'patricia.lopez@elbuensabor.cl',
                        'observaciones': 'Contacto para temas administrativos',
                        'es_contacto_principal': False
                    }
                ]
            },
            {
                'rut': '55.666.777-8',
                'nombre': 'Juan Pérez',
                'tipo_cliente': 'consumidor_final',
                'giro': 'Particular',
                'direccion': 'Calle Secundaria 123',
                'comuna': 'Ñuñoa',
                'ciudad': 'Santiago',
                'region': 'Metropolitana',
                'telefono': '+56 2 5678 9012',
                'email': 'juan.perez@email.com',
                'sitio_web': '',
                'limite_credito': Decimal('500000.00'),
                'plazo_pago': 0,
                'descuento_porcentaje': Decimal('0.00'),
                'estado': 'activo',
                'observaciones': 'Cliente particular con compras ocasionales',
                'contactos': [
                    {
                        'nombre': 'Juan Pérez',
                        'cargo': 'Propietario',
                        'tipo_contacto': 'comercial',
                        'telefono': '+56 2 5678 9012',
                        'celular': '+56 9 5432 1098',
                        'email': 'juan.perez@email.com',
                        'observaciones': 'Contacto único',
                        'es_contacto_principal': True
                    }
                ]
            },
            {
                'rut': '99.888.777-6',
                'nombre': 'Cafetería Central',
                'tipo_cliente': 'contribuyente',
                'giro': 'Servicios de alimentación y bebidas',
                'direccion': 'Plaza Central 456',
                'comuna': 'Santiago Centro',
                'ciudad': 'Santiago',
                'region': 'Metropolitana',
                'telefono': '+56 2 6789 0123',
                'email': 'info@cafeteriacentral.cl',
                'sitio_web': 'www.cafeteriacentral.cl',
                'limite_credito': Decimal('800000.00'),
                'plazo_pago': 14,
                'descuento_porcentaje': Decimal('1.50'),
                'estado': 'activo',
                'observaciones': 'Cliente con pedidos regulares de café y pastelería',
                'contactos': [
                    {
                        'nombre': 'Isabel Fernández',
                        'cargo': 'Gerente General',
                        'tipo_contacto': 'comercial',
                        'telefono': '+56 2 6789 0124',
                        'celular': '+56 9 4321 0987',
                        'email': 'isabel.fernandez@cafeteriacentral.cl',
                        'observaciones': 'Contacto principal para todas las operaciones',
                        'es_contacto_principal': True
                    }
                ]
            },
            {
                'rut': '33.444.555-2',
                'nombre': 'Panadería El Horno',
                'tipo_cliente': 'contribuyente',
                'giro': 'Elaboración y venta de productos de panadería',
                'direccion': 'Av. Industrial 789',
                'comuna': 'Maipú',
                'ciudad': 'Santiago',
                'region': 'Metropolitana',
                'telefono': '+56 2 7890 1234',
                'email': 'ventas@elhorno.cl',
                'sitio_web': 'www.elhorno.cl',
                'limite_credito': Decimal('2000000.00'),
                'plazo_pago': 21,
                'descuento_porcentaje': Decimal('4.00'),
                'estado': 'activo',
                'observaciones': 'Cliente con pedidos grandes de harina y ingredientes',
                'contactos': [
                    {
                        'nombre': 'Miguel Torres',
                        'cargo': 'Propietario',
                        'tipo_contacto': 'comercial',
                        'telefono': '+56 2 7890 1235',
                        'celular': '+56 9 3210 9876',
                        'email': 'miguel.torres@elhorno.cl',
                        'observaciones': 'Contacto principal para pedidos',
                        'es_contacto_principal': True
                    },
                    {
                        'nombre': 'Carmen Vega',
                        'cargo': 'Encargada de Producción',
                        'tipo_contacto': 'produccion',
                        'telefono': '+56 2 7890 1236',
                        'celular': '+56 9 3210 9875',
                        'email': 'carmen.vega@elhorno.cl',
                        'observaciones': 'Contacto para temas de producción',
                        'es_contacto_principal': False
                    }
                ]
            }
        ]

        # Crear clientes
        clientes_creados = 0
        for cliente_data in clientes_data:
            contactos_data = cliente_data.pop('contactos', [])
            
            cliente, created = Cliente.objects.get_or_create(
                rut=cliente_data['rut'],
                empresa=empresa,
                defaults={
                    **cliente_data,
                    'creado_por': user
                }
            )
            
            if created:
                clientes_creados += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Cliente "{cliente.nombre}" creado exitosamente')
                )
                
                # Crear contactos
                for contacto_data in contactos_data:
                    ContactoCliente.objects.create(
                        cliente=cliente,
                        **contacto_data
                    )
                
                self.stdout.write(
                    self.style.SUCCESS(f'  - {len(contactos_data)} contacto(s) agregado(s)')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Cliente "{cliente.nombre}" ya existe')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Proceso completado: {clientes_creados} cliente(s) creado(s) exitosamente'
            )
        )
