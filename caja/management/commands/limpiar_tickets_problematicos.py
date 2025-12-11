from django.core.management.base import BaseCommand
from django.db import transaction
from caja.models import VentaProcesada, MovimientoCaja
from ventas.models import Venta


class Command(BaseCommand):
    help = 'Limpia tickets problemáticos (vales con procesamiento incompleto)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa-id',
            type=int,
            help='ID de la empresa (opcional, si no se especifica limpia todas)',
        )
        parser.add_argument(
            '--ejecutar',
            action='store_true',
            help='Ejecutar la limpieza (sin este flag solo muestra lo que haría)',
        )
    
    def handle(self, *args, **options):
        empresa_id = options.get('empresa_id')
        ejecutar = options.get('ejecutar', False)
        
        if not ejecutar:
            self.stdout.write(self.style.WARNING('MODO SIMULACIÓN - No se harán cambios'))
            self.stdout.write(self.style.WARNING('Usa --ejecutar para aplicar los cambios\n'))
        
        with transaction.atomic():
            # 1. Buscar VentaProcesada sin DTE generado (procesamiento incompleto)
            ventas_procesadas_sin_dte = VentaProcesada.objects.filter(dte_generado__isnull=True)
            if empresa_id:
                ventas_procesadas_sin_dte = ventas_procesadas_sin_dte.filter(
                    venta_preventa__empresa_id=empresa_id
                )
            
            self.stdout.write(f'\n1. VentaProcesada sin DTE (procesamiento incompleto):')
            self.stdout.write(f'   Encontrados: {ventas_procesadas_sin_dte.count()}')
            
            if ventas_procesadas_sin_dte.exists():
                for vp in ventas_procesadas_sin_dte:
                    ticket = vp.venta_preventa
                    venta_final = vp.venta_final
                    self.stdout.write(f'   - Ticket #{ticket.numero_venta} (ID: {ticket.id})')
                    self.stdout.write(f'     Venta final: #{venta_final.numero_venta if venta_final else "N/A"}')
                    
                    if ejecutar:
                        # Eliminar movimientos de caja asociados
                        MovimientoCaja.objects.filter(venta=venta_final).delete()
                        # Eliminar la venta final si existe
                        if venta_final:
                            venta_final.delete()
                        # Eliminar el registro de venta procesada
                        vp.delete()
                        # Marcar el ticket como no facturado para poder reprocesarlo
                        ticket.facturado = False
                        ticket.save()
                        self.stdout.write(self.style.SUCCESS(f'     ✓ Limpiado'))
            
            # 2. Buscar vales marcados como facturados pero sin VentaProcesada
            vales_facturados_sin_procesada = Venta.objects.filter(
                tipo_documento='vale',
                facturado=True
            )
            if empresa_id:
                vales_facturados_sin_procesada = vales_facturados_sin_procesada.filter(
                    empresa_id=empresa_id
                )
            
            # Filtrar solo los que NO tienen VentaProcesada
            vales_huerfanos = []
            for vale in vales_facturados_sin_procesada:
                if not VentaProcesada.objects.filter(venta_preventa=vale).exists():
                    vales_huerfanos.append(vale)
            
            self.stdout.write(f'\n2. Vales marcados como facturados sin VentaProcesada:')
            self.stdout.write(f'   Encontrados: {len(vales_huerfanos)}')
            
            if vales_huerfanos:
                for vale in vales_huerfanos:
                    self.stdout.write(f'   - Ticket #{vale.numero_venta} (ID: {vale.id})')
                    
                    if ejecutar:
                        # Marcar como no facturado para poder reprocesarlo
                        vale.facturado = False
                        vale.save()
                        self.stdout.write(self.style.SUCCESS(f'     ✓ Desmarcado como facturado'))
            
            # 3. Resumen
            self.stdout.write(f'\n{"="*60}')
            self.stdout.write(self.style.WARNING('RESUMEN:'))
            total_afectados = ventas_procesadas_sin_dte.count() + len(vales_huerfanos)
            self.stdout.write(f'Total de tickets afectados: {total_afectados}')
            
            if ejecutar:
                self.stdout.write(self.style.SUCCESS('\n✓ Limpieza completada exitosamente'))
                self.stdout.write('Los tickets problemáticos han sido limpiados y están listos para reprocesar.')
            else:
                self.stdout.write(self.style.WARNING('\nEsto es una SIMULACIÓN'))
                self.stdout.write('Para ejecutar la limpieza, usa: --ejecutar')
            
            if not ejecutar:
                # Si es simulación, hacer rollback
                transaction.set_rollback(True)
