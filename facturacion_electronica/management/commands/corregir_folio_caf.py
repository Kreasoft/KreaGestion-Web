from django.core.management.base import BaseCommand
from facturacion_electronica.models import ArchivoCAF, DocumentoTributarioElectronico
from empresas.models import Empresa

class Command(BaseCommand):
    help = 'Verifica y corrige folio_actual de CAFs de boleta'

    def handle(self, *args, **options):
        empresa = Empresa.objects.filter(nombre__icontains='krea').first()
        if not empresa:
            empresa = Empresa.objects.first()
        
        self.stdout.write(f'Empresa: {empresa.nombre}')
        self.stdout.write('')
        
        # CAFs de boleta (tipo 39)
        cafs = ArchivoCAF.objects.filter(
            empresa=empresa, 
            tipo_documento='39',
            estado='activo'
        ).order_by('folio_desde')
        
        self.stdout.write('CAFs de Boleta (tipo 39) activos:')
        for caf in cafs:
            self.stdout.write(f'  CAF ID {caf.id}:')
            self.stdout.write(f'    Rango: {caf.folio_desde}-{caf.folio_hasta}')
            self.stdout.write(f'    Folio actual actual: {caf.folio_actual}')
            
            # Buscar último DTE de boleta en este rango
            ultimo_dte = DocumentoTributarioElectronico.objects.filter(
                empresa=empresa,
                tipo_dte='39',
                folio__gte=caf.folio_desde,
                folio__lte=caf.folio_hasta
            ).order_by('-folio').first()
            
            if ultimo_dte:
                self.stdout.write(f'    Último DTE local: folio {ultimo_dte.folio}')
                folio_correcto = max(ultimo_dte.folio, caf.folio_actual)
                
                if caf.folio_actual != folio_correcto:
                    self.stdout.write(self.style.WARNING(f'    ⚠️ CORRIGIENDO folio_actual de {caf.folio_actual} a {folio_correcto}'))
                    caf.folio_actual = folio_correcto
                    caf.folios_utilizados = folio_correcto - caf.folio_desde + 1
                    caf.save()
                    self.stdout.write(self.style.SUCCESS(f'    ✅ CAF actualizado'))
                else:
                    self.stdout.write('    ✅ Folio actual correcto')
            else:
                self.stdout.write('    ℹ️ Sin DTEs emitidos en este rango')
        
        # Ver últimos DTEs de boleta
        self.stdout.write('')
        self.stdout.write('Últimos DTEs de boleta en BD:')
        dtes = DocumentoTributarioElectronico.objects.filter(
            tipo_dte='39',
            empresa=empresa
        ).order_by('-folio')[:5]
        
        for dte in dtes:
            self.stdout.write(f'  Folio {dte.folio} - Estado: {dte.estado_sii} - {dte.fecha_emision}')
