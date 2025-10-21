"""
Comando para exportar XMLs de DTEs sin enviarlos al SII
"""
from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico
from empresas.models import Empresa
import os
from datetime import datetime


class Command(BaseCommand):
    help = 'Exporta los XMLs de DTEs a archivos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dte-id',
            type=int,
            help='ID del DTE a exportar'
        )
        parser.add_argument(
            '--empresa-id',
            type=int,
            help='ID de la empresa (exporta todos los DTEs de esa empresa)'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default='xml_export',
            help='Directorio de salida para los XMLs (default: xml_export)'
        )
        parser.add_argument(
            '--pendientes',
            action='store_true',
            help='Solo exportar DTEs no enviados'
        )

    def handle(self, *args, **options):
        dte_id = options.get('dte_id')
        empresa_id = options.get('empresa_id')
        output_dir = options.get('output_dir')
        pendientes = options.get('pendientes')
        
        # Crear directorio de salida
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            self.stdout.write(f"Directorio creado: {output_dir}")
        
        if dte_id:
            # Exportar un DTE específico
            self._exportar_dte_individual(dte_id, output_dir)
        elif empresa_id:
            # Exportar todos los DTEs de una empresa
            self._exportar_dtes_empresa(empresa_id, output_dir, pendientes)
        else:
            self.stdout.write(self.style.ERROR(
                'Debe especificar --dte-id o --empresa-id'
            ))
            return
    
    def _exportar_dte_individual(self, dte_id, output_dir):
        """Exporta un DTE específico"""
        try:
            dte = DocumentoTributarioElectronico.objects.get(id=dte_id)
            
            self.stdout.write("=" * 80)
            self.stdout.write(self.style.SUCCESS(f"EXPORTANDO DTE"))
            self.stdout.write("=" * 80)
            self.stdout.write(f"DTE ID: {dte.id}")
            self.stdout.write(f"Tipo: {dte.get_tipo_dte_display()}")
            self.stdout.write(f"Folio: {dte.folio}")
            self.stdout.write(f"Empresa: {dte.empresa.nombre}")
            
            # Generar nombre de archivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"DTE_{dte.tipo_dte}_{dte.folio}_{timestamp}.xml"
            filepath = os.path.join(output_dir, filename)
            
            # Guardar XML firmado
            if dte.xml_firmado:
                with open(filepath, 'w', encoding='ISO-8859-1') as f:
                    f.write(dte.xml_firmado)
                
                self.stdout.write(self.style.SUCCESS(f"\nXML exportado exitosamente:"))
                self.stdout.write(f"  {filepath}")
                self.stdout.write(f"  Tamaño: {len(dte.xml_firmado)} bytes")
            else:
                self.stdout.write(self.style.WARNING("No hay XML firmado para este DTE"))
                
        except DocumentoTributarioElectronico.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"No se encontró el DTE con ID {dte_id}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al exportar DTE: {str(e)}"))
            import traceback
            traceback.print_exc()
    
    def _exportar_dtes_empresa(self, empresa_id, output_dir, solo_pendientes=False):
        """Exporta todos los DTEs de una empresa"""
        try:
            empresa = Empresa.objects.get(id=empresa_id)
            
            # Filtrar DTEs
            query = DocumentoTributarioElectronico.objects.filter(empresa=empresa)
            if solo_pendientes:
                query = query.filter(estado_sii='generado')
            
            dtes = query.order_by('fecha_emision', 'folio')
            total = dtes.count()
            
            if total == 0:
                mensaje = "DTEs pendientes" if solo_pendientes else "DTEs"
                self.stdout.write(self.style.WARNING(
                    f"No hay {mensaje} para exportar de {empresa.nombre}"
                ))
                return
            
            self.stdout.write("=" * 80)
            self.stdout.write(self.style.SUCCESS(
                f"EXPORTANDO {total} DTE(S) - {empresa.nombre}"
            ))
            self.stdout.write("=" * 80)
            
            # Crear subdirectorio para la empresa
            empresa_dir = os.path.join(output_dir, f"{empresa.rut}_{empresa.nombre[:30]}")
            if not os.path.exists(empresa_dir):
                os.makedirs(empresa_dir)
            
            exportados = 0
            sin_xml = 0
            
            for i, dte in enumerate(dtes, 1):
                self.stdout.write(f"\n[{i}/{total}] {dte.get_tipo_dte_display()} Folio {dte.folio}...")
                
                if dte.xml_firmado:
                    filename = f"DTE_{dte.tipo_dte}_{dte.folio}_{dte.fecha_emision.strftime('%Y%m%d')}.xml"
                    filepath = os.path.join(empresa_dir, filename)
                    
                    with open(filepath, 'w', encoding='ISO-8859-1') as f:
                        f.write(dte.xml_firmado)
                    
                    self.stdout.write(self.style.SUCCESS(f"   Exportado: {filename}"))
                    exportados += 1
                else:
                    self.stdout.write(self.style.WARNING("   Sin XML firmado"))
                    sin_xml += 1
            
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write(self.style.SUCCESS("RESUMEN DE EXPORTACIÓN"))
            self.stdout.write("=" * 80)
            self.stdout.write(f"Total procesados: {total}")
            self.stdout.write(f"Exportados: {exportados}")
            self.stdout.write(f"Sin XML: {sin_xml}")
            self.stdout.write(f"\nArchivos guardados en: {empresa_dir}")
            
        except Empresa.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"No se encontró la empresa con ID {empresa_id}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            import traceback
            traceback.print_exc()

