"""
Parche temporal para compatibilidad con Python 3.13
El módulo cgi fue removido en Python 3.13, pero zeep lo necesita
"""
import sys

# Parche para Python 3.13: usar legacy-cgi si cgi no está disponible
if 'cgi' not in sys.modules:
    try:
        import legacy_cgi as cgi
        sys.modules['cgi'] = cgi
    except ImportError:
        pass

