"""
Comando para generar timbre de prueba sin certificado
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.pdf417_generator import PDF417Generator


class Command(BaseCommand):
    help = 'Genera timbre PDF417 de prueba para DTEs sin certificado'

    def add_arguments(self, parser):
        parser.add_argument(
            '--folio',
            type=int,
            help='Generar solo para un folio específico',
        )
        parser.add_argument(
            '--tipo',
            type=str,
            help='Generar solo para un tipo de DTE específico (33, 39, 52, etc.)',
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
                    self.stdout.write(f'\n🔄 Procesando DTE {dte.tipo_dte} N° {dte.folio}...')
                    
                    # Generar datos de prueba para PDF417
                    ted_data = f"""<TED version="1.0">
<DD>
<RE>{dte.rut_emisor}</RE>
<TD>{dte.tipo_dte}</TD>
<F>{dte.folio}</F>
<FE>{dte.fecha_emision.strftime('%Y-%m-%d')}</FE>
<RR>{dte.rut_receptor}</RR>
<RSR>{dte.razon_social_receptor}</RSR>
<MNT>{int(dte.monto_total)}</MNT>
<IT1>DOCUMENTO DE PRUEBA</IT1>
<CAF version="1.0">
<DA>
<RE>{dte.rut_emisor}</RE>
<RS>{dte.razon_social_emisor}</RS>
<TD>{dte.tipo_dte}</TD>
<RNG><D>{dte.caf_utilizado.folio_desde}</D><H>{dte.caf_utilizado.folio_hasta}</H></RNG>
<FA>{dte.caf_utilizado.fecha_autorizacion.strftime('%Y-%m-%d')}</FA>
</DA>
</CAF>
<TSTED>{dte.fecha_emision.strftime('%Y-%m-%dT%H:%M:%S')}</TSTED>
</DD>
<FRMT algoritmo="SHA1withRSA">FIRMA_DE_PRUEBA</FRMT>
</TED>"""
                    
                    # Actualizar DTE
                    dte.timbre_electronico = ted_data
                    dte.datos_pdf417 = ted_data  # Usar el XML como datos para PDF417
                    dte.save()
                    
                    # Generar imagen PDF417
                    PDF417Generator.guardar_pdf417_en_dte(dte)
                    
                    exitosos += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ DTE {dte.tipo_dte} N° {dte.folio} - Timbre de prueba generado'
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
        self.stdout.write(self.style.WARNING('\n⚠️  NOTA: Estos son timbres DE PRUEBA, no válidos para el SII'))
