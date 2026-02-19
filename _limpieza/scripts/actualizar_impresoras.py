#!/usr/bin/env python
"""Script para actualizar valores de impresora de 'termica' a 'termica_80'"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa

def actualizar_impresoras():
    empresas = Empresa.objects.all()
    count = 0
    
    for empresa in empresas:
        changed = False
        
        # Actualizar cada campo de impresora
        if empresa.impresora_factura == 'termica':
            empresa.impresora_factura = 'termica_80'
            changed = True
        
        if empresa.impresora_boleta == 'termica':
            empresa.impresora_boleta = 'termica_80'
            changed = True
        
        if empresa.impresora_guia == 'termica':
            empresa.impresora_guia = 'termica_80'
            changed = True
        
        if empresa.impresora_nota_credito == 'termica':
            empresa.impresora_nota_credito = 'termica_80'
            changed = True
        
        if empresa.impresora_nota_debito == 'termica':
            empresa.impresora_nota_debito = 'termica_80'
            changed = True
        
        if empresa.impresora_vale == 'termica':
            empresa.impresora_vale = 'termica_80'
            changed = True
        
        if empresa.impresora_cotizacion == 'termica':
            empresa.impresora_cotizacion = 'termica_80'
            changed = True
        
        if changed:
            empresa.save()
            count += 1
            print(f"✅ Actualizada empresa: {empresa.nombre}")
    
    print(f"\n✅ Total: Actualizadas {count} empresas de 'termica' a 'termica_80'")

if __name__ == '__main__':
    actualizar_impresoras()
