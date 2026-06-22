import tkinter as tk
from tkinter import ttk, messagebox
import win32print

def obtener_impresoras():
    """Obtiene la lista de impresoras instaladas en Windows"""
    try:
        impresoras = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
        nombres = [impresora[2] for impresora in impresoras]
        return nombres
    except Exception as e:
        messagebox.showerror("Error", f"No se pudieron listar las impresoras: {e}")
        return []

def imprimir_prueba():
    """Envía un texto plano o ESC/POS directo a la impresora seleccionada"""
    impresora_seleccionada = combo_impresoras.get()
    
    if not impresora_seleccionada:
        messagebox.showwarning("Aviso", "Por favor selecciona una impresora primero.")
        return

    # Comandos básicos ESC/POS
    # Inicializar impresora (\x1B\x40), Centrar (\x1B\x61\x01), Cortar papel (\x1D\x56\x00)
    texto_imprimir = (
        b"\x1B\x40"  # Inicializar impresora
        b"\x1B\x61\x01"  # Alinear al centro
        b"================================\n"
        b"        MI EMPRESA SPA          \n"
        b"================================\n"
        b"Esta es una prueba de impresion \n"
        b"directa desde Python usando la  \n"
        b"libreria nativa de Windows.     \n"
        b"                                \n"
        b"IMPRESION 100% SILENCIOSA       \n"
        b"================================\n\n\n\n\n"
        b"\x1D\x56\x00"  # Cortar papel
    )

    try:
        # Abrir conexión directa a la impresora (RAW)
        hPrinter = win32print.OpenPrinter(impresora_seleccionada)
        try:
            # Iniciar documento RAW
            win32print.StartDocPrinter(hPrinter, 1, ("Prueba de Boleta", None, "RAW"))
            try:
                win32print.StartPagePrinter(hPrinter)
                
                # Enviar los bytes directamente
                win32print.WritePrinter(hPrinter, texto_imprimir)
                
                win32print.EndPagePrinter(hPrinter)
            finally:
                win32print.EndDocPrinter(hPrinter)
        finally:
            win32print.ClosePrinter(hPrinter)
            
        messagebox.showinfo("Éxito", "La orden de impresión fue enviada correctamente a la impresora.")
        
    except Exception as e:
        messagebox.showerror("Error de Impresión", f"Ocurrió un error al intentar imprimir:\n{e}")

# ==========================================
# INTERFAZ GRÁFICA (Tkinter)
# ==========================================
root = tk.Tk()
root.title("Agente de Impresión Local - Prueba Independiente")
root.geometry("400x250")
root.resizable(False, False)

# Estilo
style = ttk.Style()
style.theme_use("clam")

# Contenedor principal
frame = ttk.Frame(root, padding=20)
frame.pack(fill=tk.BOTH, expand=True)

# Título
lbl_titulo = ttk.Label(frame, text="Prueba de Impresión Directa", font=("Arial", 14, "bold"))
lbl_titulo.pack(pady=(0, 15))

# Etiqueta Impresoras
lbl_info = ttk.Label(frame, text="Selecciona tu impresora térmica:")
lbl_info.pack(anchor="w")

# Combobox (Desplegable)
lista_impresoras = obtener_impresoras()
combo_impresoras = ttk.Combobox(frame, values=lista_impresoras, state="readonly", width=40)
if lista_impresoras:
    combo_impresoras.current(0)  # Seleccionar la primera por defecto
combo_impresoras.pack(pady=5)

# Botón Actualizar
btn_actualizar = ttk.Button(frame, text="🔄 Refrescar Impresoras", command=lambda: combo_impresoras.config(values=obtener_impresoras()))
btn_actualizar.pack(pady=5)

# Separador
ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)

# Botón de Imprimir
btn_imprimir = ttk.Button(frame, text="🖨️ Enviar Boleta de Prueba", command=imprimir_prueba, style="Accent.TButton")
# Definir color del botón principal
style.configure("Accent.TButton", font=("Arial", 10, "bold"), foreground="white", background="#007bff")
style.map("Accent.TButton", background=[("active", "#0056b3")])

btn_imprimir.pack(pady=10)

# Iniciar la interfaz
root.mainloop()
