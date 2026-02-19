"""
Ver estado de CAF de forma simple
"""

from django.core.management.base import BaseCommand
from facturacion_electronica.models import ArchivoCAF


class Command(BaseCommand):
    help = 'Ver estado simple de CAF'

    def handle(self, *args, **options):
        tipo_nombres = {
            '33': 'Factura',
            '39': 'Boleta',
            '52': 'Guía de Despacho',
        }
        
        cafs = ArchivoCAF.objects.filter(estado='activo').order_by('tipo_documento')
        
        if not cafs.exists():
            self.stdout.write('No hay CAF activos')
            return
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write('ARCHIVOS CAF ACTIVOS')
        self.stdout.write('='*80 + '\n')
        
        for caf in cafs:
            tipo_nombre = tipo_nombres.get(caf.tipo_documento, f'Tipo {caf.tipo_documento}')
            total = caf.folio_hasta - caf.folio_desde + 1
            usados = caf.folio_actual - caf.folio_desde
            disponibles = caf.folio_hasta - caf.folio_actual + 1
            
            self.stdout.write(f'\n{tipo_nombre}:')
            self.stdout.write(f'  Rango: {caf.folio_desde:,} - {caf.folio_hasta:,} ({total:,} folios)')
            self.stdout.write(f'  Próximo folio: {caf.folio_actual:,}')
            self.stdout.write(f'  Usados: {usados:,}')
            
            if disponibles > 20:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Disponibles: {disponibles:,}'))
            elif disponibles > 5:
                self.stdout.write(self.style.WARNING(f'  ⚠️  Disponibles: {disponibles:,}'))
            else:
                self.stdout.write(self.style.ERROR(f'  🚨 Disponibles: {disponibles:,}'))
        
        self.stdout.write('\n' + '='*80 + '\n')
