#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para validar el XML del DTE y explicar los datos de resolución
"""
import os
import sys
import django
from lxml import etree

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa


def validar_xml_dte(xml_string):
    """
    Valida la estructura básica del XML del DTE
    """
    print("=" * 80)
    print("VALIDACIÓN DEL XML DEL DTE")
    print("=" * 80)
    print()
    
    try:
        # Parsear XML
        root = etree.fromstring(xml_string.encode('ISO-8859-1'))
        
        print("[OK] El XML está bien formado (sintaxis correcta)")
        print()
        
        # Verificar elementos principales
        print("Elementos encontrados en el XML:")
        print("-" * 80)
        
        # Buscar DTE
        dte = root.find('.//{http://www.sii.cl/SiiDte}DTE') or root.find('.//DTE')
        if dte is not None:
            print(f"  [OK] Elemento DTE encontrado")
            print(f"       Versión: {dte.get('version', 'No especificada')}")
        else:
            print(f"  [ERROR] No se encontró elemento DTE")
        
        # Buscar Encabezado
        encabezado = root.find('.//{http://www.sii.cl/SiiDte}Encabezado') or root.find('.//Encabezado')
        if encabezado is not None:
            print(f"  [OK] Elemento Encabezado encontrado")
        else:
            print(f"  [ADVERTENCIA] No se encontró elemento Encabezado")
        
        # Buscar IdDoc
        iddoc = root.find('.//{http://www.sii.cl/SiiDte}IdDoc') or root.find('.//IdDoc')
        if iddoc is not None:
            print(f"  [OK] Elemento IdDoc encontrado")
            tipo_dte = iddoc.find('.//{http://www.sii.cl/SiiDte}TipoDTE') or iddoc.find('.//TipoDTE')
            folio = iddoc.find('.//{http://www.sii.cl/SiiDte}Folio') or iddoc.find('.//Folio')
            if tipo_dte is not None:
                print(f"       Tipo DTE: {tipo_dte.text}")
            if folio is not None:
                print(f"       Folio: {folio.text}")
        else:
            print(f"  [ERROR] No se encontró elemento IdDoc")
        
        # Buscar Emisor
        emisor = root.find('.//{http://www.sii.cl/SiiDte}Emisor') or root.find('.//Emisor')
        if emisor is not None:
            print(f"  [OK] Elemento Emisor encontrado")
            rut = emisor.find('.//{http://www.sii.cl/SiiDte}RUTEmisor') or emisor.find('.//RUTEmisor')
            if rut is not None:
                print(f"       RUT Emisor: {rut.text}")
        else:
            print(f"  [ERROR] No se encontró elemento Emisor")
        
        # Buscar Receptor
        receptor = root.find('.//{http://www.sii.cl/SiiDte}Receptor') or root.find('.//Receptor')
        if receptor is not None:
            print(f"  [OK] Elemento Receptor encontrado")
        else:
            print(f"  [ADVERTENCIA] No se encontró elemento Receptor")
        
        # Buscar Totales
        totales = root.find('.//{http://www.sii.cl/SiiDte}Totales') or root.find('.//Totales')
        if totales is not None:
            print(f"  [OK] Elemento Totales encontrado")
        else:
            print(f"  [ERROR] No se encontró elemento Totales")
        
        # Buscar TED
        ted = root.find('.//{http://www.sii.cl/SiiDte}TED') or root.find('.//TED')
        if ted is not None:
            print(f"  [OK] Elemento TED encontrado")
            dd = ted.find('.//{http://www.sii.cl/SiiDte}DD') or ted.find('.//DD')
            if dd is not None:
                if dd.text and dd.text.strip():
                    print(f"       [ADVERTENCIA] El TED tiene contenido (ya está timbrado)")
                else:
                    print(f"       [OK] El TED está vacío (listo para timbrar)")
        else:
            print(f"  [ADVERTENCIA] No se encontró elemento TED")
        
        print()
        print("=" * 80)
        print("NOTA: Esta validación solo verifica la estructura básica del XML.")
        print("Para una validación completa según el esquema del SII, se requiere")
        print("validar contra el XSD oficial del SII.")
        print("=" * 80)
        
        return True
        
    except etree.XMLSyntaxError as e:
        print(f"[ERROR] El XML tiene errores de sintaxis:")
        print(f"        {str(e)}")
        return False
    except Exception as e:
        print(f"[ERROR] Error al validar XML: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def explicar_datos_resolucion():
    """
    Explica qué son los datos de resolución y por qué deben coincidir
    """
    print()
    print("=" * 80)
    print("¿QUÉ SON LOS DATOS DE RESOLUCIÓN?")
    print("=" * 80)
    print()
    
    print("Los datos de resolución son:")
    print()
    print("1. ResolutionDate (Fecha de Resolución):")
    print("   - Es la fecha en que el SII autorizó a tu empresa a emitir")
    print("     documentos tributarios electrónicos")
    print("   - Formato: YYYY-MM-DD (ejemplo: 2019-01-01)")
    print()
    print("2. ResolutionNumber (Número de Resolución):")
    print("   - Es el número de la resolución del SII que autoriza a tu empresa")
    print("   - Ejemplo: 80, 123, 456, etc.")
    print()
    print("=" * 80)
    print("¿POR QUÉ DEBEN COINCIDIR?")
    print("=" * 80)
    print()
    print("El servidor DTEBox tiene configurado en su base de datos:")
    print("  - La resolución autorizada para tu empresa")
    print("  - La fecha de esa resolución")
    print()
    print("Cuando envías un documento a DTEBox, el servidor verifica que:")
    print("  ✓ Los datos de resolución que envías coincidan con los que tiene")
    print("    configurados para tu empresa")
    print()
    print("Si NO coinciden, el servidor rechazará la petición con error 500")
    print("porque considera que estás intentando usar una resolución no")
    print("autorizada para tu empresa.")
    print()
    print("=" * 80)
    print("EJEMPLO:")
    print("=" * 80)
    print()
    print("Si tu empresa tiene autorización:")
    print("  Resolución N° 123 del 15-01-2024")
    print()
    print("Debes enviar a DTEBox:")
    print("  ResolutionDate: 2024-01-15")
    print("  ResolutionNumber: 123")
    print()
    print("Si envías:")
    print("  ResolutionDate: 2019-01-01  ← INCORRECTO")
    print("  ResolutionNumber: 80         ← INCORRECTO")
    print()
    print("El servidor DTEBox rechazará porque esos datos no coinciden con")
    print("los que tiene configurados para tu empresa.")
    print()


def mostrar_resolucion_empresa():
    """
    Muestra la resolución configurada en la empresa
    """
    print()
    print("=" * 80)
    print("RESOLUCIÓN CONFIGURADA EN TU EMPRESA")
    print("=" * 80)
    print()
    
    try:
        empresa = Empresa.objects.first()
        if empresa:
            print(f"Empresa: {empresa.nombre}")
            print()
            
            if empresa.resolucion_numero:
                print(f"  Número de Resolución: {empresa.resolucion_numero}")
            else:
                print(f"  Número de Resolución: [NO CONFIGURADO]")
            
            if empresa.resolucion_fecha:
                print(f"  Fecha de Resolución: {empresa.resolucion_fecha.strftime('%Y-%m-%d')}")
            else:
                print(f"  Fecha de Resolución: [NO CONFIGURADO]")
            
            print()
            print("=" * 80)
            print("RECOMENDACIÓN:")
            print("=" * 80)
            print()
            
            if empresa.resolucion_numero and empresa.resolucion_fecha:
                print("Estos son los datos que se están enviando a DTEBox:")
                print(f"  ResolutionDate: {empresa.resolucion_fecha.strftime('%Y-%m-%d')}")
                print(f"  ResolutionNumber: {empresa.resolucion_numero}")
                print()
                print("Verifica que estos datos coincidan con los configurados")
                print("en el servidor DTEBox para tu empresa.")
            else:
                print("[ADVERTENCIA] Los datos de resolución no están configurados.")
                print("Debes configurarlos en:")
                print("  - Configuración de Empresa > Facturación Electrónica")
                print()
                print("O ejecutar el script de prueba con datos de ejemplo.")
        else:
            print("No se encontró ninguna empresa en la base de datos.")
    except Exception as e:
        print(f"Error al obtener datos de la empresa: {str(e)}")


if __name__ == "__main__":
    # Configurar encoding para Windows
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    # XML de prueba del script anterior
    xml_prueba = """<?xml version="1.0" encoding="ISO-8859-1"?>
<DTE version="1.0">
    <Exportaciones ID="F181T112">
        <Encabezado>
            <IdDoc>
                <TipoDTE>112</TipoDTE>
                <Folio>181</Folio>
                <FchEmis>2018-07-30</FchEmis>
            </IdDoc>
            <Emisor>
                <RUTEmisor>76123456-7</RUTEmisor>
                <RznSoc>EMPRESA DE PRUEBA</RznSoc>
            </Emisor>
            <Receptor>
                <RUTRecep>12345678-9</RUTRecep>
                <RznSocRecep>CLIENTE DE PRUEBA</RznSocRecep>
            </Receptor>
            <Totales>
                <MntTotal>10000</MntTotal>
            </Totales>
        </Encabezado>
        <Detalle>
            <NroLinDet>1</NroLinDet>
            <NmbItem>PRODUCTO DE PRUEBA</NmbItem>
            <QtyItem>1</QtyItem>
            <PrcItem>10000</PrcItem>
            <MntItem>10000</MntItem>
        </Detalle>
        <Documento>
            <TED version="1.0">
                <DD></DD>
                <FRMT algoritmo="SHA1withRSA"></FRMT>
            </TED>
        </Documento>
    </Exportaciones>
</DTE>"""
    
    # Validar XML
    validar_xml_dte(xml_prueba)
    
    # Explicar datos de resolución
    explicar_datos_resolucion()
    
    # Mostrar resolución de la empresa
    mostrar_resolucion_empresa()




