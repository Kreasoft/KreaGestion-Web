import tkinter as tk
from tkinter import ttk, messagebox
import win32print
import requests
import threading
import time
import json
import os
import sys
from urllib.parse import urlencode

CONFIG_FILE = "config_impresora.json"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/caja/api/impresion"

_IMPRESORAS_VIRTUALES = (
    "rustdesk", "anydesk", "teamviewer", "pdf", "xps", "onenote", "fax",
    "microsoft print to pdf", "microsoft pps", "cutepdf", "foxit", "chrome",
    "send to",
)
_IMPRESORAS_TERMICAS = (
    "rongta", "xprinter", "pos-80", "pos-58", "tm-", "80mm", "58mm",
    "thermal", "termica", "epson", "star ", "bixolon", "citizen",
    "gprinter", "gainscha", "mpt-",
)


def _es_impresora_virtual(nombre):
    n = (nombre or "").lower()
    return any(token in n for token in _IMPRESORAS_VIRTUALES)


def _es_impresora_termica(nombre):
    n = (nombre or "").lower()
    return any(token in n for token in _IMPRESORAS_TERMICAS)


def _elegir_impresora(impresoras, guardada=""):
    if guardada in impresoras and not _es_impresora_virtual(guardada):
        return guardada
    for nombre in impresoras:
        if _es_impresora_termica(nombre):
            return nombre
    reales = [nombre for nombre in impresoras if not _es_impresora_virtual(nombre)]
    return (reales or impresoras or [""])[0]


def get_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _comando_inicio_windows():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{os.path.abspath(__file__)}"'


def _registrar_inicio_windows():
    """Se abre solo al encender el PC. No cambia cómo imprime."""
    try:
        import winreg
        clave = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(clave, "GestionCloudImpresora", 0, winreg.REG_SZ, _comando_inicio_windows())
        winreg.CloseKey(clave)
    except Exception:
        pass


CONFIG_PATHS = [
    os.path.join(get_app_dir(), CONFIG_FILE),
    os.path.join(os.getcwd(), CONFIG_FILE),
]


class AgenteImpresionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Impresora GestionCloud")
        self.root.geometry("440x460")
        self.root.resizable(False, False)

        self.servicio_corriendo = False
        self.hilo = None
        self.config = self.cargar_config()

        self.crear_interfaz()
        self._mostrar_pantalla()
        if self._esta_vinculado() and self.config.get("auto_start", True) and self.config.get("impresora"):
            self.root.after(600, self.iniciar_servicio)

    def cargar_config(self):
        defaults = {
            "impresora": "",
            "empresa_id": "",
            "sucursal_id": "",
            "caja_id": "",
            "empresa": "",
            "sucursal": "",
            "caja": "",
            "api_base_url": DEFAULT_API_BASE_URL,
            "auto_start": True,
        }
        for config_path in CONFIG_PATHS:
            if not os.path.exists(config_path):
                continue
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                defaults.update(data or {})
                return defaults
            except Exception:
                continue
        return defaults

    def guardar_config(self, extra=None):
        if extra:
            self.config.update(extra)
        self.config["impresora"] = self.combo_impresoras.get() if hasattr(self, "combo_impresoras") else self.config.get("impresora")
        with open(CONFIG_PATHS[0], "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def _esta_vinculado(self):
        return bool(self.config.get("empresa_id") and self.config.get("sucursal_id") and self.config.get("caja_id"))

    def obtener_impresoras(self):
        try:
            impresoras = win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            )
            return [impresora[2] for impresora in impresoras]
        except Exception as e:
            messagebox.showerror("Error", f"No se encontraron impresoras:\n{e}")
            return []

    def crear_interfaz(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Accent.TButton", font=("Arial", 10, "bold"), foreground="white", background="#5F8D62")
        style.map("Accent.TButton", background=[("active", "#4E7A51")])
        style.configure("Stop.TButton", font=("Arial", 10, "bold"), foreground="white", background="#C76F43")
        style.map("Stop.TButton", background=[("active", "#A85A36")])

        self.frame = ttk.Frame(self.root, padding=18)
        self.frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(self.frame, text="Impresora de la sucursal", font=("Arial", 13, "bold")).pack(pady=(0, 12))

        self.frm_codigo = ttk.Frame(self.frame)
        ttk.Label(self.frm_codigo, text="Ingrese el código que le mostró GestionCloud:").pack(anchor="w")
        self.entry_codigo = ttk.Entry(self.frm_codigo, font=("Arial", 16), justify="center")
        self.entry_codigo.pack(fill="x", pady=8, ipady=6)
        ttk.Button(self.frm_codigo, text="Vincular este computador", command=self.vincular, style="Accent.TButton").pack(fill="x", pady=(4, 0))

        self.frm_trabajo = ttk.Frame(self.frame)
        self.lbl_lugar = ttk.Label(self.frm_trabajo, text="", justify="center", font=("Arial", 10))
        self.lbl_lugar.pack(pady=(0, 10))

        ttk.Label(self.frm_trabajo, text="¿En qué impresora se imprimen los tickets?").pack(anchor="w")
        impresoras = self.obtener_impresoras()
        self.combo_impresoras = ttk.Combobox(self.frm_trabajo, values=impresoras, state="readonly")
        elegida = _elegir_impresora(impresoras, self.config.get("impresora"))
        if elegida:
            self.combo_impresoras.set(elegida)
        self.combo_impresoras.pack(fill="x", pady=(4, 12))

        self.lbl_estado = ttk.Label(self.frm_trabajo, text="Listo para imprimir", font=("Arial", 10, "bold"))
        self.lbl_estado.pack(pady=4)

        self.btn_iniciar = ttk.Button(self.frm_trabajo, text="Iniciar", command=self.iniciar_servicio, style="Accent.TButton")
        self.btn_iniciar.pack(fill="x", pady=4)
        self.btn_detener = ttk.Button(self.frm_trabajo, text="Detener", command=self.detener_servicio, style="Stop.TButton")
        self.btn_detener.pack(fill="x", pady=4)
        self.btn_detener.state(["disabled"])
        ttk.Button(self.frm_trabajo, text="Probar impresión", command=self.probar_impresion).pack(fill="x", pady=4)
        ttk.Label(
            self.frm_trabajo,
            text="Se abrirá solo al encender el computador.",
            foreground="#8B7355",
        ).pack(pady=(8, 0))
        ttk.Button(self.frm_trabajo, text="Usar otro código", command=self.desvincular).pack(pady=(10, 0))

    def _mostrar_pantalla(self):
        self.frm_codigo.pack_forget()
        self.frm_trabajo.pack_forget()
        if self._esta_vinculado():
            self.lbl_lugar.config(
                text=f"{self.config.get('empresa', '')}\n{self.config.get('sucursal', '')}\n{self.config.get('caja', '')}"
            )
            self.frm_trabajo.pack(fill="x")
        else:
            self.frm_codigo.pack(fill="x")

    def vincular(self):
        codigo = self.entry_codigo.get().strip().upper().replace(" ", "")
        if len(codigo) < 4:
            messagebox.showinfo("Código", "Escriba el código de 6 letras que aparece en GestionCloud.")
            return
        api_base = (self.config.get("api_base_url") or DEFAULT_API_BASE_URL).rstrip("/")
        url = f"{api_base}/vincular/?codigo={codigo}"
        try:
            response = requests.get(url, timeout=8)
            data = response.json()
        except Exception:
            messagebox.showerror(
                "No se pudo conectar",
                "Descargue el programa desde GestionCloud (Caja → Conectar impresora)\ny ábralo en la carpeta descomprimida.",
            )
            return

        if not data.get("ok"):
            messagebox.showerror("Código no válido", data.get("mensaje") or "Pida un código nuevo en GestionCloud.")
            return

        self.guardar_config({
            "empresa_id": data.get("empresa_id"),
            "sucursal_id": data.get("sucursal_id"),
            "caja_id": data.get("caja_id"),
            "empresa": data.get("empresa"),
            "sucursal": data.get("sucursal"),
            "caja": data.get("caja"),
            "api_base_url": (data.get("api_base_url") or DEFAULT_API_BASE_URL).rstrip("/"),
        })
        self._mostrar_pantalla()

    def desvincular(self):
        if self.servicio_corriendo:
            self.detener_servicio()
        self.guardar_config({
            "empresa_id": "",
            "sucursal_id": "",
            "caja_id": "",
            "empresa": "",
            "sucursal": "",
            "caja": "",
        })
        self.entry_codigo.delete(0, tk.END)
        self._mostrar_pantalla()

    def _contenido_escpos_a_bytes(self, contenido_raw):
        if not isinstance(contenido_raw, str):
            return contenido_raw
        salida = bytearray()
        i = 0
        n = len(contenido_raw)
        while i < n:
            ch = contenido_raw[i]
            if ch == "\\" and i + 1 < n:
                nxt = contenido_raw[i + 1]
                if nxt == "x" and i + 3 < n:
                    try:
                        salida.append(int(contenido_raw[i + 2:i + 4], 16))
                        i += 4
                        continue
                    except ValueError:
                        pass
                if nxt == "n":
                    salida.append(0x0A)
                    i += 2
                    continue
                if nxt == "r":
                    salida.append(0x0D)
                    i += 2
                    continue
                if nxt == "t":
                    salida.append(0x09)
                    i += 2
                    continue
                if nxt == "\\":
                    salida.append(0x5C)
                    i += 2
                    continue
                if nxt == "0":
                    salida.append(0x00)
                    i += 2
                    continue
            salida.extend(ch.encode("cp850", errors="replace"))
            i += 1
        return bytes(salida)

    def imprimir_raw(self, nombre_impresora, contenido_raw):
        try:
            bytes_raw = self._contenido_escpos_a_bytes(contenido_raw)
            if not bytes_raw:
                return False, "El ticket está vacío"
            hPrinter = win32print.OpenPrinter(nombre_impresora)
            try:
                # RAW: no usar StartPagePrinter; el spooler se come el ticket.
                win32print.StartDocPrinter(hPrinter, 1, ("Ticket GestionCloud", None, "RAW"))
                try:
                    escritos = win32print.WritePrinter(hPrinter, bytes_raw)
                    if not escritos:
                        return False, "Windows no envió bytes a la impresora"
                finally:
                    win32print.EndDocPrinter(hPrinter)
            finally:
                win32print.ClosePrinter(hPrinter)
            return True, ""
        except Exception as e:
            return False, str(e)

    def probar_impresion(self):
        impresora = self.combo_impresoras.get() if hasattr(self, "combo_impresoras") else self.config.get("impresora")
        if not impresora:
            messagebox.showinfo("Impresora", "Seleccione la impresora térmica.")
            return
        if _es_impresora_virtual(impresora):
            messagebox.showerror(
                "Impresora virtual",
                "Esa impresora no es la térmica (RustDesk/PDF/AnyDesk).\nElija RONGTA 80mm Series Printer.",
            )
            return
        prueba = r"\x1B\x40\x1B\x61\x01PRUEBA GestionCloud\nSi ve este ticket, la termica esta bien\n\n\n\n\x1D\x56\x00"
        ok, err = self.imprimir_raw(impresora, prueba)
        if ok:
            messagebox.showinfo("Prueba", "Se envió un ticket de prueba a la térmica.")
        else:
            messagebox.showerror("Prueba", err or "No se pudo imprimir.")

    def tarea_fondo(self):
        empresa_id = self.config.get("empresa_id")
        sucursal_id = self.config.get("sucursal_id")
        caja_id = self.config.get("caja_id")
        impresora = self.config.get("impresora")
        api_base_url = self.config.get("api_base_url", DEFAULT_API_BASE_URL).rstrip("/")

        while self.servicio_corriendo:
            try:
                try:
                    impresoras = [
                        p[2] for p in win32print.EnumPrinters(
                            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
                        )
                    ]
                except Exception:
                    impresoras = []
                impresora_actual = (
                    self.combo_impresoras.get()
                    if hasattr(self, "combo_impresoras")
                    else impresora
                ) or impresora
                query = urlencode({
                    "empresa_id": empresa_id,
                    "sucursal_id": sucursal_id,
                    "caja_id": caja_id,
                    "impresora": impresora_actual or "",
                    "impresoras": json.dumps(impresoras, ensure_ascii=False),
                })
                response = requests.get(
                    f"{api_base_url}/pendientes/?{query}",
                    timeout=5,
                )
                if response.status_code == 200:
                    for trabajo in response.json().get("pendientes", []):
                        destino = (trabajo.get("nombre_impresora") or "").strip() or impresora_actual
                        exito, error_msg = self.imprimir_raw(destino, trabajo.get("contenido_raw"))
                        requests.post(
                            f"{api_base_url}/marcar-impreso/",
                            json={
                                "id": trabajo["id"],
                                "status": "impreso" if exito else "error",
                                "error_msg": error_msg,
                                "empresa_id": empresa_id,
                                "sucursal_id": sucursal_id,
                            },
                            timeout=5,
                        )
            except Exception:
                pass
            time.sleep(2.5)

    def iniciar_servicio(self):
        impresora = self.combo_impresoras.get()
        if not impresora:
            messagebox.showinfo("Impresora", "Seleccione la impresora térmica.")
            return
        if _es_impresora_virtual(impresora):
            messagebox.showerror(
                "Impresora virtual",
                "Esa impresora no imprime papel (RustDesk/PDF/AnyDesk).\nElija RONGTA 80mm Series Printer.",
            )
            return
        self.guardar_config({"impresora": impresora})
        _registrar_inicio_windows()
        self.servicio_corriendo = True
        self.btn_iniciar.state(["disabled"])
        self.btn_detener.state(["!disabled"])
        self.combo_impresoras.state(["disabled"])
        self.lbl_estado.config(text="Imprimiendo documentos de esta sucursal", foreground="#5F8D62")
        self.hilo = threading.Thread(target=self.tarea_fondo, daemon=True)
        self.hilo.start()

    def detener_servicio(self):
        self.servicio_corriendo = False
        self.btn_iniciar.state(["!disabled"])
        self.btn_detener.state(["disabled"])
        self.combo_impresoras.state(["readonly"])
        self.lbl_estado.config(text="Detenido", foreground="#C76F43")


if __name__ == "__main__":
    root = tk.Tk()
    app = AgenteImpresionApp(root)
    root.mainloop()
