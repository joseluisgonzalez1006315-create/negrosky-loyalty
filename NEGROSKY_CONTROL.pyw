import os
import json
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

ROOT = Path(__file__).resolve().parent
PID_FILE = ROOT / ".negrosky-server.pid"
DB_FILE = ROOT / "data" / "negrosky_v2.db"
BACKUPS = ROOT / "backups"
ERROR_LOG = ROOT / "servidor_error.log"
OUTPUT_LOG = ROOT / "servidor_salida.log"
PORT = 8030
CURRENT_VERSION = "3.0.55"
CURRENT_BUILD = "055"


def python_path():
    candidate = ROOT / "venv" / "Scripts" / "python.exe"
    return candidate if candidate.exists() else Path(sys.executable)


def server_health():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=1) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def is_online():
    return server_health() is not None


def is_current_server():
    health = server_health()
    return bool(health and str(health.get("version")) == CURRENT_VERSION and
                str(health.get("build")) == CURRENT_BUILD)


def negrosky_process_ids():
    """Devuelve solo procesos uvicorn que exponen la API de NEGROSKY."""
    if os.name != "nt":
        return []
    command = (
        "$current=$PID; "
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.ProcessId -ne $current -and "
        "([string]$_.CommandLine -match '(?i)uvicorn') -and "
        "([string]$_.CommandLine -match '(?i)(core[.]backend[.]api[.]main|app[.]main):app') } | "
        "Select-Object -ExpandProperty ProcessId"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            capture_output=True, text=True, timeout=5, creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    pids = []
    for line in result.stdout.splitlines():
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        if pid > 0 and pid != os.getpid():
            pids.append(pid)
    return sorted(set(pids))


def stop_process(pid):
    if pid <= 0 or pid == os.getpid():
        return
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       creationflags=flags, capture_output=True)
    else:
        os.kill(pid, signal.SIGTERM)


def stop_negrosky_server():
    """Detiene un servidor NEGROSKY identificado, nunca un proceso ajeno."""
    pids = negrosky_process_ids()
    if os.name != "nt" and PID_FILE.exists():
        try:
            pids.append(int(PID_FILE.read_text(encoding="ascii").strip()))
        except (OSError, ValueError):
            pass
    stopped = False
    for pid in sorted(set(pids)):
        try:
            stop_process(pid)
            stopped = True
        except (OSError, subprocess.SubprocessError):
            pass
    if stopped:
        for _ in range(20):
            if not is_online():
                break
            time.sleep(.25)
    PID_FILE.unlink(missing_ok=True)
    return stopped


def local_ips():
    found = set()
    try:
        found.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return sorted(ip for ip in found if not ip.startswith(
        ("127.", "169.254.", "192.168.56.", "172.17.", "172.18.")) and ":" not in ip)


class Control(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NEGROSKY CONTROL · BUILD 055")
        self.geometry("840x680")
        self.minsize(700, 560)
        self.configure(bg="#090910")
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._style()
        self._build()
        self.refresh()

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#11111b")
        style.configure("TLabel", background="#11111b", foreground="#f7f5ff", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), foreground="#c084fc")
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=10)

    def _build(self):
        shell = ttk.Frame(self, padding=22)
        shell.pack(fill="both", expand=True, padx=18, pady=18)
        ttk.Label(shell, text="NEGROSKY CONTROL", style="Title.TLabel").pack(anchor="w")
        ttk.Label(shell, text="BUILD 055 · Módulos por negocio · Puerto 8030").pack(anchor="w", pady=(0, 15))
        self.status_label = ttk.Label(shell, text="Comprobando…", font=("Segoe UI", 12, "bold"))
        self.status_label.pack(anchor="w", pady=(0, 12))
        actions = ttk.Frame(shell)
        actions.pack(fill="x")
        for text, command in [
            ("▶ Iniciar", self.start_server), ("■ Detener", self.stop_server),
            ("↻ Reiniciar", self.restart_server), ("🌐 Abrir administración", lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")),
            ("💾 Crear respaldo", self.backup),
        ]:
            ttk.Button(actions, text=text, command=command).pack(side="left", padx=(0, 7), pady=5)
        ttk.Label(shell, text="Direcciones para PC y celular", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(18, 7))
        self.urls = tk.Text(shell, height=9, bg="#090910", fg="#d8b4fe", insertbackground="white",
                            relief="flat", font=("Consolas", 10), padx=12, pady=10)
        self.urls.pack(fill="x")
        url_actions = ttk.Frame(shell)
        url_actions.pack(fill="x", pady=6)
        ttk.Button(url_actions, text="Copiar direcciones", command=self.copy_urls).pack(side="left", padx=(0, 7))
        ttk.Button(url_actions, text="Abrir trabajador", command=lambda: webbrowser.open(f"http://127.0.0.1:{PORT}/worker")).pack(side="left")
        ttk.Label(shell, text="Registro del servidor", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(16, 7))
        self.log = tk.Text(shell, height=14, bg="#090910", fg="#d1d5db", relief="flat", font=("Consolas", 9), padx=10, pady=8)
        self.log.pack(fill="both", expand=True)
        ttk.Button(shell, text="Actualizar estado y registro", command=self.refresh).pack(anchor="e", pady=(8, 0))

    def customer_businesses(self):
        if not DB_FILE.exists():
            return []
        try:
            with sqlite3.connect(DB_FILE) as con:
                return con.execute(
                    "SELECT name,slug FROM tenants WHERE status='active' ORDER BY name"
                ).fetchall()
        except (sqlite3.Error, OSError):
            return []

    def url_text(self):
        businesses = self.customer_businesses()
        lines = [
            "EN ESTE COMPUTADOR",
            f"Administrador: http://127.0.0.1:{PORT}",
            f"Trabajador:   http://127.0.0.1:{PORT}/worker",
            "",
            "EN EL CELULAR (misma red Wi-Fi)",
        ]
        ips = local_ips()
        if ips:
            for ip in ips:
                lines += [
                    f"Administrador: http://{ip}:{PORT}",
                    f"Trabajador:   http://{ip}:{PORT}/worker",
                    "",
                ]
        else:
            lines.append("No se detectó una IP Wi-Fi. Conecta el PC a la red y pulsa Actualizar.")
        lines += ["", "PÁGINAS DE CLIENTES POR NEGOCIO"]
        if not businesses:
            lines.append("Todavía no hay negocios activos.")
        for name, slug in businesses:
            lines.append(f"{name} · PC: http://127.0.0.1:{PORT}/b/{slug}")
            for ip in ips:
                lines.append(f"{name} · Celular: http://{ip}:{PORT}/b/{slug}")
            lines.append("")
        return "\n".join(lines)

    def refresh(self):
        health = server_health()
        if health and str(health.get("version")) == CURRENT_VERSION and str(health.get("build")) == CURRENT_BUILD:
            status = "● SERVIDOR BUILD 055 ENCENDIDO"
            color = "#61e9a8"
        elif health:
            status = "● SERVIDOR ANTIGUO ENCENDIDO · pulsa Iniciar"
            color = "#fbbf24"
        else:
            status = "● SERVIDOR DETENIDO"
            color = "#fb7185"
        self.status_label.config(text=status, foreground=color)
        self.urls.delete("1.0", "end")
        self.urls.insert("1.0", self.url_text())
        content = ""
        for path in (ERROR_LOG, OUTPUT_LOG):
            if path.exists():
                try:
                    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-35:]
                    content += f"--- {path.name} ---\n" + "\n".join(lines) + "\n"
                except OSError:
                    pass
        self.log.delete("1.0", "end")
        self.log.insert("1.0", content or "Sin errores registrados.")
        self.after(5000, self.refresh)

    def start_server(self):
        health = server_health()
        if health:
            if is_current_server():
                messagebox.showinfo("NEGROSKY", "El servidor BUILD 055 ya está funcionando.")
                return
            if not stop_negrosky_server() or is_online():
                messagebox.showerror(
                    "NEGROSKY",
                    "Hay un servidor NEGROSKY anterior en el puerto 8030 y no se pudo cerrar automáticamente. "
                    "Cierre esa versión y vuelva a pulsar Iniciar.",
                )
                self.refresh()
                return
        python = python_path()
        if not python.exists():
            messagebox.showerror("NEGROSKY", "Primero ejecuta INSTALAR_WINDOWS.bat una sola vez.")
            return
        out = open(OUTPUT_LOG, "a", encoding="utf-8")
        err = open(ERROR_LOG, "a", encoding="utf-8")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen([str(python), "-m", "uvicorn", "core.backend.api.main:app",
                                    "--host", "0.0.0.0", "--port", str(PORT)],
                                   cwd=ROOT, stdout=out, stderr=err, creationflags=flags)
        PID_FILE.write_text(str(process.pid), encoding="ascii")
        for _ in range(20):
            self.update()
            time.sleep(.25)
            if is_online():
                self.refresh()
                return
        messagebox.showerror("NEGROSKY", "No fue posible iniciar. Revisa el registro mostrado abajo.")
        self.refresh()

    def stop_server(self):
        if not stop_negrosky_server() and is_online():
            messagebox.showwarning(
                "NEGROSKY",
                "El servidor respondió, pero no pude identificarlo como un proceso NEGROSKY. "
                "No se cerró ningún proceso por seguridad.",
            )
        self.after(600, self.refresh)

    def restart_server(self):
        self.stop_server()
        self.after(900, self.start_server)

    def backup(self):
        if not DB_FILE.exists():
            messagebox.showwarning("NEGROSKY", "Todavía no existe una base de datos.")
            return
        BACKUPS.mkdir(exist_ok=True)
        target = BACKUPS / f"negrosky_{datetime.now():%Y%m%d_%H%M%S}_control.db"
        source = sqlite3.connect(DB_FILE)
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            source.close()
            destination.close()
        messagebox.showinfo("NEGROSKY", f"Respaldo creado:\n{target.name}")

    def copy_urls(self):
        self.clipboard_clear()
        self.clipboard_append(self.url_text())
        messagebox.showinfo("NEGROSKY", "Direcciones copiadas.")


if __name__ == "__main__":
    Control().mainloop()
