"""
Comando simple para generar DTE de prueba
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from ventas.models import Venta, Cliente, Vendedor
from articulos.models import Articulo
from facturacion_electronica.dte_service import DTEService
from decimal import Decimal
import random


class Command(BaseCommand):
    help = 'Genera DTE de prueba reutilizando folios'

    def handle(self, *args, **options):
        self.stdout.write('Generando DTE de prueba...')

        try:
            # Obtener empresa
            from empresas.models import Empresa
            empresa = Empresa.objects.filter(facturacion_electronica=True).first()
            if not empresa:
                self.stdout.write(self.style.ERROR('No hay empresa con facturacion electronica'))
                return

            # Verificar modo prueba
            if not empresa.modo_reutilizacion_folios:
                self.stdout.write(self.style.ERROR('Modo prueba no habilitado'))
                self.stdout.write(self.style.ERROR('Use: python manage.py configurar_modo_prueba --habilitar'))
                return

            # Crear datos basicos
            cliente = Cliente.objects.first()
            if not cliente:
                cliente = Cliente.objects.create(
                    nombre='Cliente Prueba',
                    rut='66666666-6'
                )

            vendedor = Vendedor.objects.first()
            if not vendedor:
                vendedor = Vendedor.objects.create(
                    nombre='Vendedor Prueba',
                    rut='11111111-1'
                )

            articulo = Articulo.objects.first()
            if not articulo:
                articulo = Articulo.objects.create(
                    nombre='Articulo Prueba',
                    precio=10000,
                    stock=100
                )

            usuario = User.objects.filter(is_superuser=True).first()
            if not usuario:
                self.stdout.write(self.style.ERROR('No hay usuario administrador'))
                return

            # Crear venta
            numero_venta = f'PRUEBA-{random.randint(1000, 9999)}'
            venta = Venta.objects.create(
                empresa=empresa,
                cliente=cliente,
                vendedor=vendedor,
                usuario_creacion=usuario,
                numero_venta=numero_venta,
                subtotal=Decimal('10000'),
                iva=Decimal('1900'),
                total=Decimal('11900'),
                estado='confirmada'
            )

            # Agregar detalle
            from ventas.models import VentaDetalle
            VentaDetalle.objects.create(
                venta=venta,
                articulo=articulo,
                cantidad=Decimal('1'),
                precio_unitario=Decimal('10000'),
                precio_total=Decimal('10000')
            )

            # Generar DTE
            dte_service = DTEService(empresa)
            dte = dte_service.generar_dte_desde_venta(venta, '33')

            if dte:
                self.stdout.write(self.style.SUCCESS(f'DTE generado - Tipo: 33, Folio: {dte.folio}'))
                self.stdout.write('Puede generar mas documentos con el mismo folio')
            else:
                self.stdout.write(self.style.ERROR('Error generando DTE'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))

