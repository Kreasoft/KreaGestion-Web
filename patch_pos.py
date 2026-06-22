import sys

def patch_pos_procesar():
    filepath = 'ventas/views_pos_procesar.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Block 1: procesar_venta_pos (VALE)
    old_vale_block = """    # Enviar a Cola de Impresión Local
    from caja.models import ColaImpresion
    from caja.impresion_utils import generar_esc_pos_ticket
    
    try:
        contenido = generar_esc_pos_ticket(ticket)
        
        # Obtener caja
        caja_id = 1
        if ticket.estacion_trabajo:
            from caja.models import AperturaCaja
            aps = AperturaCaja.objects.filter(caja__empresa=empresa, estado='abierta')
            for ap in aps:
                if ap.caja.estacion_trabajo == ticket.estacion_trabajo:
                    caja_id = ap.caja.id
                    break
                    
        ColaImpresion.objects.create(
            caja_id=caja_id,
            venta=ticket,
            contenido_raw=contenido,
            estado='pendiente'
        )
        print(f"[POS VALE] Impresión encolada para ticket {ticket.id}")
        messages.success(request, f"Vale #{ticket.numero_venta} generado e impreso con éxito.")
    except Exception as e:
        print(f"[POS VALE] Error al encolar impresión: {e}")
        messages.error(request, f"El vale se generó pero hubo un error al imprimir: {e}")
        
    return redirect('ventas:pos_view')"""

    new_vale_block = """    # Imprimir según formato
    formato = ticket.estacion_trabajo.formato_impresion if ticket.estacion_trabajo else '80mm'
    
    if formato == 'carta':
        messages.success(request, f"Vale #{ticket.numero_venta} generado. Abriendo documento...")
        return redirect('ventas:venta_imprimir_y_volver', pk=ticket.id)
    else:
        # Enviar a Cola de Impresión Local (Térmica)
        from caja.models import ColaImpresion
        from caja.impresion_utils import generar_esc_pos_ticket
        
        try:
            contenido = generar_esc_pos_ticket(ticket)
            caja_id = 1
            if ticket.estacion_trabajo:
                from caja.models import AperturaCaja
                aps = AperturaCaja.objects.filter(caja__empresa=empresa, estado='abierta')
                for ap in aps:
                    if ap.caja.estacion_trabajo == ticket.estacion_trabajo:
                        caja_id = ap.caja.id
                        break
                        
            ColaImpresion.objects.create(caja_id=caja_id, venta=ticket, contenido_raw=contenido, estado='pendiente')
            print(f"[POS VALE] Impresión encolada para ticket {ticket.id}")
            messages.success(request, f"Vale #{ticket.numero_venta} generado e impreso con éxito.")
        except Exception as e:
            print(f"[POS VALE] Error al encolar impresión: {e}")
            messages.error(request, f"El vale se generó pero hubo un error al imprimir: {e}")
            
        return redirect('ventas:pos_view')"""

    # Block 2: procesar_venta_pos_directo (DIRECTO)
    old_dir_block = """            from caja.models import ColaImpresion
            from caja.impresion_utils import generar_esc_pos_ticket
            
            try:
                contenido = generar_esc_pos_ticket(ticket)
                tipo_doc = ticket.tipo_documento_planeado
                
                # Obtener caja
                caja_id = 1
                if ticket.estacion_trabajo:
                    from caja.models import AperturaCaja
                    aps = AperturaCaja.objects.filter(caja__empresa=empresa, estado='abierta')
                    for ap in aps:
                        if ap.caja.estacion_trabajo == ticket.estacion_trabajo:
                            caja_id = ap.caja.id
                            break
                
                ColaImpresion.objects.create(
                    caja_id=caja_id,
                    venta=ticket,
                    contenido_raw=contenido,
                    estado='pendiente'
                )
                print(f"[POS DIRECTO] Impresión encolada para ticket {ticket.id} ({tipo_doc})")
            except Exception as e_print:
                print(f"[POS DIRECTO] Error al encolar impresión: {e_print}")
                
            return redirect('ventas:pos_view')"""

    new_dir_block = """            formato = ticket.estacion_trabajo.formato_impresion if ticket.estacion_trabajo else '80mm'
            if formato == 'carta':
                return redirect('ventas:venta_imprimir_y_volver', pk=ticket.id)
            else:
                from caja.models import ColaImpresion
                from caja.impresion_utils import generar_esc_pos_ticket
                
                try:
                    contenido = generar_esc_pos_ticket(ticket)
                    tipo_doc = ticket.tipo_documento_planeado
                    caja_id = 1
                    if ticket.estacion_trabajo:
                        from caja.models import AperturaCaja
                        aps = AperturaCaja.objects.filter(caja__empresa=empresa, estado='abierta')
                        for ap in aps:
                            if ap.caja.estacion_trabajo == ticket.estacion_trabajo:
                                caja_id = ap.caja.id
                                break
                    
                    ColaImpresion.objects.create(caja_id=caja_id, venta=ticket, contenido_raw=contenido, estado='pendiente')
                    print(f"[POS DIRECTO] Impresión encolada para ticket {ticket.id} ({tipo_doc})")
                except Exception as e_print:
                    print(f"[POS DIRECTO] Error al encolar impresión: {e_print}")
                    
                return redirect('ventas:pos_view')"""

    # Do the replacements
    content = content.replace(old_vale_block, new_vale_block)
    content = content.replace(old_dir_block, new_dir_block)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Patched views_pos_procesar.py")

patch_pos_procesar()
