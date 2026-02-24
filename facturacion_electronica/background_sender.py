"""
Servicio de envío asíncrono de DTEs al SII
Usa threading para no bloquear el POS
"""
import threading
import queue
import time
from django.utils import timezone
from django.db import transaction
from .dtebox_service import DTEBoxService
import logging

logger = logging.getLogger(__name__)


class BackgroundDTESender:
    """
    Servicio singleton para enviar DTEs al SII en segundo plano
    
    Características:
    - Cola de envíos FIFO
    - Máximo 5 threads simultáneos
    - Reintentos automáticos (3 intentos)
    - Log de errores
    - Thread-safe
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
        self.max_workers = 5
        self.workers = []
        self.running = True
        self.stats = {
            'total_enviados': 0,
            'total_errores': 0,
            'total_pendientes': 0,
            'ultimo_error': None
        }
        
        # Iniciar workers
        self._start_workers()
        
        logger.info(f"BackgroundDTESender iniciado con {self.max_workers} workers")
    
    def _start_workers(self):
        """Inicia los threads workers"""
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"DTESender-{i+1}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
    
    def _worker_loop(self):
        """Loop principal de cada worker"""
        while self.running:
            try:
                # Obtener tarea de la cola (timeout 1 segundo)
                try:
                    dte_id, empresa_id, intentos = self.send_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                # Procesar envío
                self._procesar_envio(dte_id, empresa_id, intentos)
                
                # Marcar tarea como completada
                self.send_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error en worker loop: {e}")
    
    def _procesar_envio(self, dte_id, empresa_id, intentos=0):
        """
        Procesa el envío de un DTE al SII
        
        Args:
            dte_id: ID del DocumentoTributarioElectronico
            empresa_id: ID de la Empresa
            intentos: Número de intentos realizados
        """
        from .models import DocumentoTributarioElectronico
        from empresas.models import Empresa
        
        max_intentos = 6
        
        try:
            # Obtener DTE y Empresa (nueva conexión DB por thread)
            dte = DocumentoTributarioElectronico.objects.select_related('empresa').get(id=dte_id)
            empresa = Empresa.objects.get(id=empresa_id)
            
            # XML para enviar: según GDExpress, por POST se envía XML SIN firmar (xml_dte). Si no hay, usar xml_firmado.
            xml_dte = (dte.xml_dte or '').strip()
            xml_firmado = (dte.xml_firmado or '').strip()
            xml_para_enviar = xml_dte if xml_dte else xml_firmado
            if not xml_para_enviar:
                logger.error(f"DTE {dte_id} no tiene XML (ni xml_dte ni xml_firmado)")
                self._marcar_error(dte, "XML del documento vacío. Regenera el XML desde el detalle del DTE.")
                return
            
            # Actualizar estado a "enviando"
            with transaction.atomic():
                dte.estado_sii = 'enviando'
                dte.save(update_fields=['estado_sii'])
            
            logger.info(f"[Thread {threading.current_thread().name}] Enviando DTE {dte.folio} (intento {intentos + 1}/{max_intentos})")
            
            # Todas las guías y DTEs se envían a DTEBox/GDExpress. Solo "enviado" si DTEBox responde OK.
            # Enviar a DTEBox por POST: XML sin firmar (xml_dte) según GDExpress
            dtebox = DTEBoxService(empresa)
            resultado = dtebox.timbrar_dte(xml_para_enviar, dte.tipo_dte)
            
            if resultado['success']:
                # Éxito: guardar TED y actualizar estado
                with transaction.atomic():
                    dte.timbre_electronico = resultado['ted']
                    dte.fecha_envio_sii = timezone.now()
                    dte.estado_sii = 'enviado'
                    dte.error_envio = ''  # String vacío en lugar de None
                    dte.save(update_fields=['timbre_electronico', 'fecha_envio_sii', 'estado_sii', 'error_envio'])
                
                self.stats['total_enviados'] += 1
                logger.info(f"[OK] DTE {dte.folio} enviado exitosamente")
                
            else:
                # Error: verificar si reintentar
                error_msg = resultado.get('error', 'Error desconocido')
                logger.warning(f"[ERROR] DTE {dte.folio}: {error_msg}")
                
                if intentos < max_intentos - 1:
                    delays = [5, 30, 120, 300, 900, 1800]
                    delay = delays[intentos] if intentos < len(delays) else 1800
                    logger.info(f"Reintentando DTE {dte.folio} en {delay} segundos...")
                    time.sleep(delay)
                    self.enviar_dte(dte_id, empresa_id, intentos + 1)
                else:
                    # Máximo de intentos alcanzado
                    self._marcar_error(dte, error_msg)
                    self.stats['total_errores'] += 1
                    self.stats['ultimo_error'] = error_msg
        
        except DocumentoTributarioElectronico.DoesNotExist:
            logger.error(f"DTE {dte_id} no encontrado")
        except Exception as e:
            logger.error(f"Error al procesar DTE {dte_id}: {e}")
            
            # Si hay intentos disponibles, reintentar
            if intentos < max_intentos - 1:
                delays = [5, 30, 120, 300, 900, 1800]
                delay = delays[intentos] if intentos < len(delays) else 1800
                time.sleep(delay)
                self.enviar_dte(dte_id, empresa_id, intentos + 1)
            else:
                try:
                    dte = DocumentoTributarioElectronico.objects.get(id=dte_id)
                    self._marcar_error(dte, str(e))
                except:
                    pass
                self.stats['total_errores'] += 1
    
    def _marcar_error(self, dte, error_msg):
        """Marca un DTE con error y estado pendiente"""
        try:
            with transaction.atomic():
                dte.estado_sii = 'pendiente'
                dte.error_envio = error_msg[:500]  # Limitar tamaño
                dte.save(update_fields=['estado_sii', 'error_envio'])
            logger.error(f"DTE {dte.folio} marcado como pendiente: {error_msg}")
        except Exception as e:
            logger.error(f"Error al marcar DTE como pendiente: {e}")
    
    def enviar_dte(self, dte_id, empresa_id, intentos=0):
        """
        Agrega un DTE a la cola de envío
        
        Args:
            dte_id: ID del DocumentoTributarioElectronico
            empresa_id: ID de la Empresa
            intentos: Número de intentos previos (para reintentos)
        
        Returns:
            bool: True si se agregó a la cola
        """
        try:
            self.send_queue.put((dte_id, empresa_id, intentos))
            self.stats['total_pendientes'] = self.send_queue.qsize()
            logger.info(f"DTE {dte_id} agregado a la cola de envío (cola: {self.send_queue.qsize()})")
            return True
        except Exception as e:
            logger.error(f"Error al agregar DTE a la cola: {e}")
            return False
    
    def enviar_multiples(self, dtes_ids, empresa_id):
        """
        Agrega múltiples DTEs a la cola de envío
        
        Args:
            dtes_ids: Lista de IDs de DocumentoTributarioElectronico
            empresa_id: ID de la Empresa
        
        Returns:
            int: Cantidad de DTEs agregados
        """
        count = 0
        for dte_id in dtes_ids:
            if self.enviar_dte(dte_id, empresa_id):
                count += 1
        return count
    
    def get_stats(self):
        """Retorna estadísticas del servicio"""
        return {
            'enviados': self.stats['total_enviados'],
            'errores': self.stats['total_errores'],
            'en_cola': self.send_queue.qsize(),
            'workers_activos': len([w for w in self.workers if w.is_alive()]),
            'ultimo_error': self.stats['ultimo_error']
        }
    
    def esperar_cola_vacia(self, timeout=30):
        """
        Espera a que la cola se vacíe
        
        Args:
            timeout: Tiempo máximo de espera en segundos
        
        Returns:
            bool: True si la cola se vació, False si timeout
        """
        try:
            self.send_queue.join()
            return True
        except:
            return False
    
    def shutdown(self):
        """Detiene el servicio de forma ordenada"""
        logger.info("Deteniendo BackgroundDTESender...")
        self.running = False
        
        # Esperar a que terminen los workers
        for worker in self.workers:
            worker.join(timeout=5)
        
        logger.info("BackgroundDTESender detenido")


# Instancia global del servicio
_sender_instance = None
_sender_lock = threading.Lock()


def get_background_sender():
    """
    Obtiene la instancia singleton del BackgroundDTESender
    
    Returns:
        BackgroundDTESender: Instancia del servicio
    """
    global _sender_instance
    
    if _sender_instance is None:
        with _sender_lock:
            if _sender_instance is None:
                _sender_instance = BackgroundDTESender()
    
    return _sender_instance

