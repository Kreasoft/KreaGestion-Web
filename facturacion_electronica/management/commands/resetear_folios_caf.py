"""
Comando para resetear los folios de archivos CAF
Esto permite reutilizar los rangos de folios de los CAF para pruebas
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from facturacion_electronica.models import ArchivoCAF


class Command(BaseCommand):
    help = 'Resetea los folios de los archivos CAF para poder reutilizarlos (SOLO PARA PRUEBAS)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa',
            type=int,
            help='ID de empresa específica para resetear (opcional)'
        )
        parser.add_argument(
            '--tipo_documento',
            type=str,
            choices=['33', '34', '39', '41', '52', '56', '61'],
            help='Tipo de documento específico para resetear (opcional)'
        )
        parser.add_argument(
            '--confirmacion',
            action='store_true',
            help='Confirmación obligatoria para ejecutar el reset'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('ATENCIÓN: RESET DE FOLIOS CAF'))
        self.stdout.write(self.style.WARNING('=' * 80))
        self.stdout.write(self.style.WARNING('ESTA OPERACIÓN ES SOLO PARA PRUEBAS'))
        self.stdout.write(self.style.WARNING('Los folios se resetearán al inicio del rango'))
        self.stdout.write(self.style.WARNING('No usar en producción sin respaldo'))
        self.stdout.write(self.style.WARNING('=' * 80))

        # Verificar confirmación
        if not options['confirmacion']:
            self.stdout.write(self.style.ERROR('\nERROR: Se requiere confirmación explícita'))
            self.stdout.write(self.style.ERROR('Use el argumento --confirmacion para proceder'))
            return

        # Filtrar por empresa si se especifica
        filtro = {}
        if options['empresa']:
            filtro['empresa_id'] = options['empresa']

        if options['tipo_documento']:
            filtro['tipo_documento'] = options['tipo_documento']

        # Obtener CAFs a resetear
        cafs = ArchivoCAF.objects.filter(estado__in=['activo', 'agotado', 'vencido'], **filtro)
        total_cafs = cafs.count()

        if total_cafs == 0:
            self.stdout.write(self.style.WARNING('\nNo se encontraron CAFs para resetear con los filtros especificados'))
            return

        self.stdout.write(f'\nCAFs a resetear: {total_cafs}')

        # Mostrar detalles de los CAFs
        for caf in cafs:
            self.stdout.write(f'\n- {caf.get_tipo_documento_display()}')
            self.stdout.write(f'  Empresa: {caf.empresa.nombre}')
            self.stdout.write(f'  Rango: {caf.folio_desde}-{caf.folio_hasta}')
            self.stdout.write(f'  Folios utilizados: {caf.folios_utilizados}')
            self.stdout.write(f'  Folio actual: {caf.folio_actual}')
            self.stdout.write(f'  Estado: {caf.get_estado_display()}')

        self.stdout.write('\n' + '=' * 80)

        # Confirmación final (automática para evitar problemas con entrada interactiva)
        self.stdout.write(self.style.WARNING('\nEjecutando reset automáticamente (modo producción)...'))
        # respuesta = input('\n¿Está seguro de que desea resetear estos CAFs? (si/NO): ')
        # if respuesta.lower() != 'si':
        #     self.stdout.write(self.style.WARNING('\nOperación cancelada por el usuario'))
        #     return

        # Proceder con el reset
        reseteados = 0
        errores = 0

        for caf in cafs:
            try:
                # Guardar estado anterior para mostrar en el log
                estado_anterior = caf.estado
                folios_anteriores = caf.folios_utilizados
                folio_anterior = caf.folio_actual

                # Resetear el CAF
                caf.resetear_folios()

                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nOK: {caf.get_tipo_documento_display()} '
                        f'(Folios {caf.folio_desde}-{caf.folio_hasta})'
                    )
                )
                self.stdout.write(f'   Estado anterior: {estado_anterior}')
                self.stdout.write(f'   Folios utilizados anterior: {folios_anteriores}')
                self.stdout.write(f'   Folio actual anterior: {folio_anterior}')
                self.stdout.write(f'   Estado actual: {caf.get_estado_display()}')
                self.stdout.write(f'   Folio actual reset: {caf.folio_actual}')

                reseteados += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'\nERROR al resetear CAF {caf.get_tipo_documento_display()}: {str(e)}'
                    )
                )
                errores += 1

        # Resumen final
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('\nRESUMEN DEL RESET:'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'\nCAFs reseteados exitosamente: {reseteados}')
        if errores > 0:
            self.stdout.write(f'Errores durante el proceso: {errores}')

        self.stdout.write(self.style.SUCCESS('\nRESET COMPLETADO'))
        self.stdout.write(self.style.WARNING('Ahora puede generar nuevos documentos con los folios reiniciados'))

        if errores > 0:
            self.stdout.write(self.style.ERROR(f'\nATENCIÓN: Hubo {errores} errores durante el proceso'))
            return

        self.stdout.write('\n' + '=' * 80)
