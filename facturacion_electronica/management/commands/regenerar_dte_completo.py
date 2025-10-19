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
                    
                    # Verificar certificado
                    if not empresa.certificado_digital:
                        self.stdout.write(
                            self.style.WARNING(
                                f'⚠️  Empresa sin certificado digital, saltando...'
                            )
                        )
                        continue
                    
                    # 1. Generar TED
                    firmador = FirmadorDTE(
                        empresa.certificado_digital.path,
                        empresa.password_certificado
                    )
                    
                    dte_data = {
                        'rut_emisor': dte.rut_emisor or empresa.rut,
                        'tipo_dte': dte.tipo_dte,
                        'folio': dte.folio,
                        'fecha_emision': dte.fecha_emision.strftime('%Y-%m-%d'),
                        'rut_receptor': dte.rut_receptor,
                        'razon_social_receptor': dte.razon_social_receptor,
                        'monto_total': dte.monto_total,
                        'item_1': f'Documento Tributario Electrónico',
                    }
                    
                    caf_data = {
                        'rut_emisor': empresa.rut,
                        'razon_social': empresa.razon_social_sii or empresa.razon_social,
                        'tipo_documento': dte.tipo_dte,
                        'folio_desde': caf.folio_desde,
                        'folio_hasta': caf.folio_hasta,
                        'fecha_autorizacion': caf.fecha_autorizacion.strftime('%Y-%m-%d'),
                        'modulo': 'MODULO_RSA',
                        'exponente': 'EXPONENTE_RSA',
                        'firma': caf.firma_electronica,
                    }
                    
                    ted_xml = firmador.generar_ted(dte_data, caf_data)
                    pdf417_data = firmador.generar_datos_pdf417(ted_xml)
                    
                    # 2. Actualizar DTE
                    dte.timbre_electronico = ted_xml
                    dte.datos_pdf417 = pdf417_data
                    dte.save()
                    
                    # 3. Generar imagen PDF417
                    PDF417Generator.guardar_pdf417_en_dte(dte)
                    
                    exitosos += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ DTE {dte.tipo_dte} N° {dte.folio} - Regenerado completamente'
                        )
                    )
                    
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
