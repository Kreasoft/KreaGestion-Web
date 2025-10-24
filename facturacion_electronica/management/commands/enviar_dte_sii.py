"""
Comando para enviar DTEs al SII
"""
from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dte_service import DTEService
from empresas.models import Empresa


class Command(BaseCommand):
    help = 'Envía uno o más DTEs al SII'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dte-id',
            type=int,
            help='ID del DTE a enviar'
        )
        parser.add_argument(
            '--empresa-id',
            type=int,
            help='ID de la empresa (envía todos los DTEs pendientes de esa empresa)'
        )
        parser.add_argument(
            '--todos',
            action='store_true',
            help='Enviar todos los DTEs generados pero no enviados'
        )

    def handle(self, *args, **options):
        dte_id = options.get('dte_id')
        empresa_id = options.get('empresa_id')
        todos = options.get('todos')
        
        if dte_id:
            # Enviar un DTE específico
            self._enviar_dte_individual(dte_id)
        elif empresa_id:
            # Enviar todos los DTEs pendientes de una empresa
            self._enviar_dtes_empresa(empresa_id)
        elif todos:
            # Enviar todos los DTEs pendientes
            self._enviar_todos_dtes()
        else:
            self.stdout.write(self.style.ERROR(
                'Debe especificar --dte-id, --empresa-id o --todos'
            ))
            return
    
    def _enviar_dte_individual(self, dte_id):
        """Envía un DTE específico al SII"""
        try:
            dte = DocumentoTributarioElectronico.objects.get(id=dte_id)
            
            self.stdout.write("=" * 80)
            self.stdout.write(self.style.SUCCESS(f"ENVIANDO DTE AL SII"))
            self.stdout.write("=" * 80)
            self.stdout.write(f"DTE ID: {dte.id}")
            self.stdout.write(f"Tipo: {dte.get_tipo_dte_display()}")
            self.stdout.write(f"Folio: {dte.folio}")
            self.stdout.write(f"Empresa: {dte.empresa.nombre}")
            self.stdout.write(f"Estado actual: {dte.estado_sii}")
            
            # Verificar que no haya sido enviado
            if dte.estado_sii in ['enviado', 'aceptado']:
                self.stdout.write(self.style.WARNING(
                    f"Este DTE ya fue enviado al SII (Estado: {dte.estado_sii})"
                ))
                return
            
            # Inicializar servicio y enviar
            dte_service = DTEService(dte.empresa)
            resultado = dte_service.enviar_dte_al_sii(dte)
            
            self.stdout.write("\n" + "=" * 80)
            if resultado.get('track_id'):
                self.stdout.write(self.style.SUCCESS("DTE ENVIADO EXITOSAMENTE"))
                self.stdout.write("=" * 80)
                self.stdout.write(f"Track ID: {resultado['track_id']}")
                self.stdout.write(f"Estado: {resultado.get('estado', 'N/A')}")
            else:
                self.stdout.write(self.style.WARNING("DTE enviado pero sin Track ID"))
                self.stdout.write("=" * 80)
                self.stdout.write(f"Respuesta: {resultado.get('respuesta_completa', 'N/A')[:200]}")
                
        except DocumentoTributarioElectronico.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"No se encontró el DTE con ID {dte_id}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al enviar DTE: {str(e)}"))
            import traceback
            traceback.print_exc()
    
    def _enviar_dtes_empresa(self, empresa_id):
        """Envía todos los DTEs pendientes de una empresa"""
        try:
            empresa = Empresa.objects.get(id=empresa_id)
            
            # Obtener DTEs pendientes
            dtes = DocumentoTributarioElectronico.objects.filter(
                empresa=empresa,
                estado_sii='generado'
            ).order_by('fecha_emision', 'folio')
            
            total = dtes.count()
            
            if total == 0:
                self.stdout.write(self.style.WARNING(
                    f"No hay DTEs pendientes de envío para {empresa.nombre}"
                ))
                return
            
            self.stdout.write("=" * 80)
            self.stdout.write(self.style.SUCCESS(
                f"ENVIANDO {total} DTE(S) AL SII - {empresa.nombre}"
            ))
            self.stdout.write("=" * 80)
            
            dte_service = DTEService(empresa)
            exitosos = 0
            fallidos = 0
            
            for i, dte in enumerate(dtes, 1):
                self.stdout.write(f"\n[{i}/{total}] Enviando {dte.get_tipo_dte_display()} Folio {dte.folio}...")
                
                try:
                    resultado = dte_service.enviar_dte_al_sii(dte)
                    if resultado.get('track_id'):
                        self.stdout.write(self.style.SUCCESS(
                            f"   OK - Track ID: {resultado['track_id']}"
                        ))
                        exitosos += 1
                    else:
                        self.stdout.write(self.style.WARNING("   Enviado sin Track ID"))
                        fallidos += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   Error: {str(e)}"))
                    fallidos += 1
            
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write(self.style.SUCCESS("RESUMEN DEL ENVÍO"))
            self.stdout.write("=" * 80)
            self.stdout.write(f"Total procesados: {total}")
            self.stdout.write(f"Exitosos: {exitosos}")
            self.stdout.write(f"Fallidos: {fallidos}")
            
        except Empresa.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"No se encontró la empresa con ID {empresa_id}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            import traceback
            traceback.print_exc()
    
    def _enviar_todos_dtes(self):
        """Envía todos los DTEs pendientes de todas las empresas"""
        try:
            # Obtener todas las empresas activas
            empresas = Empresa.objects.filter(activo=True)
            
            self.stdout.write("=" * 80)
            self.stdout.write(self.style.SUCCESS(
                f"ENVIANDO DTEs PENDIENTES DE TODAS LAS EMPRESAS ({empresas.count()})"
            ))
            self.stdout.write("=" * 80)
            
            for empresa in empresas:
                self._enviar_dtes_empresa(empresa.id)
                self.stdout.write("\n")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            import traceback
            traceback.print_exc()


