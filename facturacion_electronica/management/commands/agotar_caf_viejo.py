from django.core.management.base import BaseCommand
from facturacion_electronica.models import ArchivoCAF
from empresas.models import Empresa

class Command(BaseCommand):
    help = 'Marca CAF viejo de boletas como agotado'

    def handle(self, *args, **options):
        empresa = Empresa.objects.filter(nombre__icontains='krea').first()
        if not empresa:
            empresa = Empresa.objects.first()
        
        self.stdout.write(f'Empresa: {empresa.nombre}')
        
        # CAF ID 5 (rango 206-255) debería estar agotado
        try:
            caf_viejo = ArchivoCAF.objects.get(id=5, empresa=empresa)
            self.stdout.write(f'\nCAF ID 5:')
            self.stdout.write(f'  Rango: {caf_viejo.folio_desde}-{caf_viejo.folio_hasta}')
            self.stdout.write(f'  Folio actual: {caf_viejo.folio_actual}')
            self.stdout.write(f'  Estado actual: {caf_viejo.estado}')
            
            if caf_viejo.estado == 'activo':
                caf_viejo.estado = 'agotado'
                caf_viejo.save()
                self.stdout.write(self.style.SUCCESS('  ✅ Marcado como AGOTADO'))
            else:
                self.stdout.write(f'  Ya está {caf_viejo.estado}')
                
        except ArchivoCAF.DoesNotExist:
            self.stdout.write(self.style.ERROR('No se encontró CAF ID 5'))
        
        # Verificar CAF ID 15 está activo
        try:
            caf_nuevo = ArchivoCAF.objects.get(id=15, empresa=empresa)
            self.stdout.write(f'\nCAF ID 15 (nuevo):')
            self.stdout.write(f'  Rango: {caf_nuevo.folio_desde}-{caf_nuevo.folio_hasta}')
            self.stdout.write(f'  Folio actual: {caf_nuevo.folio_actual}')
            self.stdout.write(f'  Estado: {caf_nuevo.estado}')
            
            if caf_nuevo.estado == 'activo':
                self.stdout.write(self.style.SUCCESS('  ✅ Activo y listo para usar'))
            else:
                self.stdout.write(self.style.WARNING('  ⚠️ No está activo'))
                
        except ArchivoCAF.DoesNotExist:
            self.stdout.write(self.style.ERROR('No se encontró CAF ID 15'))
        
        self.stdout.write('\nEl próximo folio de boleta será: 260')
