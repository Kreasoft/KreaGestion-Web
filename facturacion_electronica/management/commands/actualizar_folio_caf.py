"""
Actualizar el folio_actual de un CAF

Permite resetear desde qué folio se comenzará a usar
CUIDADO: Solo usar si sabes que no hay documentos emitidos con esos folios

USO:
    python manage.py actualizar_folio_caf --tipo 52 --nuevo-folio 80
"""

from django.core.management.base import BaseCommand
from facturacion_electronica.models import ArchivoCAF, DocumentoTributarioElectronico


class Command(BaseCommand):
    help = 'Actualiza el folio_actual de un CAF'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tipo',
            type=str,
            required=True,
            help='Tipo de documento (33=Factura, 39=Boleta, 52=Guía)',
        )
        parser.add_argument(
            '--nuevo-folio',
            type=int,
            required=True,
            help='Nuevo valor para folio_actual (próximo folio a usar)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='No pedir confirmación',
        )

    def handle(self, *args, **options):
        tipo_doc = options['tipo']
        nuevo_folio = options['nuevo_folio']
        force = options['force']
        
        # Buscar CAF
        caf = ArchivoCAF.objects.filter(
            tipo_documento=tipo_doc,
            estado='activo'
        ).first()
        
        if not caf:
            self.stdout.write(self.style.ERROR(f'No hay CAF activo para el tipo {tipo_doc}'))
            return
        
        # Mostrar información actual
        self.stdout.write('\n' + '='*80)
        self.stdout.write(f'CAF ENCONTRADO: {caf.get_tipo_documento_display()}')
        self.stdout.write('='*80)
        self.stdout.write(f'Rango: {caf.folio_desde:,} - {caf.folio_hasta:,}')
        self.stdout.write(f'Folio actual: {caf.folio_actual:,}')
        self.stdout.write(f'Disponibles: {caf.folio_hasta - caf.folio_actual + 1:,}')
        self.stdout.write('')
        
        # Validar nuevo folio
        if nuevo_folio < caf.folio_desde:
            self.stdout.write(self.style.ERROR(f'❌ Error: El nuevo folio ({nuevo_folio}) es menor que folio_desde ({caf.folio_desde})'))
            return
        
        if nuevo_folio > caf.folio_hasta:
            self.stdout.write(self.style.ERROR(f'❌ Error: El nuevo folio ({nuevo_folio}) es mayor que folio_hasta ({caf.folio_hasta})'))
            return
        
        # Verificar si hay DTEs con folios >= nuevo_folio
        dtes_conflicto = DocumentoTributarioElectronico.objects.filter(
            tipo_documento=tipo_doc,
            folio__gte=nuevo_folio,
            folio__lte=caf.folio_hasta
        )
        
        if dtes_conflicto.exists():
            self.stdout.write(self.style.WARNING(f'\n⚠️  ADVERTENCIA: Ya existen {dtes_conflicto.count()} DTEs con folios >= {nuevo_folio}'))
            self.stdout.write('Folios en conflicto:')
            for dte in dtes_conflicto.order_by('folio')[:10]:
                self.stdout.write(f'  - Folio {dte.folio}')
            if dtes_conflicto.count() > 10:
                self.stdout.write(f'  ... y {dtes_conflicto.count() - 10} más')
            self.stdout.write('')
            
            if not force:
                self.stdout.write(self.style.ERROR('❌ Operación cancelada para evitar duplicados.'))
                self.stdout.write('Si estás seguro, usa --force')
                return
        
        # Mostrar cambio
        self.stdout.write('='*80)
        self.stdout.write('CAMBIO A REALIZAR:')
        self.stdout.write('='*80)
        self.stdout.write(f'Folio actual: {caf.folio_actual:,} → {nuevo_folio:,}')
        
        nueva_disponibilidad = caf.folio_hasta - nuevo_folio + 1
        self.stdout.write(f'Folios disponibles: {caf.folio_hasta - caf.folio_actual + 1:,} → {nueva_disponibilidad:,}')
        self.stdout.write('')
        
        # Confirmar
        if not force:
            confirm = input('¿Confirmar cambio? (S/N): ')
            if confirm.upper() != 'S':
                self.stdout.write(self.style.WARNING('Operación cancelada.'))
                return
        
        # Actualizar
        caf.folio_actual = nuevo_folio
        caf.save()
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✓ Folio actualizado correctamente'))
        self.stdout.write(f'Próximo folio a usar: {nuevo_folio:,}')
        self.stdout.write(f'Folios disponibles: {nueva_disponibilidad:,}')
        self.stdout.write('')
