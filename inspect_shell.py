from ventas.models import Venta
sales = Venta.objects.all().order_by("-id")[:20]
for s in sales:
    c_name = s.cliente.nombre if s.cliente else "NULL"
    print(f"ID:{s.id} ClientFK:{s.cliente_id} ({c_name}) | Obs:{s.observaciones[:60]}")
