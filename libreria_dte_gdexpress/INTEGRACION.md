# 🔗 Guía de Integración - DTE GDExpress

Esta guía te ayudará a integrar el paquete `dte_gdexpress` en tu proyecto Django existente.

## 📋 Requisitos Previos

- Proyecto Django 3.2 o superior
- Python 3.8 o superior
- Certificado digital (.pfx/.p12)
- API Key de GDExpress/DTEBox
- Archivos CAF descargados del SII

## 🚀 Integración Paso a Paso

### 1. Instalación

```bash
pip install dte-gdexpress
```

### 2. Configuración en settings.py

```python
# settings.py

INSTALLED_APPS = [
    ...
    'dte_gdexpress',  # Solo si usarás los modelos Django
]

# Configuración DTE GDExpress
DTE_GDEXPRESS = {
    'API_KEY': os.getenv('GDEXPRESS_API_KEY'),
    'AMBIENTE': os.getenv('DTE_AMBIENTE', 'CERTIFICACION'),
    'URL_SERVICIO': 'http://200.6.118.43/api/Core.svc/Core',
    'CERTIFICADO_PATH': os.path.join(BASE_DIR, 'certificados', 'certificado.pfx'),
    'CERTIFICADO_PASSWORD': os.getenv('CERT_PASSWORD'),
    'CAF_DIRECTORY': os.path.join(BASE_DIR, 'folios'),
}
```

### 3. Crear Vista para Emitir Factura

```python
# views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from dte_gdexpress import GeneradorFactura, Firmador, ClienteGDExpress, GestorCAF
from django.conf import settings

def emitir_factura(request):
    if request.method == 'POST':
        try:
            # 1. Obtener folio
            gestor_caf = GestorCAF(settings.DTE_GDEXPRESS['CAF_DIRECTORY'])
            gestor_caf.cargar_todos_los_cafs()
            folio = gestor_caf.obtener_siguiente_folio(tipo_dte=33)
            
            # 2. Generar factura
            factura = GeneradorFactura(
                folio=folio,
                fecha=request.POST['fecha'],
                rut_emisor=request.POST['rut_emisor'],
                razon_social_emisor=request.POST['razon_social_emisor'],
                giro_emisor=request.POST['giro_emisor'],
                direccion_emisor=request.POST['direccion_emisor'],
                comuna_emisor=request.POST['comuna_emisor'],
                rut_receptor=request.POST['rut_receptor'],
                razon_social_receptor=request.POST['razon_social_receptor'],
                direccion_receptor=request.POST['direccion_receptor'],
                comuna_receptor=request.POST['comuna_receptor'],
                items=request.POST.getlist('items'),  # Procesar items
            )
            
            xml = factura.generar_xml()
            
            # 3. Firmar
            firmador = Firmador(
                certificado_path=settings.DTE_GDEXPRESS['CERTIFICADO_PATH'],
                password=settings.DTE_GDEXPRESS['CERTIFICADO_PASSWORD']
            )
            xml_firmado = firmador.firmar(xml)
            
            # 4. Enviar a GDExpress
            cliente = ClienteGDExpress(
                api_key=settings.DTE_GDEXPRESS['API_KEY'],
                ambiente=settings.DTE_GDEXPRESS['AMBIENTE']
            )
            resultado = cliente.enviar_dte(xml_firmado)
            
            if resultado['success']:
                # Marcar folio como usado
                gestor_caf.marcar_folio_usado(tipo_dte=33, folio=folio)
                
                messages.success(request, f"Factura {folio} emitida exitosamente. Track ID: {resultado['track_id']}")
                return redirect('lista_facturas')
            else:
                messages.error(request, f"Error al emitir factura: {resultado['error']}")
        
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    return render(request, 'facturacion/emitir_factura.html')
```

### 4. Crear Template

```html
<!-- templates/facturacion/emitir_factura.html -->
{% extends 'base.html' %}

{% block content %}
<div class="container">
    <h2>Emitir Factura Electrónica</h2>
    
    <form method="post">
        {% csrf_token %}
        
        <h3>Datos del Emisor</h3>
        <input type="text" name="rut_emisor" placeholder="RUT Emisor" required>
        <input type="text" name="razon_social_emisor" placeholder="Razón Social" required>
        <input type="text" name="giro_emisor" placeholder="Giro">
        <input type="text" name="direccion_emisor" placeholder="Dirección">
        <input type="text" name="comuna_emisor" placeholder="Comuna">
        
        <h3>Datos del Receptor</h3>
        <input type="text" name="rut_receptor" placeholder="RUT Receptor" required>
        <input type="text" name="razon_social_receptor" placeholder="Razón Social" required>
        <input type="text" name="direccion_receptor" placeholder="Dirección">
        <input type="text" name="comuna_receptor" placeholder="Comuna">
        
        <h3>Items</h3>
        <!-- Agregar campos para items -->
        
        <button type="submit">Emitir Factura</button>
    </form>
</div>
{% endblock %}
```

### 5. Configurar URLs

```python
# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('facturacion/emitir/', views.emitir_factura, name='emitir_factura'),
]
```

## 📊 Uso Avanzado

### Sincronizar Documentos Recibidos

```python
# views.py
def sincronizar_documentos_recibidos(request):
    try:
        cliente = ClienteGDExpress(
            api_key=settings.DTE_GDEXPRESS['API_KEY'],
            ambiente=settings.DTE_GDEXPRESS['AMBIENTE']
        )
        
        documentos = cliente.obtener_documentos_recibidos(
            rut_receptor='77117239-3',
            dias=30
        )
        
        # Guardar en base de datos
        for doc in documentos:
            # Procesar y guardar documento
            pass
        
        messages.success(request, f"Se sincronizaron {len(documentos)} documentos")
    
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
    
    return redirect('lista_documentos_recibidos')
```

### Consultar Estado de DTE

```python
def consultar_estado_dte(request, track_id):
    cliente = ClienteGDExpress(
        api_key=settings.DTE_GDEXPRESS['API_KEY'],
        ambiente=settings.DTE_GDEXPRESS['AMBIENTE']
    )
    
    estado = cliente.consultar_estado(track_id)
    
    return render(request, 'facturacion/estado_dte.html', {'estado': estado})
```

## 🔧 Comandos de Gestión Django (Opcional)

Si quieres crear comandos de gestión:

```python
# management/commands/emitir_factura.py
from django.core.management.base import BaseCommand
from dte_gdexpress import GeneradorFactura, Firmador, ClienteGDExpress

class Command(BaseCommand):
    help = 'Emite una factura electrónica'
    
    def handle(self, *args, **options):
        # Lógica de emisión
        pass
```

## 📝 Mejores Prácticas

1. **Usar variables de entorno** para credenciales sensibles
2. **Validar datos** antes de generar XML
3. **Guardar XMLs** en base de datos para auditoría
4. **Manejar errores** apropiadamente
5. **Implementar logs** para debugging
6. **Usar transacciones** para operaciones críticas

## 🐛 Debugging

Para activar logs detallados:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('dte_gdexpress')
```

## 📞 Soporte

- Email: soporte@kreasoft.cl
- Issues: [GitHub](https://github.com/Kreasoft/dte_gdexpress/issues)
