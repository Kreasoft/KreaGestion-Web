"""
Comando para regenerar timbres PDF417 de DTEs existentes
"""
from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.pdf417_generator import PDF417Generator


class Command(BaseCommand):
    help = 'Regenera los timbres PDF417 de los DTEs que no los tienen'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Regenerar todos los timbres, incluso los que ya existen',
        )
        parser.add_argument(
            '--tipo',
            type=str,
            help='Regenerar solo un tipo de DTE específico (33, 39, 52, etc.)',
        )

    def handle(self, *args, **options):
        # Filtrar DTEs
        dtes = DocumentoTributarioElectronico.objects.all()
        
        if options['tipo']:
            dtes = dtes.filter(tipo_dte=options['tipo'])
            self.stdout.write(f"Filtrando por tipo DTE: {options['tipo']}")
        
        if not options['all']:
            # Solo los que no tienen timbre
            dtes = dtes.filter(timbre_pdf417='')
            self.stdout.write("Procesando solo DTEs sin timbre...")
        else:
            self.stdout.write("Procesando TODOS los DTEs...")
        
        total = dtes.count()
        self.stdout.write(f"\nTotal de DTEs a procesar: {total}\n")
        
        if total == 0:
            self.stdout.write(self.style.WARNING('No hay DTEs para procesar.'))
            return
        
        exitosos = 0
        errores = 0
        
        for dte in dtes:
            try:
                # Verificar que tenga datos_pdf417
                if not dte.datos_pdf417:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠️  DTE {dte.tipo_dte} N° {dte.folio} - Sin datos PDF417, saltando...'
                        )
                    )
                    continue
                
                # Generar imagen PDF417
                PDF417Generator.guardar_pdf417_en_dte(dte)
                
                exitosos += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ DTE {dte.tipo_dte} N° {dte.folio} - Timbre regenerado'
                    )
                )
                
            except Exception as e:
                errores += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ DTE {dte.tipo_dte} N° {dte.folio} - Error: {str(e)}'
                    )
                )
        
        # Resumen
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'\n✅ Exitosos: {exitosos}'))
        if errores > 0:
            self.stdout.write(self.style.ERROR(f'❌ Errores: {errores}'))
        self.stdout.write(f'📊 Total procesados: {exitosos + errores}/{total}\n')
