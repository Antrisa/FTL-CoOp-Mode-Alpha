"""Back up/install this package's DLL and launch FTL using OpenGL."""
from pathlib import Path
import hashlib,shutil,subprocess,time,json,tkinter as tk
from tkinter import filedialog,messagebox
ROOT=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def install_and_launch(exe):
    exe=Path(exe).resolve()
    if exe.name.lower()!='ftlgame.exe' or not exe.is_file():raise ValueError('Select FTLGame.exe in your game installation.')
    source=ROOT.parent/'native_bin'/'Hyperspace.dll'
    dest=exe.parent/'Hyperspace.dll'
    if not source.exists():
        manifest=ROOT.parent/'BUILD_INFO.json'
        expected=json.loads(manifest.read_text()).get('dll_sha256') if manifest.exists() else None
        if not expected or not dest.exists() or sha(dest)!=expected:
            raise ValueError('Package DLL is missing and the installed DLL could not be verified. Extract the complete package again.')
        subprocess.Popen([str(exe),'--force-opengl'],cwd=str(exe.parent))
        return expected
    if not dest.exists() or sha(dest)!=sha(source):
        if dest.exists():shutil.copy2(dest,dest.with_name('Hyperspace.before-v02816-'+str(time.time_ns())+'.dll.bak'))
        shutil.copy2(source,dest)
    if sha(dest)!=sha(source):raise RuntimeError('DLL verification failed. FTL has not been started.')
    subprocess.Popen([str(exe),'--force-opengl'],cwd=str(exe.parent))
    return sha(dest)
def main():
    root=tk.Tk();root.withdraw()
    try:
        exe=filedialog.askopenfilename(title='Select FTLGame.exe — backs up/installs v0.28.16 DLL and launches OpenGL',filetypes=[('FTL game','FTLGame.exe')])
        if exe:install_and_launch(exe)
    except Exception as exc:messagebox.showerror('Fleet Co-op launch',str(exc)+'\nClose FTL and FTL Manager first. Leave the package folders together.')
    finally:root.destroy()
if __name__=='__main__':main()
