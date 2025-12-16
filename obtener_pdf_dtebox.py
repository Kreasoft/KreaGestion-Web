#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para obtener PDF de un documento desde DTEBox
Factura tipo 33, folio 3233 - Ambiente Producción
"""
import os
import sys
import django
import requests
import base64
import json

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from empresas.models import Empresa

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def print_header(title):
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80)

def obtener_pdf_dtebox():
    """
    Obtiene el PDF de una factura desde DTEBox
    """
    print_header("OBTENER PDF DESDE DTEBox")
    
    # Datos de la factura
    tipo_dte = 33  # Factura
    folio = 3233
    ambiente = "P"  # Producción
    
    print(f"\nDatos del documento:")
    print(f"  Tipo DTE: {tipo_dte} (Factura)")
    print(f"  Folio: {folio}")
    print(f"  Ambiente: {ambiente} (Producción)")
    
    # Obtener empresa
    try:
        empresa = Empresa.objects.filter(dtebox_habilitado=True).first()
        
        if not empresa:
            empresa = Empresa.objects.first()
            if not empresa:
                print("\n[ERROR] No se encontró ninguna empresa")
                return
        
        # Configurar DTEBox si no está configurado
        if not empresa.dtebox_habilitado or not empresa.dtebox_url or not empresa.dtebox_auth_key:
            print("\n[INFO] Configurando DTEBox con datos de acceso...")
            empresa.dtebox_habilitado = True
            empresa.dtebox_url = "http://200.6.118.43/api/Core.svc/Core"
            empresa.dtebox_auth_key = "0a1c295d-7853-4e2e-ac90-d7d2fd46ecf0"
            empresa.dtebox_ambiente = ambiente
            empresa.save()
        
        print(f"\nEmpresa: {empresa.nombre}")
        print(f"RUT: {empresa.rut}")
        print(f"URL DTEBox: {empresa.dtebox_url}")
        print(f"Auth Key: {empresa.dtebox_auth_key[:20]}...")
        print(f"Ambiente: {empresa.dtebox_ambiente}")
        
        # Construir URL base y endpoint según la documentación proporcionada
        # Formato: http://[ip-dtebox]/api/Core.svc/core/RecoverPDF_V2/P/E/777117239-3/33/3233
        url_base = empresa.dtebox_url.strip().rstrip('/')
        
        # Normalizar URL base para construir el endpoint correcto
        # La URL base puede ser: http://200.6.118.43/api/Core.svc/Core
        # Necesitamos: http://200.6.118.43/api/Core.svc/core/RecoverPDF_V2/P/E/RUT/TipoDTE/Folio
        
        # Extraer la IP/base del servidor
        if '/api/Core.svc' in url_base or '/api/core.svc' in url_base:
            # Extraer hasta /api/Core.svc
            base_url = url_base.split('/api/')[0] + '/api/Core.svc'
        else:
            base_url = url_base
        
        # Normalizar a minúsculas en /core
        base_url = base_url.replace('/Core.svc/Core', '/Core.svc/core').replace('/core.svc/core', '/Core.svc/core')
        
        # Formatear RUT: quitar puntos pero mantener guión
        rut_formateado = empresa.rut.replace('.', '').replace('-', '-')  # Mantener formato con guión
        
        # Construir endpoint completo
        endpoint = f"{base_url}/core/RecoverPDF_V2/{ambiente}/E/{rut_formateado}/{tipo_dte}/{folio}"
        
        print(f"\nURL base normalizada: {base_url}")
        print(f"RUT formateado: {rut_formateado}")
        print(f"Endpoint completo: {endpoint}")
        
        # Headers con AuthKey
        headers = {
            'AuthKey': empresa.dtebox_auth_key,
            'Accept': 'application/pdf, application/json, */*'
        }
        
        print(f"\nIntentando obtener PDF...")
        print(f"Headers: AuthKey = {empresa.dtebox_auth_key[:20]}...")
        
        pdf_obtenido = False
        
        try:
            # Intentar con GET (endpoint con parámetros en la URL)
            print(f"\n[SOLICITUD] GET {endpoint}")
            response = requests.get(
                endpoint,
                headers=headers,
                timeout=30,
                verify=False
            )
                
            print(f"  Status Code: {response.status_code}")
            print(f"  Content-Type: {response.headers.get('Content-Type', 'N/A')}")
            print(f"  Content-Length: {len(response.content)} bytes")
            
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '').lower()
                
                # Verificar si la respuesta es un PDF
                if 'application/pdf' in content_type or 'pdf' in content_type:
                    print(f"  ✅ PDF obtenido exitosamente!")
                    
                    # Guardar PDF
                    nombre_archivo = f"factura_{tipo_dte}_{folio}.pdf"
                    with open(nombre_archivo, 'wb') as f:
                        f.write(response.content)
                    
                    print(f"  📄 PDF guardado como: {nombre_archivo}")
                    print(f"  📊 Tamaño: {len(response.content)} bytes ({len(response.content)/1024:.2f} KB)")
                    pdf_obtenido = True
                
                # Si la respuesta es JSON, puede contener el PDF en Base64
                elif 'application/json' in content_type:
                    try:
                        json_response = response.json()
                        print(f"  Respuesta JSON recibida:")
                        print(f"  {json.dumps(json_response, indent=2)[:500]}...")
                        
                        # Buscar campo PDF o Content en Base64
                        pdf_base64 = None
                        for key in ['PDF', 'Content', 'Document', 'File', 'Data']:
                            if key in json_response:
                                pdf_base64 = json_response[key]
                                break
                        
                        if pdf_base64:
                            pdf_bytes = base64.b64decode(pdf_base64)
                            nombre_archivo = f"factura_{tipo_dte}_{folio}.pdf"
                            with open(nombre_archivo, 'wb') as f:
                                f.write(pdf_bytes)
                            
                            print(f"  ✅ PDF obtenido desde Base64!")
                            print(f"  📄 PDF guardado como: {nombre_archivo}")
                            print(f"  📊 Tamaño: {len(pdf_bytes)} bytes ({len(pdf_bytes)/1024:.2f} KB)")
                            pdf_obtenido = True
                        else:
                            print(f"  ⚠️ No se encontró campo PDF/Content en la respuesta JSON")
                    except json.JSONDecodeError as e:
                        print(f"  ⚠️ Error al parsear JSON: {str(e)}")
                        print(f"  Respuesta (primeros 500 chars): {response.text[:500]}")
                
                # Si la respuesta es texto, puede ser Base64
                elif 'text' in content_type:
                    try:
                        pdf_base64 = response.text.strip()
                        pdf_bytes = base64.b64decode(pdf_base64)
                        nombre_archivo = f"factura_{tipo_dte}_{folio}.pdf"
                        with open(nombre_archivo, 'wb') as f:
                            f.write(pdf_bytes)
                        
                        print(f"  ✅ PDF obtenido desde Base64 (texto)!")
                        print(f"  📄 PDF guardado como: {nombre_archivo}")
                        print(f"  📊 Tamaño: {len(pdf_bytes)} bytes ({len(pdf_bytes)/1024:.2f} KB)")
                        pdf_obtenido = True
                    except Exception as e:
                        print(f"  ⚠️ No se pudo decodificar como Base64: {str(e)}")
                        print(f"  Respuesta (primeros 200 chars): {response.text[:200]}")
                
                # Si es binario pero no PDF reconocido, intentar guardar como PDF
                elif len(response.content) > 0:
                    # Verificar si es PDF por la firma mágica
                    if response.content[:4] == b'%PDF':
                        nombre_archivo = f"factura_{tipo_dte}_{folio}.pdf"
                        with open(nombre_archivo, 'wb') as f:
                            f.write(response.content)
                        
                        print(f"  ✅ PDF obtenido (detectado por firma PDF)!")
                        print(f"  📄 PDF guardado como: {nombre_archivo}")
                        print(f"  📊 Tamaño: {len(response.content)} bytes ({len(response.content)/1024:.2f} KB)")
                        pdf_obtenido = True
                    else:
                        print(f"  ⚠️ Tipo de contenido no reconocido: {content_type}")
                        print(f"  Primeros bytes (hex): {response.content[:50].hex()}")
                        print(f"  Primeros 200 caracteres de la respuesta:")
                        try:
                            print(f"  {response.text[:200]}")
                        except:
                            print(f"  (No se puede decodificar como texto)")
            
            elif response.status_code == 404:
                print(f"  ❌ Endpoint no encontrado (404)")
                print(f"  Verificar que la URL sea correcta")
            elif response.status_code == 401:
                print(f"  ❌ No autorizado (401) - Verificar AuthKey")
                print(f"  Respuesta: {response.text[:500]}")
            elif response.status_code == 403:
                print(f"  ❌ Prohibido (403) - Sin permisos para acceder al recurso")
                print(f"  Respuesta: {response.text[:500]}")
            elif response.status_code == 500:
                print(f"  ❌ Error del servidor (500)")
                print(f"  Respuesta: {response.text[:500]}")
            else:
                print(f"  ⚠️ Status code no esperado: {response.status_code}")
                print(f"  Respuesta: {response.text[:500]}")
        
        except requests.exceptions.ConnectionError:
            print(f"  ❌ Error de conexión - El servidor no responde")
            print(f"  Verificar que el servidor DTEBox esté accesible")
        except requests.exceptions.Timeout:
            print(f"  ❌ Timeout - El servidor tardó demasiado en responder")
        except Exception as e:
            print(f"  ❌ Error inesperado: {str(e)}")
            import traceback
            traceback.print_exc()
        
        if not pdf_obtenido:
            print("\n" + "=" * 80)
            print("⚠️ NO SE PUDO OBTENER EL PDF".center(80))
            print("=" * 80)
            print("\nPosibles causas:")
            print("1. El endpoint para obtener PDF puede ser diferente")
            print("2. Los parámetros del request pueden ser diferentes")
            print("3. Puede requerir autenticación adicional")
            print("4. El documento puede no existir en el servidor DTEBox")
            print("\nPor favor, proporciona:")
            print("- El endpoint exacto para obtener PDFs")
            print("- El formato del request requerido")
            print("- Los parámetros necesarios (RUT, Tipo DTE, Folio, etc.)")
            print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print("✅ PDF OBTENIDO EXITOSAMENTE".center(80))
            print("=" * 80)
    
    except Exception as e:
        print(f"\n[ERROR] Error inesperado: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    obtener_pdf_dtebox()

