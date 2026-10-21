import importlib.util,subprocess,sys,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('runner',Path(__file__).with_name('dev_runner.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class Tests(unittest.TestCase):
 def test_cleanup_preserves_data(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);cache=root/'frontend/node_modules/.vite';cache.mkdir(parents=True)
   db=root/'backend/var/states-v2.db';db.parent.mkdir(parents=True);db.write_text('saved')
   runtime=root/'runtime';runtime.mkdir();r.clear_caches(root,runtime)
   self.assertFalse(cache.exists());self.assertFalse(runtime.exists());self.assertEqual(db.read_text(),'saved')
 def test_group_shutdown(self):
  child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
  r.stop_children([child],timeout=1);self.assertIsNotNone(child.poll())
if __name__=='__main__':unittest.main()
