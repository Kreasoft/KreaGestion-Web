
import os

path = r'c:\PROJECTOS-WEB\GestionCloud\documentos\templates\documentos\documento_compra_form.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Buscamos el inicio del bloque de totales antiguo
marker = '<!-- Totales -->'
idx = content.find(marker)

if idx != -1:
    head = content[:idx]
    tail = """<!-- Panel de Totales y Descuentos Globales -->
            <div class="row mt-4">
                <div class="col-md-6">
                    <!-- Espacio para archivos o datos extra si se requiere -->
                     {% if form.archivo_documento %}
                     <div class="card border-0 shadow-sm p-3 mb-3" style="background: #fdfbf7; border-radius: 12px;">
                        <h6 class="text-uppercase fw-bold mb-2 small" style="color: var(--stone-primary);">Archivo Adjunto</h6>
                        {{ form.archivo_documento }}
                     </div>
                     {% endif %}
                </div>

                <div class="col-md-6">
                    <div class="totals-panel shadow-sm" style="background-color: #fdfbf7; border: 1px solid var(--stone-light); border-radius: 12px; padding: 1.5rem;">
                        <!-- Subtotal de Items -->
                        <div class="total-row align-items-center mb-2" style="display: flex; justify-content: space-between; font-size: 0.9rem;">
                             <span class="fw-bold text-muted">SUBTOTAL ITEMS BRUTO:</span>
                             {{ form.subtotal }}
                        </div>

                        <!-- SISTEMA DE TRIPLE DESCUENTO EN CASCADA -->
                        <div class="bg-white p-2 rounded border border-light mb-2 shadow-sm">
                            <span class="small fw-bold text-muted text-uppercase d-block mb-1" style="font-size: 0.65rem;">Descuentos Escalonados (%)</span>
                            <div class="row g-2">
                                <div class="col-4">
                                    <label class="small text-muted mb-0" style="font-size: 0.6rem;">Desc 1</label>
                                    {{ form.descuento_porcentaje_1 }}
                                </div>
                                <div class="col-4">
                                    <label class="small text-muted mb-0" style="font-size: 0.6rem;">Desc 2</label>
                                    {{ form.descuento_porcentaje_2 }}
                                </div>
                                <div class="col-4">
                                    <label class="small text-muted mb-0" style="font-size: 0.6rem;">Desc 3</label>
                                    {{ form.descuento_porcentaje_3 }}
                                </div>
                            </div>
                        </div>

                        <!-- DESCUENTO DIRECTO -->
                        <div class="total-row align-items-center mb-2" style="display: flex; justify-content: space-between;">
                             <span class="text-danger small fw-bold">DESC. DIRECTO ($):</span>
                             {{ form.descuento_monto_directo }}
                        </div>

                        <div class="total-row align-items-center mb-2" style="display: flex; justify-content: space-between;">
                             <span class="text-danger small">SUMA DESCUENTOS:</span>
                             {{ form.descuentos_totales }}
                        </div>

                        <hr class="my-2" style="border-color: var(--stone-light);">

                        <!-- NETO, IVA E IMPUESTO ESP -->
                        <div class="total-row align-items-center mb-2" style="display: flex; justify-content: space-between;">
                             <span class="fw-bold fs-6" style="color: var(--stone-primary);">MONTO NETO:</span>
                             {{ form.neto_ajustado }}
                        </div>

                        <div class="total-row align-items-center mb-2" style="display: flex; justify-content: space-between;">
                             <span>IVA (19%):</span>
                             {{ form.iva_ajustado }}
                        </div>

                        <div class="total-row align-items-center mb-2" style="display: flex; justify-content: space-between;">
                             <span>IMPUESTO ESP.:</span>
                             {{ form.impuesto_especifico }}
                        </div>

                        <div class="total-row final align-items-center" style="border-top: 2px solid var(--stone-light); margin-top: 0.5rem; padding-top: 0.5rem; font-weight: 700; font-size: 1.1rem; display: flex; justify-content: space-between;">
                             <span>TOTAL DOCUMENTO:</span>
                             {{ form.total_documento }}
                        </div>
                    </div>
                    
                    <button type="submit" class="btn-stone-primary w-100 mt-3 py-2 fs-5">
                        <i class="fas fa-save me-2"></i> GUARDAR DOCUMENTO
                    </button>
                    <p class="text-center text-muted mt-2 small">
                        <i class="fas fa-info-circle me-1"></i> Los totales son editables para cuadrar decimales.
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
                    <option value="{{ articulo.id }}" data-precio-costo="{% if articulo.precio_costo %}{{ articulo.precio_costo|floatformat:0 }}{% else %}0{% endif %}">
                        {{ articulo.codigo }} - {{ articulo.nombre|truncatechars:35 }}
                    </option>
                {% endfor %}
            </select>
        </div>
        <div class="col-2 px-1"><input type="number" name="items-__prefix__-cantidad" class="form-control form-control-sm text-center" value="1"></div>
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

<!-- Modal OCs (Mantener existente) -->
<div class="modal fade" id="modalOrdenesCompra" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header stone-header-card" style="border-bottom: 2px solid var(--stone-light);">
                <h5 class="modal-title stone-title">Órdenes de Compra Disponibles</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <div class="table-responsive">
                    <table class="table table-hover" id="tablaOrdenesCompra">
                        <thead>
                            <tr>
                                <th>N° Orden</th>
                                <th>Fecha</th>
                                <th>Estado</th>
                                <th>Total</th>
                                <th>Acción</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
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
                const cantidad = parseFloat($(this).find('input[name$="-cantidad"]').val()) || 0;
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
                const netoBase = subtotalBrutoItems - totalDescuentoItems;
                const d1 = parseFloat($('#id_descuento_porcentaje_1').val()) || 0;
                const d2 = parseFloat($('#id_descuento_porcentaje_2').val()) || 0;
                const d3 = parseFloat($('#id_descuento_porcentaje_3').val()) || 0;
                const dDirecto = parseFloat($('#id_descuento_monto_directo').val()) || 0;

                let actual_neto = netoBase;
                actual_neto = actual_neto * (1 - d1 / 100);
                actual_neto = actual_neto * (1 - d2 / 100);
                actual_neto = actual_neto * (1 - d3 / 100);
                
                const netoFinalCalculado = Math.round(actual_neto) - dDirecto;
                
                $('#id_neto_ajustado').val(netoFinalCalculado);
                $('#id_descuentos_totales').val(subtotalBrutoItems - netoFinalCalculado);
                $('#id_iva_ajustado').val(Math.round(netoFinalCalculado * 0.19));
            }

            const ivaVal = parseInt($('#id_iva_ajustado').val()) || 0;
            const espVal = parseInt($('#id_impuesto_especifico').val()) || 0;
            $('#id_impuestos_totales').val(ivaVal + espVal);
            const netoVal = parseInt($('#id_neto_ajustado').val()) || 0;
            $('#id_total_documento').val(netoVal + ivaVal + espVal);
        }

        $(document).on('input change', '.item-row input, .item-row select, #id_descuento_porcentaje_1, #id_descuento_porcentaje_2, #id_descuento_porcentaje_3', function() {
            manualAdjust = false; 
            calcularTotales();
        });

        $(document).on('input change', '#id_descuento_monto_directo, #id_neto_ajustado, #id_iva_ajustado, #id_impuesto_especifico, #id_total_documento', function() {
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

        // TRAER OC
        window.abrirModalOrdenesCompra = function() {
            const proveedorId = $('#id_proveedor').val();
            if (!proveedorId) {
                Swal.fire('Atención', 'Seleccione un proveedor primero', 'warning');
                return;
            }
            const url = "{% url 'documentos:ordenes_compra_disponibles' %}?proveedor_id=" + proveedorId;
            $.get(url, function(data) {
                if (data.success) {
                    const tbody = $('#tablaOrdenesCompra tbody').empty();
                    if (data.ordenes.length === 0) {
                        tbody.append('<tr><td colspan="5" class="text-center">No hay órdenes disponibles.</td></tr>');
                    } else {
                        data.ordenes.forEach(oc => {
                            tbody.append(`<tr><td>${oc.numero_orden}</td><td>${oc.fecha_orden}</td><td>${oc.estado}</td><td>$${oc.total_orden.toLocaleString('es-CL')}</td><td><button type="button" class="btn btn-sm btn-stone-primary" onclick="cargarOC(${oc.id})">Seleccionar</button></td></tr>`);
                        });
                    }
                    new bootstrap.Modal(document.getElementById('modalOrdenesCompra')).show();
                }
            });
        };

        window.cargarOC = function(ocId) {
             const url = "{% url 'documentos:orden_compra_detalle_json' 0 %}".replace('0', ocId);
             $.get(url, function(data) {
                 if (data.success) {
                    $('#orden_compra_id').val(data.orden.id);
                    // Cargar items...
                    data.items.forEach(item => {
                        $('#addItemBtn').click();
                        const row = $('#items-wrapper .item-line:last-child');
                        row.find('.articulo-select').val(item.articulo_id).trigger('change');
                        row.find('input[name$="-cantidad"]').val(item.cantidad_solicitada);
                        row.find('input[name$="-precio_unitario"]').val(item.precio_unitario);
                    });
                    calcularTotales();
                    bootstrap.Modal.getInstance(document.getElementById('modalOrdenesCompra')).hide();
                 }
             });
        };

        calcularTotales();
    });
</script>
{% endblock %}
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(head + tail)
    print('SUCCESS')
else:
    print('MARKER NOT FOUND')
