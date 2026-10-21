"""POSIX local-development supervisor. No third-party packages needed."""
import argparse,fcntl,os,shutil,signal,socket,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def stop_children(children,timeout=8):
 for child in children:
  try:os.killpg(child.pid,signal.SIGTERM)
  except ProcessLookupError:pass
 deadline=time.monotonic()+timeout
 while time.monotonic()<deadline and any(p.poll() is None for p in children):time.sleep(.05)
 for child in children:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  child.wait()

def clear_caches(root,runtime):
 for path in [runtime,root/'frontend/node_modules/.vite',root/'backend/.pytest_cache',root/'.pytest_cache']:
  if path.is_symlink():continue
  try:
   if path.is_dir():shutil.rmtree(path)
  except OSError as e:print('Cache cleanup warning:',e,file=sys.stderr)

def preflight(root):
 vite=root/'frontend/node_modules/vite/bin/vite.js'
 if not vite.is_file():raise RuntimeError('Vite missing. Run bash start.sh to install dependencies.')
 if not shutil.which('node'):raise RuntimeError('Node.js is missing')
 for port in (8000,5173):
  with socket.socket() as sock:
   try:sock.bind(('127.0.0.1',port))
   except OSError:raise RuntimeError(f'Port {port} is already in use. Stop the old app first; no unrelated process was killed.')
 return vite

def run():
 parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
 with (ROOT/'.life-atlas-dev.lock').open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:print('This project is already running.',file=sys.stderr);return 1
  try:vite=preflight(ROOT)
  except RuntimeError as e:print(e,file=sys.stderr);return 1
  if args.check:print('Dependencies and ports checked.');return 0
  runtime=Path(tempfile.mkdtemp(prefix='life-atlas-v2-'));env=os.environ.copy()
  env['PYTHONPYCACHEPREFIX']=str(runtime/'pycache');env['PYTHONUNBUFFERED']='1'
  commands=[([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'],ROOT/'backend'),
            ([shutil.which('node'),str(vite),'--host','127.0.0.1','--port','5173','--strictPort'],ROOT/'frontend')]
  children=[];stopping=False;code=0
  def request_stop(signum,frame):
   nonlocal stopping
   stopping=True
  for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,request_stop)
  try:
   for command,cwd in commands:
    if stopping:break
    children.append(subprocess.Popen(command,cwd=cwd,env=env,start_new_session=True))
   print('Open http://localhost:5173 when Vite is ready. Ctrl+C stops BOTH servers and clears temporary caches.',flush=True)
   while not stopping:
    for child in children:
     if child.poll() is not None:code=child.returncode or 1;stopping=True;break
    time.sleep(.1)
  except OSError as e:print('Startup failed:',e,file=sys.stderr);code=1
  finally:
   for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,signal.SIG_IGN)
   stop_children(children);clear_caches(ROOT,runtime)
   print('Both servers stopped. Temporary caches cleared. Saved lives and datasets preserved.',flush=True)
  return code
if __name__=='__main__':raise SystemExit(run())
