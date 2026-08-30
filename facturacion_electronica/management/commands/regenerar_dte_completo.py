"""
Comando para regenerar DTEs completos (XML, firma, TED y timbre)
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dte_generator import DTEXMLGenerator
from facturacion_electronica.firma_electronica import FirmadorDTE
from facturacion_electronica.pdf417_generator import PDF417Generator
from decimal import Decimal


class Command(BaseCommand):
    help = 'Regenera DTEs completos (XML, firma, TED y timbre PDF417)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--folio',
            type=int,
            help='Regenerar solo un folio específico',
        )
        parser.add_argument(
            '--tipo',
            type=str,
            help='Regenerar solo un tipo de DTE específico (33, 39, 52, etc.)',
        )

    def handle(self, *args, **options):
        # Filtrar DTEs
        dtes = DocumentoTributarioElectronico.objects.select_related('empresa', 'caf_utilizado').all()
        
        if options['tipo']:
            dtes = dtes.filter(tipo_dte=options['tipo'])
            self.stdout.write(f"Filtrando por tipo DTE: {options['tipo']}")
        
        if options['folio']:
            dtes = dtes.filter(folio=options['folio'])
            self.stdout.write(f"Filtrando por folio: {options['folio']}")
        
        total = dtes.count()
        self.stdout.write(f"\nTotal de DTEs a procesar: {total}\n")
        
        if total == 0:
            self.stdout.write(self.style.WARNING('No hay DTEs para procesar.'))
            return
        
        exitosos = 0
        errores = 0
        
        for dte in dtes:
            try:
                with transaction.atomic():
                    empresa = dte.empresa
                    caf = dte.caf_utilizado
                    
                    self.stdout.write(f'\n🔄 Procesando DTE {dte.tipo_dte} N° {dte.folio}...')
                    
                    
                    # Usar el servicio centralizado para regenerar todo con la nueva lógica
                    from facturacion_electronica.dte_service import DTEService
                    
                    service = DTEService(empresa)
                    service.procesar_dte_existente(dte)
                    
                    exitosos += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ DTE {dte.tipo_dte} N° {dte.folio} - Regenerado completamente con DTEService'
                        )
                    )
                    
                    # Saltamos el resto de la lógica manual ya que procesar_dte_existente hace todo
                    continue
                    
            except Exception as e:
                errores += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ DTE {dte.tipo_dte} N° {dte.folio} - Error: {str(e)}'
                    )
                )
                import traceback
                traceback.print_exc()
        
        # Resumen
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'\n✅ Exitosos: {exitosos}'))
        if errores > 0:
            self.stdout.write(self.style.ERROR(f'❌ Errores: {errores}'))
        self.stdout.write(f'📊 Total procesados: {exitosos + errores}/{total}\n')
