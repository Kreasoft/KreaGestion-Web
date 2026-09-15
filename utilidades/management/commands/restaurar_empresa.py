import os
import sys
import time
import json
import traceback
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from empresas.models import Empresa
from utilidades.respaldo_empresa import restaurar_respaldo, extraer_payload_respaldo, RespaldoError


class Command(BaseCommand):
    help = 'Restaura un respaldo completo de empresa desde un archivo JSON directamente en la base de datos.'

    def add_arguments(self, parser):
        parser.add_argument('archivo', type=str, help='Ruta al archivo JSON de respaldo')
        parser.add_argument(
            '--empresa_id',
            type=int,
            help='ID de la empresa destino. Si no se especifica, se detectará automáticamente del archivo.'
        )
        parser.add_argument(
            '--forzar',
            action='store_true',
            help='Omite la confirmación interactiva antes de restaurar.'
        )
        parser.add_argument(
            '--verbose_detalles',
            action='store_true',
            help='Muestra el detalle paso a paso de cada modelo procesado.'
        )

    def handle(self, *args, **options):
        archivo_path = options['archivo']
        empresa_id = options.get('empresa_id')
        forzar = options.get('forzar', False)
        verbose = options.get('verbose_detalles', False)

        self.stdout.write(self.style.MIGRATE_HEADING('=' * 70))
        self.stdout.write(self.style.MIGRATE_HEADING('   RESTAURACIÓN ROBUSTA DE RESPALDO DE EMPRESA'))
        self.stdout.write(self.style.MIGRATE_HEADING('=' * 70))

        if not os.path.exists(archivo_path):
            raise CommandError(f'El archivo "{archivo_path}" no existe.')

        self.stdout.write(f'Leyendo archivo: {archivo_path} ...')
        try:
            with open(archivo_path, 'rb') as f:
                contenido = f.read()
        except Exception as e:
            raise CommandError(f'Error al leer el archivo: {e}')

        size_mb = len(contenido) / (1024 * 1024)
        self.stdout.write(f'Tamaño del archivo: {size_mb:.2f} MB')

        # Analizar metadatos del archivo
        try:
            payload = extraer_payload_respaldo(contenido)
        except Exception as e:
            raise CommandError(f'Error al interpretar el contenido del respaldo: {e}')

        json_empresa_id = payload.get('empresa_id')
        json_rut = payload.get('rut')
        json_nombre = payload.get('empresa_nombre')
        total_registros = len(payload.get('registros', []))

        self.stdout.write(f'Metadatos del respaldo:')
        self.stdout.write(f' - Empresa ID origen: {json_empresa_id}')
        self.stdout.write(f' - RUT origen: {json_rut}')
        self.stdout.write(f' - Nombre origen: {json_nombre or "(No especificado)"}')
        self.stdout.write(f' - Total de registros en archivo: {total_registros}')

        # Determinar empresa destino
        empresa = None
        if empresa_id:
            try:
                empresa = Empresa.objects.get(pk=empresa_id)
            except Empresa.DoesNotExist:
                raise CommandError(f'La empresa con ID {empresa_id} no existe en la base de datos.')
        elif json_empresa_id and Empresa.objects.filter(pk=json_empresa_id).exists():
            empresa = Empresa.objects.get(pk=json_empresa_id)
        elif json_rut and Empresa.objects.filter(rut=json_rut).exists():
            empresa = Empresa.objects.filter(rut=json_rut).first()
        else:
            empresas = list(Empresa.objects.all())
            if len(empresas) == 1:
                empresa = empresas[0]
            else:
                self.stdout.write(self.style.WARNING('\nEmpresas disponibles en el sistema:'))
                for emp in empresas:
                    self.stdout.write(f' [{emp.pk}] {emp.nombre} (RUT: {emp.rut})')
                raise CommandError('Debe especificar --empresa_id=<ID> para indicar la empresa destino.')

        self.stdout.write(self.style.SUCCESS(f'\nEmpresa destino seleccionada: [{empresa.pk}] {empresa.nombre} (RUT: {empresa.rut})'))

        if not forzar:
            self.stdout.write(self.style.WARNING('\nADVERTENCIA: Se restaurarán y actualizarán los registros de la empresa seleccionada.'))
            confirm = input('¿Desea continuar con la restauración? (escriba "si" o "y" para confirmar): ')
            if confirm.strip().lower() not in ('si', 'sí', 'y', 'yes'):
                self.stdout.write(self.style.NOTICE('Operación cancelada por el usuario.'))
                return

        self.stdout.write('\nIniciando proceso de restauración...')
        inicio = time.time()

        def progreso(model, count, accion):
            if verbose:
                self.stdout.write(f' - Procesado {model._meta.label_lower}: {count} registros ({accion})')

        resumen = {}
        try:
            total_recuperados = restaurar_respaldo(contenido, empresa, resumen=resumen, callback_progreso=progreso)
            duracion = time.time() - inicio

            self.stdout.write(self.style.MIGRATE_HEADING('\n' + '=' * 70))
            self.stdout.write(self.style.SUCCESS('   RESTAURACIÓN COMPLETADA CON ÉXITO'))
            self.stdout.write(self.style.MIGRATE_HEADING('=' * 70))
            self.stdout.write(f'Tiempo total: {duracion:.2f} segundos')
            self.stdout.write(f'Total registros restaurados/actualizados: {total_recuperados}')
            self.stdout.write(f'Tablas afectadas: {resumen.get("tablas_afectadas", 0)}')
            if resumen.get('referencias_historicas_conservadas'):
                self.stdout.write(f'Referencias históricas conservadas: {resumen["referencias_historicas_conservadas"]}')
            self.stdout.write(self.style.SUCCESS('\nSecuencias de PostgreSQL y claves foráneas sincronizadas correctamente.\n'))

        except Exception as e:
            self.stdout.write(self.style.ERROR('\n' + '!' * 70))
            self.stdout.write(self.style.ERROR(f'   ERROR AL RESTAURAR: {str(e)}'))
            self.stdout.write(self.style.ERROR('!' * 70 + '\n'))
            traceback.print_exc()
            raise CommandError(f'Fallo en la restauración: {e}')
