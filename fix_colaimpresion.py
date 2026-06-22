import re

with open('ventas/views_pos_procesar.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix for procesar_venta_pos
old_body_vale = r"""    try:
        contenido = generar_esc_pos_ticket\(ticket\)
        ColaImpresion\.objects\.create\(
            empresa=empresa,
            tipo_documento='vale',
            documento_id=ticket\.id,
            contenido_esc_pos=contenido,
            estado='pendiente'
        \)"""

new_body_vale = """    try:
        contenido = generar_esc_pos_ticket(ticket)
        
        # Obtener caja
        caja_id = 1
        if ticket.estacion_trabajo:
            from caja.models import AperturaCaja
            aps = AperturaCaja.objects.filter(caja__empresa=empresa, activo=True)
            for ap in aps:
                if ap.caja.estaciones.filter(id=ticket.estacion_trabajo.id).exists() or ap.caja.estacion == ticket.estacion_trabajo:
                    caja_id = ap.caja.id
                    break
                    
        ColaImpresion.objects.create(
            caja_id=caja_id,
            venta=ticket,
            contenido_raw=contenido,
            estado='pendiente'
        )"""

content = re.sub(old_body_vale, new_body_vale, content)

# Fix for procesar_venta_pos_directo
old_body_direct = r"""            try:
                # Tanto si es DTE como si es vale, generamos formato texto \(Ticket/Vale\)
                # En un futuro se podría mandar un PDF a ColaImpresion
                contenido = generar_esc_pos_ticket\(ticket\)
                tipo_doc = ticket\.tipo_documento_planeado
                ColaImpresion\.objects\.create\(
                    empresa=empresa,
                    tipo_documento=tipo_doc,
                    documento_id=ticket\.id,
                    contenido_esc_pos=contenido,
                    estado='pendiente'
                \)"""

new_body_direct = """            try:
                contenido = generar_esc_pos_ticket(ticket)
                tipo_doc = ticket.tipo_documento_planeado
                
                # Obtener caja
                caja_id = 1
                if ticket.estacion_trabajo:
                    from caja.models import AperturaCaja
                    aps = AperturaCaja.objects.filter(caja__empresa=empresa, activo=True)
                    for ap in aps:
                        if ap.caja.estaciones.filter(id=ticket.estacion_trabajo.id).exists() or ap.caja.estacion == ticket.estacion_trabajo:
                            caja_id = ap.caja.id
                            break
                
                ColaImpresion.objects.create(
                    caja_id=caja_id,
                    venta=ticket,
                    contenido_raw=contenido,
                    estado='pendiente'
                )"""

content = re.sub(old_body_direct, new_body_direct, content)

with open('ventas/views_pos_procesar.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed ColaImpresion creation in views_pos_procesar.py")
