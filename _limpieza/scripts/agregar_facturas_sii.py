import re

# Leer el archivo sin modificar el encoding
with open('templates/base.html', 'r', encoding='utf-8', newline='') as f:
    content = f.read()

# Buscar y reemplazar SOLO después de Órdenes de Compra
pattern = r"(Órdenes de Compra</span>\s*</a>\s*{% endif %}\s*)(<!-- Configuración -->)"
replacement = r'\1<a href="{% url \'compras:facturas_recibidas_sii\' %}" class="nav-link submenu-link {% if \'facturas-sii\' in request.path %}active{% endif %}">\r\n                            <i class="fas fa-cloud-download-alt me-2" style="color: #8B7355;"></i>\r\n                            <span>Facturas SII</span>\r\n                        </a>\r\n                        \r\n                        \2'

content_new = re.sub(pattern, replacement, content, count=1)

# Escribir sin modificar nada más
with open('templates/base.html', 'w', encoding='utf-8', newline='') as f:
    f.write(content_new)

print("LISTO - Enlace agregado")
