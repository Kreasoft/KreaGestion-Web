import re

# Leer archivo
with open(r'c:\PROJECTOS-WEB\GestionCloud\templates\empresas\editar_empresa_activa.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Lista de documentos a actualizar (sin Factura que ya la hicimos)
documentos = [
    ('boleta', 'Boleta Electrónica', 'fa-receipt'),
    ('guia', 'Guía de Despacho', 'fa-truck'),
    ('nota_credito', 'Nota de Crédito', 'fa-file-excel'),
    ('nota_debito', 'Nota de Débito', 'fa-file-invoice-dollar'),
]

for doc_type, doc_name, icon in documentos:
    #

 Patrón para encontrar la sección del documento
    pattern = rf'(<label class="fw-bold mb-2">.*?<i class="{icon} me-2"></i>{doc_name}.*?</label>.*?<div class="d-flex gap-3 mb-2">.*?</div>.*?<div>.*?<select.*?</select>.*?</div>)'
    
    # Reemplazo con 3 opciones y sin dropdown
    replacement = f'''<label class="fw-bold mb-2">
                                                    <i class="{icon} me-2"></i>{doc_name}
                                                </label>
                                                <div class="d-flex gap-3 mb-2">
                                                    <div class="form-check">
                                                        <input class="form-check-input" type="radio" name="impresora_{doc_type}" id="{doc_type}_laser" value="laser" {{% if empresa.impresora_{doc_type} == 'laser' %}}checked{{% endif %}}>
                                                        <label class="form-check-label" for="{doc_type}_laser">
                                                            <i class="fas fa-desktop me-1"></i>Láser
                                                        </label>
                                                    </div>
                                                    <div class="form-check">
                                                        <input class="form-check-input" type="radio" name="impresora_{doc_type}" id="{doc_type}_termica80" value="termica_80" {{% if empresa.impresora_{doc_type} == 'termica_80' or empresa.impresora_{doc_type} == 'termica' %}}checked{{% endif %}}>
                                                        <label class="form-check-label" for="{doc_type}_termica80">
                                                            <i class="fas fa-receipt me-1"></i>Térmica 80mm
                                                        </label>
                                                    </div>
                                                    <div class="form-check">
                                                        <input class="form-check-input" type="radio" name="impresora_{doc_type}" id="{doc_type}_termica58" value="termica_58" {{% if empresa.impresora_{doc_type} == 'termica_58' %}}checked{{% endif %}}>
                                                        <label class="form-check-label" for="{doc_type}_termica58">
                                                            <i class="fas fa-receipt me-1"></i>Térmica 58mm
                                                        </label>
                                                    </div>
                                                </div>'''
    
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Guardar archivo
with open(r'c:\PROJECTOS-WEB\GestionCloud\templates\empresas\editar_empresa_activa.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Actualización completada")
