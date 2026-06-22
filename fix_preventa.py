import re

with open('ventas/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the duplicate number error in pos_procesar_preventa
old_body = r"""                    # Verificar que el número no exista \(en el mismo tipo\)
                    existe_numero = Venta.objects.filter\(empresa=request.empresa, tipo_documento=data\['tipo_documento'\], numero_venta=proximo_numero\).exists\(\)
                    print\(f"\[DEBUG\] Número generado: \{proximo_numero\}, ¿existe\?: \{existe_numero\}"\)
                    
                    max_intentos = 100
                    intento = 0
                    while existe_numero and intento < max_intentos:
                        print\(f"\[WARN\] El número \{proximo_numero\} de tipo \{data\['tipo_documento'\]\} ya existe, incrementando correlativo..."\)
                        numero_ticket = estacion_bloqueada.incrementar_correlativo_ticket\(\)
                        proximo_numero = f"\{numero_ticket:06d\}"
                        existe_numero = Venta.objects.filter\(empresa=request.empresa, tipo_documento=data\['tipo_documento'\], numero_venta=proximo_numero\).exists\(\)
                        print\(f"\[DEBUG\] Nuevo número: \{proximo_numero\}, ¿existe\?: \{existe_numero\}"\)
                        intento \+= 1"""

new_body = """                    # Verificar que el número no exista (en el mismo tipo que se va a crear)
                    tipo_check = 'cotizacion' if data.get('tipo_documento') == 'cotizacion' else 'ticket'
                    existe_numero = Venta.objects.filter(empresa=request.empresa, tipo_documento=tipo_check, numero_venta=proximo_numero).exists()
                    print(f"[DEBUG] Número generado: {proximo_numero}, ¿existe?: {existe_numero}")
                    
                    max_intentos = 100
                    intento = 0
                    while existe_numero and intento < max_intentos:
                        print(f"[WARN] El número {proximo_numero} de tipo {tipo_check} ya existe, incrementando correlativo...")
                        numero_ticket = estacion_bloqueada.incrementar_correlativo_ticket()
                        proximo_numero = f"{numero_ticket:06d}"
                        existe_numero = Venta.objects.filter(empresa=request.empresa, tipo_documento=tipo_check, numero_venta=proximo_numero).exists()
                        print(f"[DEBUG] Nuevo número: {proximo_numero}, ¿existe?: {existe_numero}")
                        intento += 1"""

content = re.sub(old_body, new_body, content)

with open('ventas/views.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed preventa duplication bug in views.py")
