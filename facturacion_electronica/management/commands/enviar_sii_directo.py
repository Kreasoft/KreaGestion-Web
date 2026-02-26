"""
Comando para enviar DTE directamente al SII (sin DTEBox).
Solo funciona en ambiente de certificación.
"""
from django.core.management.base import BaseCommand
from facturacion_electronica.models import DocumentoTributarioElectronico
from facturacion_electronica.dte_service import DTEService
from facturacion_electronica.firma_electronica import FirmadorDTE
from facturacion_electronica.cliente_sii import ClienteSII
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = 'Envía un DTE directamente al SII (sin DTEBox) - solo certificación'

    def add_arguments(self, parser):
        parser.add_argument('folio', type=int, help='Folio del DTE a enviar')
        parser.add_argument('--tipo', type=str, default='33', help='Tipo de DTE (33=factura, 39=boleta, etc.)')

    def handle(self, *args, **options):
        folio = options['folio']
        tipo_dte = options['tipo']

        try:
            dte = DocumentoTributarioElectronico.objects.get(folio=folio, tipo_dte=tipo_dte)
            self.stdout.write(self.style.SUCCESS(f'DTE {tipo_dte}-{folio} encontrado (ID: {dte.id})'))
            
            empresa = dte.empresa
            
            # Verificar que estamos en certificación
            ambiente = empresa.ambiente_sii or 'certificacion'
            if ambiente not in ['certificacion', 'certificación', 'CERTIFICACION']:
                self.stdout.write(self.style.ERROR(f'⚠️ Ambiente actual: {ambiente}'))
                self.stdout.write(self.style.ERROR('❌ Este comando solo funciona en ambiente CERTIFICACION'))
                self.stdout.write(self.style.WARNING('Para producción, use DTEBox'))
                return
            
            self.stdout.write(f'Empresa: {empresa.nombre}')
            self.stdout.write(f'Ambiente: {ambiente}')
            self.stdout.write(f'RUT Emisor: {empresa.rut}')
            
            # Inicializar cliente SII
            self.stdout.write('\n--- Inicializando Cliente SII ---')
            cliente_sii = ClienteSII(ambiente='certificacion')
            
            # Obtener firmador
            self.stdout.write('Obteniendo firmador...')
            certificado_path = empresa.certificado_digital.path
            password = empresa.password_certificado
            firmador = FirmadorDTE(certificado_path, password)
            
            # Obtener semilla
            self.stdout.write('Obteniendo semilla del SII...')
            semilla = cliente_sii.obtener_semilla()
            self.stdout.write(self.style.SUCCESS(f'✅ Semilla obtenida: {semilla[:50]}...'))
            
            # Obtener token
            self.stdout.write('Obteniendo token de autenticación...')
            token = cliente_sii.obtener_token(semilla, firmador)
            self.stdout.write(self.style.SUCCESS(f'✅ Token obtenido: {token[:50]}...'))
            
            # Preparar XML para envío (SetDTE)
            self.stdout.write('\n--- Preparando SetDTE ---')
            xml_dte = dte.xml_firmado or dte.xml_dte
            if not xml_dte:
                self.stdout.write(self.style.ERROR('❌ No hay XML disponible'))
                return
            
            # Carátula
            caratula = {
                'rut_emisor': empresa.rut,
                'rut_envia': empresa.rut,
                'rut_receptor': '60803000-K',
                'fecha_resolucion': (empresa.resolucion_fecha.strftime('%Y-%m-%d') if empresa.resolucion_fecha else '2014-08-22'),
                'numero_resolucion': int(empresa.resolucion_numero or 0),
            }
            
            self.stdout.write(f'Carátula: {caratula}')
            
            # Crear SetDTE
            set_xml = cliente_sii.crear_set_dte([xml_dte], caratula)
            self.stdout.write(self.style.SUCCESS(f'✅ SetDTE creado ({len(set_xml)} bytes)'))
            
            # Enviar al SII
            self.stdout.write('\n--- Enviando al SII ---')
            respuesta = cliente_sii.enviar_dte(
                xml_envio=set_xml,
                token=token,
                rut_emisor=empresa.rut,
                rut_envia=empresa.rut
            )
            
            track_id = respuesta.get('track_id')
            if track_id:
                self.stdout.write(self.style.SUCCESS(f'✅ DTE enviado exitosamente al SII'))
                self.stdout.write(self.style.SUCCESS(f'✅ Track ID: {track_id}'))
                
                # Actualizar DTE
                with transaction.atomic():
                    dte.estado_sii = 'enviado'
                    dte.track_id = track_id
                    dte.fecha_envio_sii = timezone.now()
                    dte.respuesta_sii = respuesta.get('respuesta_completa', '')
                    dte.save()
                
                self.stdout.write(self.style.SUCCESS(f'✅ DTE actualizado en base de datos'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ No se recibió Track ID'))
                self.stdout.write(f'Respuesta: {respuesta}')
                
        except DocumentoTributarioElectronico.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'DTE {tipo_dte}-{folio} no encontrado'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
            import traceback
            traceback.print_exc()
