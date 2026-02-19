"""
Comando para ver el estado actual de los CAF (Códigos de Autorización de Folios)

Muestra:
- Folios totales del CAF
- Folios usados
- Folios disponibles
- Próximo folio a usar

USO:
    python manage.py ver_estado_caf
    python manage.py ver_estado_caf --tipo 52  # Solo Guías
"""

from django.core.management.base import BaseCommand
from facturacion_electronica.models import ArchivoCAF, DocumentoTributarioElectronico
from django.db.models import Max, Min, Count


class Command(BaseCommand):
    help = 'Muestra el estado actual de los CAF activos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tipo',
            type=str,
            help='Filtrar por tipo de documento (33=Factura, 39=Boleta, 52=Guía)',
        )

    def handle(self, *args, **options):
        tipo_doc = options.get('tipo')
        
        # Mapeo de códigos a nombres
        tipo_nombres = {
            '33': 'Factura Electrónica',
            '39': 'Boleta Electrónica',
            '52': 'Guía de Despacho',
            '61': 'Nota de Crédito',
            '56': 'Nota de Débito',
        }
        
        # Filtrar CAFs
        cafs = ArchivoCAF.objects.filter(estado='activo').order_by('tipo_documento', 'folio_desde')
        
        if tipo_doc:
            cafs = cafs.filter(tipo_documento=tipo_doc)
        
        if not cafs.exists():
            self.stdout.write(self.style.WARNING('No hay CAF activos en el sistema.'))
            return
        
        self.stdout.write('\n' + '='*100)
        self.stdout.write(self.style.SUCCESS('ESTADO DE ARCHIVOS CAF ACTIVOS'))
        self.stdout.write('='*100 + '\n')
        
        for caf in cafs:
            tipo_nombre = tipo_nombres.get(caf.tipo_documento, f'Tipo {caf.tipo_documento}')
            
            # Calcular estadísticas
            total_folios = caf.folio_hasta - caf.folio_desde + 1
            folios_usados = caf.folio_actual - caf.folio_desde
            folios_disponibles = caf.folio_hasta - caf.folio_actual + 1
            porcentaje_uso = (folios_usados / total_folios * 100) if total_folios > 0 else 0
            
            # Buscar DTEs generados con este CAF
            dtes_con_este_caf = DocumentoTributarioElectronico.objects.filter(
                tipo_documento=caf.tipo_documento,
                folio__gte=caf.folio_desde,
                folio__lte=caf.folio_hasta
            )
            
            dtes_count = dtes_con_este_caf.count()
            
            if dtes_count > 0:
                folios_usados_reales = list(dtes_con_este_caf.values_list('folio', flat=True).order_by('folio'))
                primer_folio_usado = folios_usados_reales[0] if folios_usados_reales else None
                ultimo_folio_usado = folios_usados_reales[-1] if folios_usados_reales else None
            else:
                primer_folio_usado = None
                ultimo_folio_usado = None
                folios_usados_reales = []
            
            # Mostrar información
            self.stdout.write(self.style.HTTP_INFO(f'📄 {tipo_nombre}'))
            self.stdout.write(f'   CAF ID: {caf.id}')
            self.stdout.write(f'   Empresa: {caf.empresa.razon_social}')
            self.stdout.write(f'   Fecha autorización: {caf.fecha_autorizacion}')
            self.stdout.write('')
            
            self.stdout.write('   🔢 RANGO DE FOLIOS:')
            self.stdout.write(f'      Desde: {caf.folio_desde:,}')
            self.stdout.write(f'      Hasta: {caf.folio_hasta:,}')
            self.stdout.write(f'      Total: {total_folios:,} folios')
            self.stdout.write('')
            
            self.stdout.write('   📊 ESTADO DE USO:')
            self.stdout.write(f'      Folio actual: {caf.folio_actual:,}')
            self.stdout.write(f'      Usados: {folios_usados:,} folios ({porcentaje_uso:.1f}%)')
            
            # Color según disponibilidad
            if folios_disponibles > 20:
                estilo = self.style.SUCCESS
                icono = '✅'
            elif folios_disponibles > 5:
                estilo = self.style.WARNING
                icono = '⚠️'
            else:
                estilo = self.style.ERROR
                icono = '🚨'
            
            self.stdout.write(estilo(f'      {icono} Disponibles: {folios_disponibles:,} folios'))
            self.stdout.write('')
            
            if dtes_count > 0:
                self.stdout.write('   📋 DTEs GENERADOS:')
                self.stdout.write(f'      Total documentos: {dtes_count}')
                self.stdout.write(f'      Primer folio usado: {primer_folio_usado:,}')
                self.stdout.write(f'      Último folio usado: {ultimo_folio_usado:,}')
                
                # Detectar huecos
                if ultimo_folio_usado and primer_folio_usado:
                    folios_esperados = ultimo_folio_usado - primer_folio_usado + 1
                    if dtes_count < folios_esperados:
                        huecos = folios_esperados - dtes_count
                        self.stdout.write(self.style.WARNING(f'      ⚠️  Posibles huecos: {huecos} folios sin usar entre el rango usado'))
            else:
                self.stdout.write('   📋 DTEs GENERADOS:')
                self.stdout.write('      Ningún documento generado aún')
            
            self.stdout.write('')
            self.stdout.write('   ➡️  PRÓXIMO FOLIO A USAR: ' + 
                            self.style.SUCCESS(f'{caf.folio_actual:,}'))
            
            self.stdout.write('')
            self.stdout.write('-'*100)
            self.stdout.write('')
        
        # Resumen general
        self.stdout.write('='*100)
        self.stdout.write(self.style.SUCCESS('RESUMEN GENERAL'))
        self.stdout.write('='*100)
        
        for tipo_cod, tipo_nom in tipo_nombres.items():
            cafs_tipo = ArchivoCAF.objects.filter(tipo_documento=tipo_cod, estado='activo')
            if cafs_tipo.exists():
                total_disp = sum(c.folio_hasta - c.folio_actual + 1 for c in cafs_tipo)
                self.stdout.write(f'{tipo_nom}: {total_disp:,} folios disponibles en total')
        
        self.stdout.write('')
