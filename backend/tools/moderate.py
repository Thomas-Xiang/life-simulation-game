import argparse
from app.main import db,initialize
p=argparse.ArgumentParser();p.add_argument('--approve');p.add_argument('--reject');a=p.parse_args();initialize()
with db() as c:
 if a.approve:c.execute('UPDATE memorials SET approved=1 WHERE id=?',(a.approve,))
 elif a.reject:
  c.execute('DELETE FROM candles WHERE memorial_id=?',(a.reject,));c.execute('DELETE FROM memorials WHERE id=?',(a.reject,))
 else:
  for r in c.execute('SELECT * FROM memorials WHERE approved=0'):print(dict(r))
