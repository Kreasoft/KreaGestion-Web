#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para configurar los datos de resolución en la empresa
"""
import os
import sys
import django
from datetime import date

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa

def configurar_resolucion():
    """
    Configura los datos de resolución en la empresa
    """
    print("=" * 80)
    print("CONFIGURACIÓN DE DATOS DE RESOLUCIÓN")
    print("=" * 80)
    print()
    
    try:
        # Buscar empresa (usar la primera o la empresa activa)
        empresa = Empresa.objects.first()
        
        if not empresa:
            print("ERROR: No se encontró ninguna empresa en la base de datos")
            return
        
        print(f"Empresa: {empresa.nombre}")
        print()
        
        # Datos proporcionados por el usuario
        resolucion_numero = 80
        resolucion_fecha = date(2014, 8, 22)  # 22-08-2014
        
        print("Configurando datos de resolución:")
        print(f"  Número: {resolucion_numero}")
        print(f"  Fecha: {resolucion_fecha.strftime('%d-%m-%Y')} ({resolucion_fecha.strftime('%Y-%m-%d')})")
        print()
        
        # Actualizar empresa
        empresa.resolucion_numero = resolucion_numero
        empresa.resolucion_fecha = resolucion_fecha
        empresa.save()
        
        print("[OK] Datos de resolución configurados exitosamente")
        print()
        print("Estos datos se usarán al enviar documentos a DTEBox:")
        print(f"  ResolutionDate: {resolucion_fecha.strftime('%Y-%m-%d')}")
        print(f"  ResolutionNumber: {resolucion_numero}")
        print()
        print("=" * 80)
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Configurar encoding para Windows
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    configurar_resolucion()







