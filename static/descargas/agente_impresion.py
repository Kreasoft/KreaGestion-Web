import tkinter as tk
from tkinter import ttk, messagebox
import win32print
import requests
import threading
import time
import json
import os

# Configuración Base
CONFIG_FILE = "config_impresora.json"
API_BASE_URL = "http://127.0.0.1:8000/caja/api/impresion" # Cambiar a la URL de Producción

class AgenteImpresionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Agente de Impresión - GestionCloud")
        self.root.geometry("450x350")
        self.root.resizable(False, False)
        
        self.servicio_corriendo = False
        self.hilo = None
        self.config = self.cargar_config()

        self.crear_interfaz()

    def cargar_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"impresora": "", "caja_id": "1"}

    def guardar_config(self, impresora, caja_id):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"impresora": impresora, "caja_id": caja_id}, f)

    def obtener_impresoras(self):
        try:
            impresoras = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
            return [impresora[2] for impresora in impresoras]
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron listar las impresoras: {e}")
            return []

    def crear_interfaz(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Accent.TButton", font=("Arial", 10, "bold"), foreground="white", background="#28a745")
        style.map("Accent.TButton", background=[("active", "#218838")])
        style.configure("Stop.TButton", font=("Arial", 10, "bold"), foreground="white", background="#dc3545")
        style.map("Stop.TButton", background=[("active", "#c82333")])

        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Configuración del Agente", font=("Arial", 12, "bold")).pack(pady=(0, 10))

        # ID de Caja
        frame_caja = ttk.Frame(frame)
        frame_caja.pack(fill='x', pady=5)
        ttk.Label(frame_caja, text="ID de la Caja (Backend):").pack(side='left')
        self.entry_caja = ttk.Entry(frame_caja, width=10)
        self.entry_caja.insert(0, self.config.get("caja_id", "1"))
        self.entry_caja.pack(side='right')

        # Impresoras
        ttk.Label(frame, text="Selecciona la impresora térmica:").pack(anchor="w", pady=(10, 0))
        self.combo_impresoras = ttk.Combobox(frame, values=self.obtener_impresoras(), state="readonly", width=40)
        
        impresora_guardada = self.config.get("impresora")
        if impresora_guardada in self.combo_impresoras['values']:
            self.combo_impresoras.set(impresora_guardada)
        elif self.combo_impresoras['values']:
            self.combo_impresoras.current(0)
            
        self.combo_impresoras.pack(pady=5)

        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=15)

        # Botones de Control
        self.lbl_estado = ttk.Label(frame, text="Estado: DETENIDO", foreground="red", font=("Arial", 10, "bold"))
        self.lbl_estado.pack(pady=5)

        self.btn_iniciar = ttk.Button(frame, text="▶ INICIAR SERVICIO", command=self.iniciar_servicio, style="Accent.TButton")
        self.btn_iniciar.pack(pady=5, fill='x')

        self.btn_detener = ttk.Button(frame, text="⏹ DETENER SERVICIO", command=self.detener_servicio, style="Stop.TButton")
        self.btn_detener.pack(pady=5, fill='x')
        self.btn_detener.state(['disabled'])

    def imprimir_raw(self, nombre_impresora, contenido_raw):
        try:
            hPrinter = win32print.OpenPrinter(nombre_impresora)
            try:
                win32print.StartDocPrinter(hPrinter, 1, ("Boleta Django", None, "RAW"))
                try:
                    win32print.StartPagePrinter(hPrinter)
                    # Convertir el string (que puede tener secuencias de escape como \x1b) a bytes reales
                    if isinstance(contenido_raw, str):
                        # Convertir texto con escapes python a bytes reales
                        bytes_raw = bytes(contenido_raw, "utf-8").decode("unicode_escape").encode("latin-1")
                    else:
                        bytes_raw = contenido_raw

                    win32print.WritePrinter(hPrinter, bytes_raw)
                    win32print.EndPagePrinter(hPrinter)
                finally:
                    win32print.EndDocPrinter(hPrinter)
            finally:
                win32print.ClosePrinter(hPrinter)
            return True, ""
        except Exception as e:
            return False, str(e)

    def tarea_fondo(self):
        caja_id = self.entry_caja.get()
        impresora = self.combo_impresoras.get()
        
        while self.servicio_corriendo:
            try:
                # 1. Consultar trabajos pendientes
                url_get = f"{API_BASE_URL}/pendientes/?caja_id={caja_id}"
                response = requests.get(url_get, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    pendientes = data.get('pendientes', [])
                    
                    for trabajo in pendientes:
                        job_id = trabajo['id']
                        contenido = trabajo['contenido_raw']
                        
                        # 2. Imprimir localmente
                        exito, error_msg = self.imprimir_raw(impresora, contenido)
                        
                        # 3. Marcar como impreso o reportar error al servidor
                        status = "impreso" if exito else "error"
                        url_post = f"{API_BASE_URL}/marcar-impreso/"
                        payload = {"id": job_id, "status": status, "error_msg": error_msg}
                        requests.post(url_post, json=payload)
                        
                        if not exito:
                            print(f"Error al imprimir trabajo {job_id}: {error_msg}")
            
            except Exception as e:
                print(f"Error de conexión con el servidor: {e}")
                
            # Esperar 2.5 segundos antes de la siguiente consulta
            time.sleep(2.5)

    def iniciar_servicio(self):
        impresora = self.combo_impresoras.get()
        caja_id = self.entry_caja.get()
        
        if not impresora or not caja_id:
            messagebox.showwarning("Faltan datos", "Selecciona impresora y Caja ID")
            return
            
        self.guardar_config(impresora, caja_id)
        
        self.servicio_corriendo = True
        self.btn_iniciar.state(['disabled'])
        self.btn_detener.state(['!disabled'])
        self.combo_impresoras.state(['disabled'])
        self.entry_caja.state(['disabled'])
        self.lbl_estado.config(text="Estado: CORRIENDO (Buscando boletas...)", foreground="green")

        self.hilo = threading.Thread(target=self.tarea_fondo, daemon=True)
        self.hilo.start()

    def detener_servicio(self):
        self.servicio_corriendo = False
        self.btn_iniciar.state(['!disabled'])
        self.btn_detener.state(['disabled'])
        self.combo_impresoras.state(['readonly'])
        self.entry_caja.state(['!disabled'])
        self.lbl_estado.config(text="Estado: DETENIDO", foreground="red")


if __name__ == "__main__":
    root = tk.Tk()
    app = AgenteImpresionApp(root)
    root.mainloop()
