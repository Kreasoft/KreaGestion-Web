"""
Comando para limpiar datos antes de la migración multi-sucursal
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Limpia datos para facilitar la migración a sistema multi-sucursal'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirmar la eliminación de datos',
        )

    def handle(self, *args, **options):
        if not options['confirmar']:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  ADVERTENCIA: Este comando eliminará los siguientes datos:\n'
                '   - Todas las ventas\n'
                '   - Todos los detalles de ventas\n'
                '   - Todos los movimientos de cuenta corriente\n'
                '   - Todos los movimientos de caja\n'
                '\n'
                '   Las empresas, sucursales, clientes, productos y usuarios NO se eliminarán.\n'
                '\n'
                '   Para confirmar, ejecuta: python manage.py limpiar_datos_migracion --confirmar\n'
            ))
            return

        self.stdout.write(self.style.WARNING('\n🔄 Iniciando limpieza de datos...\n'))

        try:
            with transaction.atomic():
                # Importar modelos
                from ventas.models import Venta, VentaDetalle
                from tesoreria.models import MovimientoCuentaCorrienteCliente
                from caja.models import MovimientoCaja, AperturaCaja
                
                # Contar registros antes
                ventas_count = Venta.objects.count()
                detalles_count = VentaDetalle.objects.count()
                movimientos_cc_count = MovimientoCuentaCorrienteCliente.objects.count()
                movimientos_caja_count = MovimientoCaja.objects.count()
                aperturas_count = AperturaCaja.objects.count()
                
                self.stdout.write(f'📊 Registros encontrados:')
                self.stdout.write(f'   - Ventas: {ventas_count}')
                self.stdout.write(f'   - Detalles de ventas: {detalles_count}')
                self.stdout.write(f'   - Movimientos cuenta corriente: {movimientos_cc_count}')
                self.stdout.write(f'   - Movimientos de caja: {movimientos_caja_count}')
                self.stdout.write(f'   - Aperturas de caja: {aperturas_count}')
                
                # Eliminar datos
                self.stdout.write('\n🗑️  Eliminando datos...')
                
                VentaDetalle.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'   ✓ {detalles_count} detalles de ventas eliminados'))
                
                Venta.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'   ✓ {ventas_count} ventas eliminadas'))
                
                MovimientoCuentaCorrienteCliente.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'   ✓ {movimientos_cc_count} movimientos de cuenta corriente eliminados'))
                
                MovimientoCaja.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'   ✓ {movimientos_caja_count} movimientos de caja eliminados'))
                
                AperturaCaja.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'   ✓ {aperturas_count} aperturas de caja eliminadas'))
                
                self.stdout.write(self.style.SUCCESS('\n✅ Limpieza completada exitosamente!'))
                self.stdout.write(self.style.SUCCESS('   Ahora puedes ejecutar: python manage.py makemigrations'))
                self.stdout.write(self.style.SUCCESS('   Luego: python manage.py migrate\n'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error durante la limpieza: {str(e)}\n'))
            raise
