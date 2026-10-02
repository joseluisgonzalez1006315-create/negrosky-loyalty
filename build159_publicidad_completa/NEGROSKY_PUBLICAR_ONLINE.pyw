import os,re,subprocess,threading,webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox,filedialog

TARGET=Path(r'C:\Negrosky\Loyalty\negrosky-loyalty-main')

def find_project(exe=None):
    if exe:
        p=Path(exe).resolve()
        # El proyecto principal es conocido; no exigimos que el ejecutable tenga un nombre específico.
        if TARGET.exists(): return TARGET,p
        for a in [p.parent,*p.parents]:
            if (a/'app').exists(): return a,p
    bases=[TARGET,Path.home()/'Downloads',Path.home()/'Desktop',Path(__file__).resolve().parent,Path(r'C:\Negrosky\Loyalty')]
    seen=set()
    for b in bases:
        if not b.exists(): continue
        for p in [b,*b.rglob('*')]:
            try:
                if p in seen: continue
                seen.add(p)
                if p.is_file() and p.suffix.lower()=='.exe' and ('cloud' in p.name.lower() or 'tunnel' in p.name.lower()):
                    if TARGET.exists(): return TARGET,p
                    for a in [p.parent,*p.parents]:
                        if (a/'app').exists(): return a,p
            except OSError: pass
    return None,None

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title('NEGROSKY · Publicar online'); self.geometry('780x540'); self.configure(bg='#090910'); self.proc=None; self.url=''; self.root,self.exe=find_project()
        ttk.Style().configure('TButton',padding=8,font=('Segoe UI',10,'bold'))
        tk.Label(self,text='NEGROSKY LOYALTY',fg='#c084fc',bg='#090910',font=('Segoe UI',20,'bold')).pack(anchor='w',padx=24,pady=(20,2))
        tk.Label(self,text='Publicación online mediante Cloudflare Tunnel',fg='white',bg='#090910',font=('Segoe UI',10)).pack(anchor='w',padx=26)
        self.status=tk.Label(self,text='Estado: detenido',fg='#fbbf24',bg='#090910',font=('Segoe UI',12,'bold')); self.status.pack(anchor='w',padx=26,pady=12)
        row=tk.Frame(self,bg='#090910'); row.pack(anchor='w',padx=24)
        self.start=ttk.Button(row,text='Publicar online',command=self.start_tunnel); self.start.pack(side='left',padx=(0,8))
        self.stop=ttk.Button(row,text='Detener',command=self.stop_tunnel); self.stop.pack(side='left',padx=(0,8))
        self.open=ttk.Button(row,text='Abrir dirección',command=lambda:webbrowser.open(self.url),state='disabled'); self.open.pack(side='left',padx=(0,8))
        ttk.Button(row,text='Buscar cloudflared',command=self.choose).pack(side='left')
        self.urlvar=tk.StringVar(value='La dirección aparecerá aquí'); tk.Entry(self,textvariable=self.urlvar,state='readonly',width=90,fg='#d8b4fe',bg='#171322',readonlybackground='#171322',relief='flat').pack(padx=24,pady=14,fill='x')
        self.log=tk.Text(self,height=18,bg='#090910',fg='#d1d5db',font=('Consolas',9),relief='flat'); self.log.pack(padx=24,pady=(0,20),fill='both',expand=True)
        self.refresh_message(); self.protocol('WM_DELETE_WINDOW',self.close)
    def refresh_message(self):
        self.log.delete('1.0','end')
        if self.root: self.write('Proyecto encontrado: '+str(self.root)); self.write('Ejecutable: '+str(self.exe)); self.start.configure(state='normal')
        else: self.write('No encontré el ejecutable de Cloudflare.'); self.write('Pulsa “Buscar cloudflared” y selecciona el archivo descargado.'); self.start.configure(state='disabled')
    def choose(self):
        f=filedialog.askopenfilename(title='Selecciona cloudflared.exe',filetypes=[('Ejecutable Cloudflare','*.exe'),('Todos','*.*')])
        if not f:return
        self.root,self.exe=find_project(f)
        if not self.root:
            messagebox.showerror('Ubicación incorrecta','No pude usar ese archivo. Selecciona el ejecutable descargado de Cloudflare.\n\nCarpeta del proyecto:\n'+str(TARGET)); return
        self.refresh_message()
    def write(self,s): self.log.insert('end',s+'\n'); self.log.see('end')
    def start_tunnel(self):
        if self.proc and self.proc.poll() is None:return
        try:
            self.proc=subprocess.Popen([str(self.exe),'tunnel','--url','http://localhost:8030','--no-autoupdate'],cwd=str(self.root),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.status.config(text='Estado: conectando...',fg='#86efac'); self.write('Iniciando túnel seguro...'); threading.Thread(target=self.read_output,daemon=True).start()
        except Exception as e: self.write('ERROR: '+str(e)); messagebox.showerror('Cloudflare',str(e))
    def read_output(self):
        for line in self.proc.stdout:
            line=line.strip()
            if line:self.after(0,lambda x=line:self.write(x))
            m=re.search(r'https://[-a-zA-Z0-9]+\.trycloudflare\.com',line)
            if m:self.after(0,lambda u=m.group(0):self.found(u))
        self.after(0,lambda:self.status.config(text='Estado: detenido',fg='#fbbf24'))
    def found(self,u): self.url=u; self.urlvar.set(u); self.open.configure(state='normal'); self.status.config(text='Estado: ONLINE',fg='#86efac'); self.write('Dirección online lista.')
    def stop_tunnel(self):
        if self.proc and self.proc.poll() is None:self.proc.terminate(); self.write('Túnel detenido.')
        self.status.config(text='Estado: detenido',fg='#fbbf24')
    def close(self): self.stop_tunnel(); self.destroy()
App().mainloop()
