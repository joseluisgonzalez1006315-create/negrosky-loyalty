from pathlib import Path
from datetime import datetime
import ast,zipfile
OLD = '    target = f"{request.url.scheme}://{host}:{request.url.port or 8030}/q/{tenant[\'public_key\']}"'
NEW = '    # Preserve public HTTPS ports; 8030 is not a default for cloud URLs.\n    authority = f"[{host}]" if ":" in host else host\n    if request.url.port is not None:\n        authority += f":{request.url.port}"\n    target = f"{request.url.scheme}://{authority}/q/{tenant[\'public_key\']}"'

def apply(root):
 p=root/'app'/'main.py'
 s=p.read_text(encoding='utf-8')
 if NEW in s: print('El parche QR ya esta aplicado.');return
 if s.count(OLD)!=1: raise RuntimeError('Version diferente. No se modifico nada; envia tu ZIP actual.')
 result=s.replace(OLD,NEW,1);ast.parse(result)
 folder=Path.home()/'NEGROSKY_RESPALDOS';folder.mkdir(exist_ok=True)
 backup=folder/('antes_parche_qr_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.zip')
 with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED) as z:z.write(p,'app/main.py')
 p.write_text(result,encoding='utf-8')
 print('PARCHE QR APLICADO. Publica tu carpeta completa y descarga de nuevo el QR del negocio.')
 print('Respaldo del codigo: '+str(backup))
if __name__=='__main__':
 try:apply(Path(__file__).resolve().parent)
 except Exception as e:print('ERROR: '+str(e));raise SystemExit(1)
