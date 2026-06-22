import re

with open('ventas/views_pos_procesar.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the redirect in procesar_venta_pos_directo
old_body = r"""            if dte:
                # Redirigir a vista del DTE con impresión y cierre automático
                from urllib.parse import quote
                doc_url = reverse\('facturacion_electronica:ver_factura_electronica', kwargs=\{'dte_id': dte.pk\}\)
                pos_url = reverse\('ventas:pos_view'\)
                # auto=1: imprime automáticamente
                # autoclose=1: cierra y vuelve después de imprimir
                # autoclose_delay=2000: espera 2 segundos \(menos que caja porque POS es más rápido\)
                # IMPORTANTE: codificar return_url para que se pase correctamente
                return redirect\(f"\{doc_url\}\?auto=1&autoclose=1&autoclose_delay=2000&return_url=\{quote\(pos_url, safe=''\)\}"\)
            else:
                # Si no hay DTE, imprimir como vale
                from urllib.parse import quote
                pos_url = reverse\('ventas:pos_view'\)
                vale_url = reverse\('ventas:vale_html', args=\[ticket.pk\]\)
                return redirect\(f"\{vale_url\}\?auto=1&autoclose=1&autoclose_delay=2000&return_url=\{quote\(pos_url, safe=''\)\}"\)"""

new_body = """            from caja.models import ColaImpresion
            from caja.impresion_utils import generar_esc_pos_ticket
            
            try:
                # Tanto si es DTE como si es vale, generamos formato texto (Ticket/Vale)
                # En un futuro se podría mandar un PDF a ColaImpresion
                contenido = generar_esc_pos_ticket(ticket)
                tipo_doc = ticket.tipo_documento_planeado
                ColaImpresion.objects.create(
                    empresa=empresa,
                    tipo_documento=tipo_doc,
                    documento_id=ticket.id,
                    contenido_esc_pos=contenido,
                    estado='pendiente'
                )
                print(f"[POS DIRECTO] Impresión encolada para ticket {ticket.id} ({tipo_doc})")
            except Exception as e_print:
                print(f"[POS DIRECTO] Error al encolar impresión: {e_print}")
                
            return redirect('ventas:pos_view')"""

content = re.sub(old_body, new_body, content)

with open('ventas/views_pos_procesar.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done replacing redirect with local print in procesar_venta_pos_directo")
