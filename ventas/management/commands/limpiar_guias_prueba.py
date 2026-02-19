"""
Comando para limpiar guías de despacho de prueba con errores

Elimina:
- Guías creadas hoy con tipo_despacho incorrecto
- DTEs asociados
- Libera los folios usados

USO:
    python manage.py limpiar_guias_prueba --dry-run  # Ver qué se eliminaría
    python manage.py limpiar_guias_prueba             # Eliminar realmente
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import date
from ventas.models import Venta
from facturacion_electronica.models import DocumentoTributarioElectronico


class Command(BaseCommand):
    help = 'Limpia guías de despacho de prueba con errores'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra qué se eliminaría, sin eliminar realmente',
        )
        parser.add_argument(
            '--fecha',
            type=str,
            help='Fecha específica (YYYY-MM-DD). Por defecto: hoy',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        fecha_str = options.get('fecha')
        
        if fecha_str:
            from datetime import datetime
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        else:
            fecha = date.today()
        
        self.stdout.write(self.style.WARNING(f'Buscando guías problemáticas del {fecha}...'))
        
        # Buscar guías de hoy
        guias = Venta.objects.filter(
            tipo_documento='guia',
            fecha=fecha
        ).order_by('id')
        
        total_guias = guias.count()
        self.stdout.write(f'Total de guías encontradas: {total_guias}')
        
        if total_guias == 0:
            self.stdout.write(self.style.SUCCESS('No hay guías para revisar.'))
            return
        
        # Mostrar detalles de cada guía
        self.stdout.write('\n' + '='*80)
        self.stdout.write('GUÍAS ENCONTRADAS:')
        self.stdout.write('='*80)
        
        guias_a_eliminar = []
        
        for guia in guias:
            dte = DocumentoTributarioElectronico.objects.filter(venta=guia).first()
            
            self.stdout.write(f'\nID: {guia.id} | Número: {guia.numero_venta}')
            self.stdout.write(f'  Cliente: {guia.cliente.nombre if guia.cliente else "N/A"}')
            self.stdout.write(f'  Total: ${guia.total:,.0f}')
            self.stdout.write(f'  Tipo Despacho: {guia.get_tipo_despacho_display() if guia.tipo_despacho else "⚠️  NO DEFINIDO"}')
            self.stdout.write(f'  DTE: {f"Folio {dte.folio}" if dte else "Sin DTE"}')
            if dte:
                self.stdout.write(f'  Estado SII: {dte.estado_sii if hasattr(dte, "estado_sii") else "N/A"}')
            
            # Criterios para eliminar (puedes ajustar esto)
            es_problematica = False
            razones = []
            
            # Criterio 1: Sin tipo de despacho
            if not guia.tipo_despacho:
                es_problematica = True
                razones.append('❌ Sin tipo de despacho')
            
            # Criterio 2: Tipo despacho = 1 (Venta) que probablemente debería ser otro
            # (Esto es subjetivo, ajusta según tu caso)
            if guia.tipo_despacho == '1' and guia.total == 0:
                es_problematica = True
                razones.append('❌ Venta con total $0 (probablemente prueba)')
            
            if es_problematica:
                guias_a_eliminar.append({
                    'guia': guia,
                    'dte': dte,
                    'razones': razones
                })
                
                for razon in razones:
                    self.stdout.write(f'  {razon}')
        
        # Resumen
        self.stdout.write('\n' + '='*80)
        self.stdout.write(f'Guías a eliminar: {len(guias_a_eliminar)} de {total_guias}')
        self.stdout.write('='*80 + '\n')
        
        if len(guias_a_eliminar) == 0:
            self.stdout.write(self.style.SUCCESS('✓ No hay guías problemáticas para eliminar.'))
            return
        
        # Mostrar lista de eliminación
        for item in guias_a_eliminar:
            guia = item['guia']
            dte = item['dte']
            self.stdout.write(f'• ID {guia.id} - Número {guia.numero_venta}' + 
                            (f' - Folio DTE {dte.folio}' if dte else ''))
            for razon in item['razones']:
                self.stdout.write(f'  {razon}')
        
        if dry_run:
            self.stdout.write('\n' + self.style.WARNING('🔍 MODO DRY-RUN: No se eliminó nada.'))
            self.stdout.write('Para eliminar realmente, ejecuta sin --dry-run')
            return
        
        # Confirmar eliminación
        self.stdout.write('\n' + self.style.ERROR('⚠️  ADVERTENCIA: Esto eliminará las guías permanentemente.'))
        confirm = input('¿Estás seguro? Escribe "ELIMINAR" para confirmar: ')
        
        if confirm != 'ELIMINAR':
            self.stdout.write(self.style.WARNING('Operación cancelada.'))
            return
        
        # Eliminar
        eliminadas = 0
        dtes_eliminados = 0
        
        with transaction.atomic():
            for item in guias_a_eliminar:
                guia = item['guia']
                dte = item['dte']
                
                try:
                    # Eliminar DTE primero
                    if dte:
                        folio = dte.folio
                        dte.delete()
                        dtes_eliminados += 1
                        self.stdout.write(f'  ✓ DTE Folio {folio} eliminado')
                    
                    # Eliminar Venta (los detalles se eliminan en cascada)
                    numero = guia.numero_venta
                    guia.delete()
                    eliminadas += 1
                    self.stdout.write(f'  ✓ Guía #{numero} eliminada')
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ✗ Error al eliminar {guia.id}: {str(e)}'))
        
        # Resumen final
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS(f'✓ Eliminación completada:'))
        self.stdout.write(f'  - Guías eliminadas: {eliminadas}')
        self.stdout.write(f'  - DTEs eliminados: {dtes_eliminados}')
        self.stdout.write('='*80)
