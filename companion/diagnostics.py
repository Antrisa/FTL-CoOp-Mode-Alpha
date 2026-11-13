"""File diagnostics independent of PowerShell output; inert when imported in tests."""
import atexit
import faulthandler
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os
import sys
import threading
import time
import traceback

logger=logging.getLogger('fleet.diagnostics')
logger.addHandler(logging.NullHandler())
logger.propagate=False
_stop=threading.Event()
_last_tick=time.monotonic()
_stage='startup'
_active=False
_fault_file=None

def record(message):
    logger.info(message)

def exception(where):
    logger.error('%s\n%s',where,traceback.format_exc())

def mark(stage):
    global _last_tick,_stage
    _stage=stage;_last_tick=time.monotonic()

def dump(reason):
    names={t.ident:t.name for t in threading.enumerate()}
    chunks=[reason+'; stage='+_stage]
    for ident,frame in sys._current_frames().items():
        chunks.append('Thread '+str(ident)+' '+names.get(ident,'unknown')+'\n'+''.join(traceback.format_stack(frame)))
    record('\n'.join(chunks))

def tk_error(kind,value,tb):
    logger.error('TK CALLBACK ERROR\n%s',''.join(traceback.format_exception(kind,value,tb)))
    dump('Tk callback failed; UI polling may have stopped')

def thread_error(args):
    logger.error('THREAD ERROR %s\n%s',args.thread.name if args.thread else '?',''.join(traceback.format_exception(args.exc_type,args.exc_value,args.exc_traceback)))

def main_error(kind,value,tb):
    logger.error('MAIN ERROR\n%s',''.join(traceback.format_exception(kind,value,tb)))
    sys.__excepthook__(kind,value,tb)

def _watch():
    last_dump=time.monotonic();reported=False
    while not _stop.wait(2):
        age=time.monotonic()-_last_tick
        if age>8 and not reported:
            dump('UI heartbeat missing for %.1fs'%age);reported=True
        elif age<=8:reported=False
        if time.monotonic()-last_dump>=30:
            dump('Periodic snapshot; UI age %.1fs'%age);last_dump=time.monotonic()

def start(folder):
    global _active,_fault_file
    if _active:return
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    handler=RotatingFileHandler(folder/'fleet_diagnostics.txt',maxBytes=4*1024*1024,backupCount=1,encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(threadName)s %(message)s'))
    logger.addHandler(handler);logger.setLevel(logging.INFO)
    _active=True;_stop.clear();mark('startup')
    record('START v0.28.16 pid=%s Python=%s executable=%s'%(os.getpid(),sys.version,sys.executable))
    _fault_file=open(folder/'fleet_faults.txt','w',buffering=1,encoding='utf-8')
    _fault_file.write('Native fault diagnostics active\n');_fault_file.flush()
    faulthandler.enable(file=_fault_file,all_threads=True)
    threading.excepthook=thread_error;sys.excepthook=main_error
    threading.Thread(target=_watch,name='FleetDiagnostics',daemon=True).start()
    atexit.register(stop)

def stop():
    _stop.set()
    if _active:record('PROCESS EXIT')
