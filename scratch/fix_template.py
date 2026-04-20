
import sys
import os

path = r'c:\PROJECTOS-WEB\GestionCloud\compras\templates\compras\orden_compra_form.html'
if not os.path.exists(path):
    print(f'Error: {path} not found')
    sys.exit(1)

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_line = -1
for i, line in enumerate(lines):
    if '<!-- Sección Items -->' in line:
        start_line = i
        break

if start_line != -1:
    new_tail = """             <!-- Sección Items -->
            <div class="d-flex justify-content-between align-items-center mt-4 mb-2">
                <h5 class="m-0 text-muted text-uppercase fs-6 fw-bold" style="color: var(--stone-primary) !important;">
                    <i class="fas fa-boxes me-2"></i> Items Orden
                </h5>
                <button type="button" class="btn-stone-primary btn-sm" id="addItemBtn">
                    <i class="fas fa-plus me-1"></i> Agregar Item
                </button>
            </div>
            
            <div class="items-list-compact">
                <!-- Header Tabla -->
                <div class="items-list-header row g-0">
                    <div class="col-4 ps-2">Artículo</div>
                    <div class="col-2 text-center">Cant</div>
                    <div class="col-2 text-end pe-2">Precio U.</div>
                    <div class="col-2 text-center">Desc %</div>
                    <div class="col-2 text-end pe-3">Total</div>
                </div>
                
                <!-- Body Tabla -->
                <div id="items-wrapper">
                    {% for item_form in formset %}
                        <div class="item-line item-row row g-0 align-items-center" data-form-index="{{ forloop.counter0 }}">
                            <div class="col-4 ps-2 pe-2">
                                <select name="{{ item_form.articulo.html_name }}" class="form-select articulo-select form-control-sm">
                                    <option value="">...</option>
                                    {% for articulo in articulos_empresa %}
                                        <option value="{{ articulo.id|unlocalize }}" 
                                                data-precio-costo="{% if articulo.precio_costo %}{{ articulo.precio_costo|unlocalize }}{% else %}0{% endif %}"
                                                {% if item_form.articulo.value|unlocalize == articulo.id|unlocalize %}selected{% endif %}>
                                            {{ articulo.codigo }} - {{ articulo.nombre|truncatechars:35 }}
                                        </option>
                                    {% endfor %}
                                </select>
                                {% for hidden in item_form.hidden_fields %}{{ hidden }}{% endfor %}
                                <!-- Asegurar envío de impuesto -->
                                <input type="hidden" name="{{ item_form.impuesto_porcentaje.html_name }}" value="{{ item_form.impuesto_porcentaje.value|default:19 }}">
                            </div>
                            <div class="col-2 px-1">
                                <input type="number" name="{{ item_form.cantidad_solicitada.html_name }}" value="{{ item_form.cantidad_solicitada.value|unlocalize|default:1 }}" class="form-control form-control-sm text-center cantidad-input" min="1">
                            </div>
                            <div class="col-2 px-1">
                                <input type="number" name="{{ item_form.precio_unitario.html_name }}" value="{{ item_form.precio_unitario.value|unlocalize|default:0 }}" class="form-control form-control-sm text-end precio-unitario-input" min="0">
                            </div>
                             <div class="col-2 px-1">
                                <input type="number" name="{{ item_form.descuento_porcentaje.html_name }}" value="{{ item_form.descuento_porcentaje.value|unlocalize|default:0 }}" class="form-control form-control-sm text-center descuento-input" min="0" max="100">
                            </div>
                            <div class="col-2 ps-1 pe-2 d-flex align-items-center">
                                <input type="text" class="subtotal-display form-control form-control-sm text-end item-total bg-transparent border-0 fw-bold" readonly value="0">
                                <button type="button" class="btn-stone-danger ms-2" onclick="eliminarItem(this)">
                                    <i class="fas fa-times"></i>
                                </button>
                            </div>
                        </div>
                    {% endfor %}
                </div>
            </div>

            <!-- Panel de Totales y Descuentos Globales -->
            <div class="row mt-4">
                <div class="col-md-7">
                    <div class="card border-0 shadow-sm p-3 mb-3" style="background: #fdfbf7; border-radius: 12px;">
                        <h6 class="text-uppercase fw-bold mb-3" style="font-size: 0.75rem; color: var(--stone-primary);">Opciones de Documento</h6>
                        <div class="row g-3">
                             <div class="col-md-6">
                                <label class="form-label">Condiciones de Pago</label>
                                {{ form.condiciones_pago }}
                             </div>
                             <div class="col-md-6">
                                <label class="form-label">Plazo de Entrega</label>
                                {{ form.plazo_entrega }}
                             </div>
                             <div class="col-12">
                                <label class="form-label">Observaciones</label>
                                {{ form.observaciones }}
                             </div>
                        </div>
                    </div>
                </div>

                <div class="col-md-5">
                    <div class="totals-panel shadow-sm">
                        <div class="total-row align-items-center mb-2">
                             <span>Subtotal Bruto Items:</span>
                             {{ form.subtotal }}
                        </div>

                        <div class="row mb-2 align-items-center g-2 bg-white p-2 rounded border border-light">
                             <div class="col-4">
                                <span class="small fw-bold text-muted">DESC. GLOBAL (%):</span>
                             </div>
                             <div class="col-3">
                                {{ form.descuento_global_porcentaje }}
                             </div>
                             <div class="col-5">
                                {{ form.descuento_global_monto }}
                             </div>
                        </div>

                        <div class="total-row align-items-center mb-2">
                             <span class="text-danger">Total Descuentos:</span>
                             {{ form.descuentos_totales }}
                        </div>

                        <hr class="my-2" style="border-color: var(--stone-light);">

                        <div class="total-row align-items-center mb-2">
                             <span class="fw-bold fs-6">MONTO NETO:</span>
                             {{ form.neto_ajustado }}
                        </div>

                        <div class="total-row align-items-center mb-2">
                             <span>IVA (19%):</span>
                             {{ form.iva_ajustado }}
                        </div>

                        <div class="total-row align-items-center mb-2">
                             <span>IMPUESTO ESP.:</span>
                             {{ form.impuesto_especifico }}
                        </div>

                        <div class="total-row final align-items-center">
                             <span>TOTAL:</span>
                             {{ form.total_orden }}
                        </div>
                    </div>
                    
                    <button type="submit" class="btn-stone-primary w-100 mt-3 py-2 fs-5">
                        <i class="fas fa-save me-2"></i> GUARDAR COMPRA
                    </button>
                    <p class="text-center text-muted mt-2 small">
                        <i class="fas fa-info-circle me-1"></i> Los totales son editables para cuadrar diferencias.
                    </p>
                </div>
            </div>
        </form>
        </div>
    </div>
</div>

<!-- Template Oculto -->
<div id="empty-form-template" style="display:none;">
    <div class="item-line item-row row g-0 align-items-center" data-form-index="__prefix__">
        <div class="col-4 ps-2 pe-2">
            <input type="hidden" name="items-__prefix__-impuesto_porcentaje" value="19">
            <select name="items-__prefix__-articulo" class="form-select articulo-select form-control-sm">
                <option value="">...</option>
                {% for articulo in articulos_empresa %}
                    <option value="{{ articulo.id|unlocalize }}" data-precio-costo="{% if articulo.precio_costo %}{{ articulo.precio_costo|unlocalize }}{% else %}0{% endif %}">
                        {{ articulo.codigo }} - {{ articulo.nombre|truncatechars:35 }}
                    </option>
                {% endfor %}
            </select>
        </div>
        <div class="col-2 px-1"><input type="number" name="items-__prefix__-cantidad_solicitada" class="form-control form-control-sm text-center" value="1"></div>
        <div class="col-2 px-1"><input type="number" name="items-__prefix__-precio_unitario" class="form-control form-control-sm text-end" value="0"></div>
        <div class="col-2 px-1"><input type="number" name="items-__prefix__-descuento_porcentaje" class="form-control form-control-sm text-center" value="0"></div>
        <div class="col-2 ps-1 pe-2 d-flex align-items-center">
            <input type="text" class="form-control form-control-sm text-end item-total bg-transparent border-0 fw-bold" readonly placeholder="0">
            <button type="button" class="btn-stone-danger ms-2" onclick="eliminarItem(this)">
                <i class="fas fa-times"></i>
            </button>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>

<script>
    $(document).ready(function() {
        function initSelect2Global() {
            $('.form-select').not('#empty-form-template .form-select').each(function() {
                if (!$(this).hasClass('select2-hidden-accessible')) {
                    $(this).select2({ theme: 'default', width: '100%', placeholder: 'Seleccione...' });
                }
            });
        }
        initSelect2Global();

        let manualAdjust = false;

        function calcularTotales() {
            let subtotalBrutoItems = 0;
            let totalDescuentoItems = 0;
            
            $('.item-line:visible').each(function() {
                if($(this).closest('#empty-form-template').length > 0) return;
                const formIdx = $(this).attr('data-form-index');
                if(formIdx === '__prefix__') return;

                const cantidad = parseFloat($(this).find('input[name$="-cantidad_solicitada"]').val()) || 0;
                const precio = parseFloat($(this).find('input[name$="-precio_unitario"]').val()) || 0;
                const descuentoPorc = parseFloat($(this).find('input[name$="-descuento_porcentaje"]').val()) || 0;
                
                const bruto = cantidad * precio;
                const desc = Math.round(bruto * (descuentoPorc / 100));
                const neto = bruto - desc;
                $(this).find('.item-total').val(Math.round(neto).toLocaleString('es-CL'));
                subtotalBrutoItems += bruto;
                totalDescuentoItems += desc;
            });
            
            $('#id_subtotal').val(Math.round(subtotalBrutoItems));

            if (!manualAdjust) {
                const descGlobalPorc = parseFloat($('#id_descuento_global_porcentaje').val()) || 0;
                const netoPreGlobal = subtotalBrutoItems - totalDescuentoItems;
                const descGlobalMonto = Math.round(netoPreGlobal * (descGlobalPorc / 100));
                $('#id_descuento_global_monto').val(descGlobalMonto);
                $('#id_descuentos_totales').val(totalDescuentoItems + descGlobalMonto);
                const netoFinal = netoPreGlobal - descGlobalMonto;
                $('#id_neto_ajustado').val(netoFinal);
                $('#id_iva_ajustado').val(Math.round(netoFinal * 0.19));
            }

            const ivaVal = parseInt($('#id_iva_ajustado').val()) || 0;
            const espVal = parseInt($('#id_impuesto_especifico').val()) || 0;
            $('#id_impuestos_totales').val(ivaVal + espVal);
            const netoVal = parseInt($('#id_neto_ajustado').val()) || 0;
            $('#id_total_orden').val(netoVal + ivaVal + espVal);
        }

        $(document).on('input change', '.item-row input, .item-row select, #id_descuento_global_porcentaje', function() {
            manualAdjust = false; 
            calcularTotales();
        });

        $(document).on('input change', '#id_descuento_global_monto, #id_neto_ajustado, #id_iva_ajustado, #id_impuesto_especifico, #id_total_orden', function() {
            manualAdjust = true; 
            calcularTotales();
        });

        $('#addItemBtn').click(function() {
            const formIdx = parseInt($('#id_items-TOTAL_FORMS').val());
            let tmplHtml = $('#empty-form-template').html();
            tmplHtml = tmplHtml.replace(/__prefix__/g, formIdx);
            let $tmpl = $(tmplHtml).attr('data-form-index', formIdx);
            $tmpl.find('[name*="__prefix__"]').each(function() {
                $(this).attr('name', $(this).attr('name').replace('__prefix__', formIdx));
                $(this).attr('id', 'id_' + $(this).attr('name'));
            });
            $('#items-wrapper').append($tmpl);
            $('#id_items-TOTAL_FORMS').val(formIdx + 1);
            $tmpl.find('.articulo-select').select2({ theme: 'default', width: '100%', placeholder: '...' });
        });

        window.eliminarItem = function(button) {
            const row = $(button).closest('.item-line');
            if (row.find('input[name$="-DELETE"]').length) {
                row.find('input[name$="-DELETE"]').prop('checked', true);
                row.hide();
            } else { row.remove(); }
            calcularTotales();
        }

        if (!$('.edit-mode').length && $('#id_descuento_global_porcentaje').val() == 0) {
            $('#id_descuento_global_porcentaje').val(3);
        }
        calcularTotales();
    });
</script>
{% endblock %}
"""
    
with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines[:start_line])
    f.write(new_tail)
print('REWRITE SUCCESSFUL')
