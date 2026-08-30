"""
Servicio de envío asíncrono de DTEs al SII.
Corre en segundo plano: no bloquea POS ni caja.
El reintento de pendientes se hace solo en tiempos muertos (cola vacía).
"""
import os
import sys
import threading
import queue
import time
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

COMANDOS_SIN_SENDER = {
    'migrate', 'makemigrations', 'collectstatic', 'check', 'shell',
    'test', 'dumpdata', 'loaddata', 'createsuperuser',
}


class BackgroundDTESender:
    """
    Servicio singleton para enviar DTEs al SII en segundo plano.

    - Cola FIFO con pocos workers (no satura el SII ni el POS)
    - Reintentos diferidos, sin dormir el worker
    - Scanner en tiempos muertos: encola de a pocos
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.send_queue = queue.Queue()
        self.max_workers = 2
        self.workers = []
        self.running = True
        self.stats = {
            'total_enviados': 0,
            'total_errores': 0,
            'total_pendientes': 0,
            'ultimo_error': None,
        }
        self._en_cola = {}
        self._cola_lock = threading.Lock()
        self._delayed = []
        self._idle_thread = None

        self._start_workers()
        self._start_idle_scanner()
        logger.info(
            "BackgroundDTESender iniciado: %s workers + reenvío automático en tiempos muertos",
            self.max_workers,
        )

    def _start_workers(self, cantidad=None):
        faltan = self.max_workers if cantidad is None else cantidad
        ya = len(self.workers)
        for i in range(faltan):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"DTESender-{ya + i + 1}",
                daemon=True,
            )
            worker.start()
            self.workers.append(worker)

    def _ensure_workers(self):
        vivos = [w for w in self.workers if w.is_alive()]
        if not vivos:
            with self._cola_lock:
                self._en_cola.clear()
        self.workers = vivos
        faltan = self.max_workers - len(self.workers)
        if faltan > 0:
            self._start_workers(faltan)
            logger.info("Workers DTE reactivados: %s", faltan)

    def _worker_loop(self):
        from django.db import close_old_connections

        while self.running:
            try:
                try:
                    dte_id, empresa_id, intentos = self.send_queue.get(timeout=1)
                except queue.Empty:
                    self._pasar_reintentos_listos()
                    continue
                try:
                    close_old_connections()
                    self._procesar_envio(dte_id, empresa_id, intentos)
                finally:
                    close_old_connections()
                    self.send_queue.task_done()
            except Exception as e:
                logger.error("Error en worker loop: %s", e)

    def _procesar_envio(self, dte_id, empresa_id, intentos=0):
        from .models import DocumentoTributarioElectronico
        from empresas.models import Empresa

        max_intentos = 4

        try:
            dte = DocumentoTributarioElectronico.objects.select_related('empresa', 'caf_utilizado').get(id=dte_id)
            empresa = Empresa.objects.get(id=empresa_id)
            if dte.estado_sii in ('aceptado', 'aceptado_reparos', 'anulado'):
                self._sacar_de_cola(dte_id)
                return
            if str(dte.track_id or '').strip() and not dte.permite_reenvio_xml_corregido:
                self._sacar_de_cola(dte_id)
                return
            caf = getattr(dte, 'caf_utilizado', None)
            if caf and hasattr(caf, 'esta_vigente') and not caf.esta_vigente():
                self._marcar_pendiente_reenvio(dte, f'El CAF está vencido (venció el {caf.fecha_vencimiento})')
                self._sacar_de_cola(dte_id)
                logger.info("DTE %s omitido: CAF vencido, no se reintenta solo", dte.folio)
                return

            logger.info(
                "[%s] Enviando DTE %s (intento %s/%s)",
                threading.current_thread().name, dte.folio, intentos + 1, max_intentos,
            )

            from .dte_service import DTEService
            try:
                resultado = DTEService(empresa).enviar_dte_al_sii(dte)
            except Exception as exc:
                resultado = {'success': False, 'error': str(exc)}

            dte.refresh_from_db()
            track = str(dte.track_id or '').strip() or resultado.get('track_id')
            if resultado.get('success') or track:
                self.stats['total_enviados'] += 1
                self._sacar_de_cola(dte_id)
                logger.info("DTE %s enviado al SII Track %s", dte.folio, track or '-')
                return

            error_msg = resultado.get('error') or resultado.get('xml_respuesta') or 'El SII no confirmó el envío'
            logger.warning("DTE %s sin confirmación: %s", dte.folio, error_msg)
            self._manejar_fallo(dte, dte_id, empresa_id, intentos, max_intentos, error_msg)

        except DocumentoTributarioElectronico.DoesNotExist:
            self._sacar_de_cola(dte_id)
        except Exception as e:
            logger.error("Error al procesar DTE %s: %s", dte_id, e)
            try:
                dte = DocumentoTributarioElectronico.objects.get(id=dte_id)
                self._manejar_fallo(dte, dte_id, empresa_id, intentos, max_intentos, str(e))
            except Exception:
                self._sacar_de_cola(dte_id)
                self.stats['total_errores'] += 1

    def _manejar_fallo(self, dte, dte_id, empresa_id, intentos, max_intentos, error_msg):
        self._marcar_pendiente_reenvio(dte, error_msg)
        self._sacar_de_cola(dte_id)
        texto = (error_msg or '').lower()
        if 'caf' in texto and 'vencid' in texto:
            logger.info("DTE %s no se reintenta: CAF vencido", dte.folio)
            return
        if 'prcitem' in texto or 'precio o total 0' in texto or 'mininclusive' in texto:
            logger.info("DTE %s no se reintenta: precio 0 inválido para el SII", dte.folio)
            return
        if intentos < max_intentos - 1:
            from .clasificacion_sii import es_espera_reintento_sii, extraer_segundos_espera
            delays = [45, 180, 600, 1800]
            delay = delays[intentos] if intentos < len(delays) else 1800
            if es_espera_reintento_sii(error_msg):
                delay = max(delay, extraer_segundos_espera(error_msg) or 900)
            self._agendar_reintento(dte_id, empresa_id, intentos + 1, delay)
        else:
            self.stats['total_errores'] += 1
            self.stats['ultimo_error'] = error_msg
            logger.info("DTE %s queda pendiente de reenvío automático", dte.folio)

    def _marcar_pendiente_reenvio(self, dte, error_msg):
        try:
            with transaction.atomic():
                from .clasificacion_sii import extraer_track_id
                dte.estado_sii = 'error_envio'
                dte.error_envio = (error_msg or '')[:500]
                dte.fecha_consulta_estado = timezone.now()
                campos = ['estado_sii', 'error_envio', 'fecha_consulta_estado']
                track_glosa = extraer_track_id(error_msg)
                if track_glosa and not str(dte.track_id or '').strip():
                    dte.track_id = track_glosa
                    campos.append('track_id')
                dte.save(update_fields=campos)
        except Exception as e:
            logger.error("No se pudo marcar pendiente de reenvío: %s", e)

    def _agendar_reintento(self, dte_id, empresa_id, intentos, delay_segundos):
        when = time.time() + delay_segundos
        with self._cola_lock:
            self._delayed.append((when, dte_id, empresa_id, intentos))
        logger.info("DTE %s se reintentará en %ss (sin bloquear el sistema)", dte_id, delay_segundos)

    def _pasar_reintentos_listos(self):
        ahora = time.time()
        listos = []
        with self._cola_lock:
            quedan = []
            for item in self._delayed:
                if item[0] <= ahora:
                    listos.append(item)
                else:
                    quedan.append(item)
            self._delayed = quedan
        for _, dte_id, empresa_id, intentos in listos:
            self.enviar_dte(dte_id, empresa_id, intentos)

    def enviar_dte(self, dte_id, empresa_id, intentos=0):
        self._ensure_workers()
        try:
            with self._cola_lock:
                inicio = self._en_cola.get(dte_id)
                if inicio and (time.time() - inicio) < 180:
                    return False
                self._en_cola[dte_id] = time.time()
            self.send_queue.put((dte_id, empresa_id, intentos))
            self.stats['total_pendientes'] = self.send_queue.qsize()
            return True
        except Exception as e:
            self._sacar_de_cola(dte_id)
            logger.error("Error al agregar DTE a la cola: %s", e)
            return False

    def enviar_ahora(self, dte_ids, empresa_id):
        """Envía ya (mismo camino que el botón de la fila) y devuelve Track o error."""
        from .dte_service import DTEService
        from .models import DocumentoTributarioElectronico
        from empresas.models import Empresa

        empresa = Empresa.objects.filter(id=empresa_id).first()
        if not empresa:
            return [], [{'folio': '-', 'error': 'Empresa no encontrada'}]

        servicio = DTEService(empresa)
        enviados = []
        fallidos = []
        for dte_id in dte_ids:
            try:
                dte = DocumentoTributarioElectronico.objects.select_related('empresa').get(id=dte_id)
                if dte.tiene_track_sii and not dte.permite_reenvio_xml_corregido:
                    continue
                try:
                    resultado = servicio.enviar_dte_al_sii(dte)
                except Exception as exc:
                    resultado = {'success': False, 'error': str(exc)}
                dte.refresh_from_db()
                track = str(resultado.get('track_id') or dte.track_id_efectivo() or '').strip()
                if resultado.get('success') or track:
                    enviados.append({'folio': dte.folio, 'track': track})
                else:
                    fallidos.append({
                        'folio': dte.folio,
                        'error': (resultado.get('error') or 'El SII no entregó Track')[:240],
                    })
            except DocumentoTributarioElectronico.DoesNotExist:
                fallidos.append({'folio': dte_id, 'error': 'DTE no encontrado'})
            except Exception as e:
                fallidos.append({'folio': dte_id, 'error': str(e)[:240]})
        return enviados, fallidos

    def enviar_multiples(self, dtes_ids, empresa_id):
        count = 0
        for dte_id in dtes_ids:
            if self.enviar_dte(dte_id, empresa_id):
                count += 1
        return count

    def get_stats(self):
        with self._cola_lock:
            en_cola_ids = len(self._en_cola)
            delayed = len(self._delayed)
        return {
            'enviados': self.stats['total_enviados'],
            'errores': self.stats['total_errores'],
            'en_cola': self.send_queue.qsize(),
            'en_proceso': en_cola_ids,
            'reintentos_programados': delayed,
            'workers_activos': len([w for w in self.workers if w.is_alive()]),
            'ultimo_error': self.stats['ultimo_error'],
        }

    def _sacar_de_cola(self, dte_id):
        with self._cola_lock:
            self._en_cola.pop(dte_id, None)

    def is_idle_auto(self, empresa_id=None):
        return True

    def set_idle_auto(self, empresa_id, enabled=True):
        return True

    def encolar_pendientes(self, empresa_id, limite=None, solo_enfriados=True):
        self._ensure_workers()
        from django.db.models import Q
        from .validacion_envio import obtener_dtes_pendientes_envio
        from empresas.models import Empresa

        empresa = Empresa.objects.filter(id=empresa_id).first()
        if not empresa:
            return 0
        pendientes = obtener_dtes_pendientes_envio(empresa, solo_mes_actual=True)
        if solo_enfriados:
            umbral = timezone.now() - timedelta(minutes=3)
            pendientes = pendientes.exclude(
                Q(estado_sii='error_envio') &
                Q(fecha_consulta_estado__isnull=False) &
                Q(fecha_consulta_estado__gt=umbral)
            )
        if limite:
            pendientes = pendientes[:limite]
        dte_ids = list(pendientes.values_list('id', flat=True))
        count = self.enviar_multiples(dte_ids, empresa_id)
        if count:
            print(f"[DTE AUTO] Mes actual: {count} documento(s) encolados al SII")
        return count

    def consultar_pendientes_sii(self, empresa_id, limite=4):
        """Consulta en segundo plano DTEs con Track que aún no tienen veredicto."""
        from django.db.models import Q
        from .models import DocumentoTributarioElectronico
        from .dte_service import DTEService
        from empresas.models import Empresa

        empresa = Empresa.objects.filter(id=empresa_id).first()
        if not empresa:
            return 0
        umbral = timezone.now() - timedelta(minutes=2)
        hoy = timezone.localdate()
        inicio = hoy.replace(day=1)
        qs = (
            DocumentoTributarioElectronico.objects.filter(empresa_id=empresa_id)
            .filter(
                Q(fecha_emision__gte=inicio, fecha_emision__lte=hoy) |
                Q(fecha__gte=inicio, fecha__lte=hoy)
            )
            .exclude(Q(track_id__isnull=True) | Q(track_id=''))
            .exclude(track_id__istartswith='DTEBOX')
            .exclude(estado_sii__in=['aceptado', 'aceptado_reparos', 'anulado'])
            .filter(
                Q(fecha_consulta_estado__isnull=True) |
                Q(fecha_consulta_estado__lte=umbral)
            )
            .select_related('empresa')
            .order_by('-fecha_emision', '-folio')[:limite]
        )
        servicio = DTEService(empresa)
        consultados = 0
        for dte in qs:
            if not dte.requiere_refresco_estado_sii():
                continue
            try:
                servicio.consultar_estado_dte(dte)
                consultados += 1
            except Exception as e:
                logger.warning("Consulta automática folio %s: %s", dte.folio, e)
        return consultados

    def _start_idle_scanner(self):
        if self._idle_thread and self._idle_thread.is_alive():
            return
        self._idle_thread = threading.Thread(
            target=self._idle_loop,
            name="DTESender-Idle",
            daemon=True,
        )
        self._idle_thread.start()

    def _esta_ocupado(self):
        if self.send_queue.qsize() > 0:
            return True
        ahora = time.time()
        with self._cola_lock:
            for dte_id, inicio in list(self._en_cola.items()):
                if ahora - inicio > 180:
                    self._en_cola.pop(dte_id, None)
            return len(self._en_cola) > 0

    def _idle_loop(self):
        from django.db import close_old_connections

        primera = True
        while self.running:
            time.sleep(15 if primera else 45)
            primera = False
            if not self.running:
                break
            self._pasar_reintentos_listos()
            try:
                close_old_connections()
                from empresas.models import Empresa
                empresas = Empresa.objects.filter(facturacion_electronica=True).values_list('id', flat=True)
                for empresa_id in empresas:
                    if not self._esta_ocupado():
                        self.encolar_pendientes(empresa_id, limite=2, solo_enfriados=True)
                    if not self._esta_ocupado():
                        self.consultar_pendientes_sii(empresa_id, limite=4)
            except Exception as e:
                logger.error("Error en reenvío/consulta automática idle: %s", e)
            finally:
                close_old_connections()

    def esperar_cola_vacia(self, timeout=30):
        try:
            self.send_queue.join()
            return True
        except Exception:
            return False

    def shutdown(self):
        logger.info("Deteniendo BackgroundDTESender...")
        self.running = False
        for worker in self.workers:
            worker.join(timeout=5)
        if self._idle_thread:
            self._idle_thread.join(timeout=5)


_sender_instance = None
_sender_lock = threading.Lock()


def debe_iniciar_sender_en_proceso():
    if any(cmd in sys.argv for cmd in COMANDOS_SIN_SENDER):
        return False
    if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') != 'true':
        return False
    return True


def get_background_sender():
    global _sender_instance
    if _sender_instance is None:
        with _sender_lock:
            if _sender_instance is None:
                _sender_instance = BackgroundDTESender()
    return _sender_instance
