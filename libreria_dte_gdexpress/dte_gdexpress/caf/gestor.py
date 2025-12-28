"""
Gestor de CAF (Código de Autorización de Folios)
"""
from lxml import etree
from datetime import datetime
import os


class GestorCAF:
    """
    Gestor de archivos CAF para control de folios
    
    Uso:
        gestor = GestorCAF(directorio='folios/')
        gestor.cargar_caf('FOLIO33.xml')
        
        folio = gestor.obtener_siguiente_folio(tipo_dte=33)
    """
    
    def __init__(self, directorio=None):
        """
        Inicializa el gestor
        
        Args:
            directorio (str, optional): Directorio donde están los archivos CAF
        """
        self.directorio = directorio or 'folios/'
        self.cafs = {}  # {tipo_dte: {info_caf}}
        self.folios_usados = {}  # {tipo_dte: set(folios_usados)}
    
    def cargar_caf(self, archivo_caf):
        """
        Carga un archivo CAF
        
        Args:
            archivo_caf (str): Ruta al archivo CAF
        """
        try:
            # Leer archivo
            if not os.path.isabs(archivo_caf) and self.directorio:
                archivo_caf = os.path.join(self.directorio, archivo_caf)
            
            with open(archivo_caf, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # Parsear XML
            root = etree.fromstring(xml_content.encode('utf-8'))
            
            # Extraer información
            tipo_dte = int(root.findtext('.//TD', 0))
            rango_desde = int(root.findtext('.//RNG/D', 0))
            rango_hasta = int(root.findtext('.//RNG/H', 0))
            fecha_autorizacion = root.findtext('.//FA', '')
            
            # Guardar CAF
            self.cafs[tipo_dte] = {
                'desde': rango_desde,
                'hasta': rango_hasta,
                'fecha_autorizacion': fecha_autorizacion,
                'xml': xml_content,
                'archivo': archivo_caf,
            }
            
            # Inicializar conjunto de folios usados
            if tipo_dte not in self.folios_usados:
                self.folios_usados[tipo_dte] = set()
        
        except Exception as e:
            raise ValueError(f"Error al cargar CAF: {e}")
    
    def cargar_todos_los_cafs(self):
        """
        Carga todos los archivos CAF del directorio
        """
        if not self.directorio or not os.path.exists(self.directorio):
            return
        
        for archivo in os.listdir(self.directorio):
            if archivo.endswith('.xml'):
                try:
                    self.cargar_caf(archivo)
                except Exception:
                    continue
    
    def obtener_siguiente_folio(self, tipo_dte):
        """
        Obtiene el siguiente folio disponible
        
        Args:
            tipo_dte (int): Tipo de DTE
            
        Returns:
            int: Siguiente folio disponible
        """
        if tipo_dte not in self.cafs:
            raise ValueError(f"No hay CAF cargado para tipo DTE {tipo_dte}")
        
        caf = self.cafs[tipo_dte]
        folios_usados = self.folios_usados.get(tipo_dte, set())
        
        # Buscar primer folio disponible
        for folio in range(caf['desde'], caf['hasta'] + 1):
            if folio not in folios_usados:
                return folio
        
        raise ValueError(f"No hay folios disponibles para tipo DTE {tipo_dte}")
    
    def marcar_folio_usado(self, tipo_dte, folio):
        """
        Marca un folio como usado
        
        Args:
            tipo_dte (int): Tipo de DTE
            folio (int): Número de folio
        """
        if tipo_dte not in self.folios_usados:
            self.folios_usados[tipo_dte] = set()
        
        self.folios_usados[tipo_dte].add(folio)
    
    def folios_disponibles(self, tipo_dte):
        """
        Retorna la cantidad de folios disponibles
        
        Args:
            tipo_dte (int): Tipo de DTE
            
        Returns:
            int: Cantidad de folios disponibles
        """
        if tipo_dte not in self.cafs:
            return 0
        
        caf = self.cafs[tipo_dte]
        folios_usados = self.folios_usados.get(tipo_dte, set())
        
        total_folios = caf['hasta'] - caf['desde'] + 1
        return total_folios - len(folios_usados)
    
    def verificar_vigencia(self, tipo_dte):
        """
        Verifica si el CAF está vigente
        
        Args:
            tipo_dte (int): Tipo de DTE
            
        Returns:
            bool: True si está vigente
        """
        if tipo_dte not in self.cafs:
            return False
        
        # Por ahora, solo verificar que tenga folios disponibles
        return self.folios_disponibles(tipo_dte) > 0
    
    def obtener_info_caf(self, tipo_dte):
        """
        Obtiene información del CAF
        
        Args:
            tipo_dte (int): Tipo de DTE
            
        Returns:
            dict: Información del CAF
        """
        if tipo_dte not in self.cafs:
            return None
        
        caf = self.cafs[tipo_dte]
        
        return {
            'tipo_dte': tipo_dte,
            'desde': caf['desde'],
            'hasta': caf['hasta'],
            'fecha_autorizacion': caf['fecha_autorizacion'],
            'folios_totales': caf['hasta'] - caf['desde'] + 1,
            'folios_disponibles': self.folios_disponibles(tipo_dte),
            'folios_usados': len(self.folios_usados.get(tipo_dte, set())),
        }
    
    def obtener_xml_caf(self, tipo_dte):
        """
        Obtiene el XML del CAF
        
        Args:
            tipo_dte (int): Tipo de DTE
            
        Returns:
            str: XML del CAF
        """
        if tipo_dte not in self.cafs:
            return None
        
        return self.cafs[tipo_dte]['xml']
