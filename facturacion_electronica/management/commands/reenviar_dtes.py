"""
Comando Django para reenviar DTEs pendientes de forma segura
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.envio_seguro import reenviar_dtes_pendientes, enviar_dte_seguro
from facturacion_electronica.validacion_envio import diagnosticar_dte
from empresas.models import Empresa


class Command(BaseCommand):
    help = 'Reenvía DTEs pendientes de envío al SII'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa',
            type=str,
            help='RUT de la empresa (opcional, procesa todas si no se especifica)'
        )
        
        parser.add_argument(
            '--limite',
            type=int,
            help='Número máximo de DTEs a procesar'
        )
        
        parser.add_argument(
            '--diagnostico',
            action='store_true',
            help='Solo muestra diagnóstico sin enviar realmente'
        )
        
        parser.add_argument(
            '--dte-id',
            type=int,
            help='ID específico de un DTE a reenviar'
        )
        
        parser.add_argument(
            '--forzar',
            action='store_true',
            help='Forzar envío aunque falle la validación (usar con cuidado)'
        )

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("SISTEMA DE REENVÍO SEGURO DE DTEs"))
        self.stdout.write("=" * 80)
        self.stdout.write("")
        
        # Obtener empresa si se especificó
        empresa = None
        if options['empresa']:
            try:
                empresa = Empresa.objects.get(rut=options['empresa'])
                self.stdout.write(f"📋 Empresa: {empresa.nombre} ({empresa.rut})")
            except Empresa.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ Empresa con RUT {options['empresa']} no encontrada"))
                return
        
        # Modo: DTE específico
        if options['dte_id']:
            self.stdout.write("")
            self.stdout.write(f"🎯 Modo: Reenvío de DTE específico (ID: {options['dte_id']})")
            self.stdout.write("")
            
            try:
                dte = DocumentoTributarioElectronico.objects.get(pk=options['dte_id'])
            except DocumentoTributarioElectronico.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ DTE con ID {options['dte_id']} no encontrado"))
                return
            
            # Mostrar información del DTE
            self.stdout.write(f"Tipo: {dte.get_tipo_dte_display()} ({dte.tipo_dte})")
            self.stdout.write(f"Folio: {dte.folio}")
            self.stdout.write(f"Fecha: {dte.fecha_emision}")
            self.stdout.write(f"Estado actual: {dte.estado_sii}")
            self.stdout.write(f"Receptor: {dte.razon_social_receptor}")
            self.stdout.write(f"Monto: ${dte.monto_total:,.0f}")
            self.stdout.write("")
            
            if options['diagnostico']:
                # Solo diagnóstico
                self.stdout.write("🔍 Ejecutando diagnóstico...")
                self.stdout.write("")
                
                diagnostico = diagnosticar_dte(dte)
                
                self.stdout.write("Resultado del diagnóstico:")
                self.stdout.write(f"  • Tiene XML: {'✓' if diagnostico['tiene_xml'] else '✗'}")
                self.stdout.write(f"  • Tiene CAF: {'✓' if diagnostico['tiene_caf'] else '✗'}")
                if diagnostico['caf_vigente'] is not None:
                    self.stdout.write(f"  • CAF vigente: {'✓' if diagnostico['caf_vigente'] else '✗'}")
                self.stdout.write(f"  • Válido para envío: {'✓' if diagnostico['es_valido_para_envio'] else '✗'}")
                
                if not diagnostico['es_valido_para_envio']:
                    self.stdout.write("")
                    self.stdout.write(self.style.WARNING(f"⚠️ Error de validación: {diagnostico['error_validacion']}"))
                
                if diagnostico['ultimo_error_envio']:
                    self.stdout.write("")
                    self.stdout.write(f"Último error de envío: {diagnostico['ultimo_error_envio']}")
            else:
                # Enviar realmente
                self.stdout.write("📤 Enviando DTE...")
                self.stdout.write("")
                
                resultado = enviar_dte_seguro(dte, forzar=options['forzar'])
                
                if resultado['success']:
                    self.stdout.write(self.style.SUCCESS(f"✅ {resultado['mensaje']}"))
                    if resultado['track_id']:
                        self.stdout.write(f"Track ID: {resultado['track_id']}")
                else:
                    self.stdout.write(self.style.ERROR(f"❌ {resultado['mensaje']}"))
                    if resultado['error']:
                        self.stdout.write(f"Error: {resultado['error']}")
        
        # Modo: Reenvío masivo
        else:
            self.stdout.write("")
            self.stdout.write(f"🎯 Modo: Reenvío masivo de DTEs pendientes")
            if options['limite']:
                self.stdout.write(f"Límite: {options['limite']} DTEs")
            if options['diagnostico']:
                self.stdout.write("⚠️ Solo diagnóstico (no se enviarán DTEs)")
            self.stdout.write("")
            
            # Ejecutar reenvío
            resumen = reenviar_dtes_pendientes(
                empresa=empresa,
                limite=options['limite'],
                solo_diagnostico=options['diagnostico']
            )
            
            # Mostrar resumen
            self.stdout.write("")
            self.stdout.write("=" * 80)
            self.stdout.write("RESUMEN")
            self.stdout.write("=" * 80)
            self.stdout.write(f"Total procesados: {resumen['total_procesados']}")
            self.stdout.write(self.style.SUCCESS(f"✅ Exitosos: {resumen['exitosos']}"))
            self.stdout.write(self.style.ERROR(f"❌ Fallidos: {resumen['fallidos']}"))
            if resumen['saltados'] > 0:
                self.stdout.write(self.style.WARNING(f"⚠️ Saltados: {resumen['saltados']}"))
            
            # Mostrar detalles
            if resumen['resultados']:
                self.stdout.write("")
                self.stdout.write("DETALLES:")
                self.stdout.write("")
                
                for i, res in enumerate(resumen['resultados'], 1):
                    simbolo = "✅" if res['accion'] in ['ENVIADO', 'DIAGNÓSTICO'] else "❌"
                    
                    if options['diagnostico']:
                        # Modo diagnóstico
                        diag = res['diagnostico']
                        valido = "✓" if diag['es_valido_para_envio'] else "✗"
                        self.stdout.write(
                            f"{i}. {simbolo} DTE {res['tipo']} #{res['folio']} - "
                            f"Válido: {valido}"
                        )
                        if not diag['es_valido_para_envio']:
                            self.stdout.write(f"   Error: {diag['error_validacion']}")
                    else:
                        # Modo envío
                        resultado = res['resultado']
                        self.stdout.write(
                            f"{i}. {simbolo} DTE {res['tipo']} #{res['folio']} - "
                            f"{resultado['mensaje']}"
                        )
            
            self.stdout.write("")
            self.stdout.write("=" * 80)
            
            if not options['diagnostico'] and resumen['exitosos'] > 0:
                self.stdout.write(self.style.SUCCESS(f"✅ Proceso completado - {resumen['exitosos']} DTEs enviados exitosamente"))
            elif options['diagnostico']:
                self.stdout.write(self.style.SUCCESS("✅ Diagnóstico completado"))
