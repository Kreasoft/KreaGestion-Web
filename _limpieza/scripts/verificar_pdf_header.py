
try:
    with open("Factura_47_b64.pdf", "rb") as f:
        header = f.read(8)
        print(f"Header: {header}")
        if header.startswith(b'%PDF'):
            print("VERIFICADO: Es un archivo PDF válido.")
        else:
            print("ALERTA: El archivo no parece ser un PDF válido.")
except FileNotFoundError:
    print("ERROR: El archivo Factura_47_b64.pdf no existe.")
