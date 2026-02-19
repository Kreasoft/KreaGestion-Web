import os
import re

# Leer el XML generado
xml_file = r'C:\PROJECTOS-WEB\GestionCloud\logs\dtebox_debug\test_guia_xml.xml'

html_output = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Verificación XML Guía de Despacho</title>
    <style>
        body { font-family: 'Courier New', monospace; padding: 20px; background: #1e1e1e; color: #d4d4d4; }
        h1 { color: #4ec9b0; }
        h2 { color: #569cd6; margin-top: 30px; }
        .success { color: #4ec9b0; }
        .error { color: #f48771; }
        .warning { color: #ce9178; }
        pre { background: #252526; padding: 15px; border-left: 3px solid #007acc; overflow-x: auto; }
        .check { margin: 10px 0; padding: 10px; background: #252526; border-radius: 4px; }
    </style>
</head>
<body>
"""

if os.path.exists(xml_file):
    with open(xml_file, 'r', encoding='ISO-8859-1') as f:
        xml_content = f.read()
    
    html_output += "<h1>✅ VERIFICACIÓN DEL XML GENERADO PARA GUÍA DE DESPACHO</h1>"
    
    # Mostrar primeras líneas
    lines = xml_content.split('\n')
    html_output += "<h2>📄 PRIMERAS 40 LÍNEAS DEL XML:</h2>"
    html_output += "<pre>"
    for i, line in enumerate(lines[:40], 1):
        html_output += f"{i:3}: {line.replace('<', '&lt;').replace('>', '&gt;')}\n"
    html_output += "</pre>"
    
    # Verificaciones
    html_output += "<h2>🔍 VERIFICACIONES CRÍTICAS:</h2>"
    
    checks = [
        (r'<DTE.*version="1\.0"', 'DTE con version 1.0', True),
        (r'<Documento ID="F\d+T52"', 'ID correcto (F{folio}T52)', True),
        (r'<IndTraslado>(\d+)</IndTraslado>', 'IndTraslado en IdDoc', True),
        (r'<RznSoc>', 'RznSoc (no RznSocEmisor)', True),
        (r'<GiroEmis>', 'GiroEmis (no GiroEmisor)', True),
        (r'<Transporte>', 'Transporte (NO debería estar)', False),
    ]
    
    for pattern, message, should_exist in checks:
        match = re.search(pattern, xml_content)
        if match:
            if should_exist:
                html_output += f'<div class="check success">✓ {message}'
                if 'IndTraslado' in pattern:
                    html_output += f' → Valor: <strong>{match.group(1)}</strong>'
                html_output += '</div>'
            else:
                html_output += f'<div class="check error">✗ {message} - ENCONTRADO (debería estar AUSENTE)</div>'
        else:
            if should_exist:
                html_output += f'<div class="check error">✗ {message} - NO ENCONTRADO</div>'
            else:
                html_output += f'<div class="check success">✓ {message} - AUSENTE (correcto)</div>'
    
    # Resumen
    html_output += "<h2>📊 RESUMEN:</h2>"
    html_output += f"<div class='check'><strong>Tamaño del XML:</strong> {len(xml_content)} caracteres</div>"
    html_output += f"<div class='check'><strong>Archivo:</strong> {xml_file}</div>"
    
    # Mostrar XML completo
    html_output += "<h2>📝 XML COMPLETO:</h2>"
    html_output += "<pre style='max-height: 600px; overflow-y: auto;'>"
    html_output += xml_content.replace('<', '&lt;').replace('>', '&gt;')
    html_output += "</pre>"
    
else:
    html_output += f"<h1 class='error'>❌ No se encontró el archivo: {xml_file}</h1>"

html_output += """
</body>
</html>
"""

# Guardar HTML
output_file = r'C:\PROJECTOS-WEB\GestionCloud\verificacion_xml.html'
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(html_output)

print(f"✅ Reporte generado: {output_file}")
print(f"   Abre este archivo en tu navegador para ver los resultados")
