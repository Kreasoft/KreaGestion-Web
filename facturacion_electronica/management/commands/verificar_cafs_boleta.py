from django.core.management.base import BaseCommand
from facturacion_electronica.models import ArchivoCAF, DocumentoTributarioElectronico
from empresas.models import Empresa

class Command(BaseCommand):
    help = 'Verifica estado de CAFs de boleta'

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
            activo=True
        ).order_by('folio_desde')
        
        self.stdout.write('CAFs de Boleta (tipo 39) activos:')
        for caf in cafs:
            folio_actual = caf.folio_actual or caf.folio_desde - 1
            usados = folio_actual - caf.folio_desde + 1
            disponibles = caf.folio_hasta - folio_actual
            
            self.stdout.write(f'  CAF ID {caf.id}:')
            self.stdout.write(f'    Rango: {caf.folio_desde}-{caf.folio_hasta}')
            self.stdout.write(f'    Folio actual: {folio_actual}')
            self.stdout.write(f'    Usados: {usados}, Disponibles: {disponibles}')
            self.stdout.write(f'    Vencimiento: {caf.fecha_vencimiento}')
        
        # Últimos DTEs de boleta
        self.stdout.write('')
        self.stdout.write('Últimos DTEs de boleta creados:')
        dtes = DocumentoTributarioElectronico.objects.filter(
            tipo_dte='39'
        ).order_by('-folio')[:5]
        
        for dte in dtes:
            self.stdout.write(f'  Folio {dte.folio} - Estado: {dte.estado_sii} - {dte.fecha_emision}')
