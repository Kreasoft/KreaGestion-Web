"""
Comando para verificar y actualizar automáticamente la vigencia de los CAF
Los CAF tienen una vigencia de 6 meses desde la fecha de autorización
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from facturacion_electronica.models import ArchivoCAF


class Command(BaseCommand):
    help = 'Verifica y actualiza la vigencia de los archivos CAF (vencen a los 6 meses)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa',
            type=int,
            help='ID de empresa específica para verificar (opcional)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('VERIFICACIÓN DE VIGENCIA DE CAF'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Filtrar por empresa si se especifica
        filtro = {}
        if options['empresa']:
            filtro['empresa_id'] = options['empresa']
            empresa = ArchivoCAF.objects.filter(id=options['empresa']).first()
            self.stdout.write(f"\nVerificando CAFs de: {empresa.empresa.nombre if empresa else 'Empresa no encontrada'}")
        
        # Obtener todos los CAFs activos
        cafs_activos = ArchivoCAF.objects.filter(estado='activo', **filtro)
        total_activos = cafs_activos.count()
        
        self.stdout.write(f"\nTotal de CAFs activos: {total_activos}")
        
        if total_activos == 0:
            self.stdout.write(self.style.WARNING('\nNo hay CAFs activos para verificar'))
            return
        
        vencidos = 0
        por_vencer_30 = 0
        por_vencer_60 = 0
        vigentes = 0
        
        self.stdout.write("\n" + "=" * 70)
        
        for caf in cafs_activos:
            dias_restantes = caf.dias_para_vencer()
            fecha_venc = caf.fecha_vencimiento()
            
            # Verificar si está vencido
            if not caf.esta_vigente():
                caf.estado = 'vencido'
                caf.save()
                vencidos += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'\nVENCIDO: {caf.get_tipo_documento_display()} '
                        f'(Folios {caf.folio_desde}-{caf.folio_hasta})'
                    )
                )
                self.stdout.write(f'   Empresa: {caf.empresa.nombre}')
                self.stdout.write(f'   Autorizado: {caf.fecha_autorizacion}')
                self.stdout.write(f'   Vencio: {fecha_venc}')
                self.stdout.write(f'   Estado actualizado a: VENCIDO')
            
            # Alertas por vencimiento próximo
            elif dias_restantes <= 30:
                por_vencer_30 += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'\nCRITICO (<=30 dias): {caf.get_tipo_documento_display()} '
                        f'(Folios {caf.folio_desde}-{caf.folio_hasta})'
                    )
                )
                self.stdout.write(f'   Empresa: {caf.empresa.nombre}')
                self.stdout.write(f'   Dias restantes: {dias_restantes}')
                self.stdout.write(f'   Vence: {fecha_venc}')
                self.stdout.write(self.style.WARNING('   ACCION REQUERIDA: Solicitar nuevo CAF al SII'))
            
            elif dias_restantes <= 60:
                por_vencer_60 += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'\nADVERTENCIA (<=60 dias): {caf.get_tipo_documento_display()} '
                        f'(Folios {caf.folio_desde}-{caf.folio_hasta})'
                    )
                )
                self.stdout.write(f'   Empresa: {caf.empresa.nombre}')
                self.stdout.write(f'   Dias restantes: {dias_restantes}')
                self.stdout.write(f'   Vence: {fecha_venc}')
            
            else:
                vigentes += 1
        
        # Resumen
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS('\nRESUMEN:'))
        self.stdout.write("=" * 70)
        self.stdout.write(f'\nOK Vigentes (>60 dias): {vigentes}')
        self.stdout.write(f'ATENCION Por vencer (30-60 dias): {por_vencer_60}')
        self.stdout.write(f'CRITICO Por vencer (<=30 dias): {por_vencer_30}')
        self.stdout.write(f'VENCIDO Marcados como vencidos: {vencidos}')
        
        if vencidos > 0:
            self.stdout.write(
                self.style.ERROR(
                    f'\nATENCION! Se encontraron {vencidos} CAF(s) vencido(s) '
                    f'y fueron marcados como "vencido"'
                )
            )
        
        if por_vencer_30 > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'\nURGENTE! Hay {por_vencer_30} CAF(s) que vencen en menos de 30 dias'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    'Se recomienda solicitar nuevos CAF al SII INMEDIATAMENTE'
                )
            )
        
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS('\nOK Verificacion completada\n'))

