import json
import pytest
from fastapi.testclient import TestClient
from app.main import app,db,requests
from app import simulation as s
@pytest.fixture
def client(tmp_path,monkeypatch):
 monkeypatch.setenv('DB_PATH',str(tmp_path/'test.db'));requests.clear()
 with TestClient(app) as c:yield c

def born(c):
 r=c.post('/api/lives',json={'home_state':'TX'});assert r.status_code==201
 b=r.json();return b,{'Authorization':'Bearer '+b['token']}

def test_health_states(client):
 assert client.get('/api/health').json()['states']==51
 assert len(client.get('/api/states').json())==51

def test_invalid_state(client):assert client.post('/api/lives',json={'home_state':'ZZ'}).status_code==422

def test_auth_version_persistence(client):
 b,h=born(client);url='/api/lives/'+b['life']['id']
 assert client.get(url).status_code==404
 assert client.post(url+'/step',headers=h,json={'version':99}).status_code==409
 r=client.post(url+'/step',headers=h,json={'version':0});assert r.status_code==200
 assert client.get(url,headers=h).json()['life']['version']==1
 assert client.post(url+'/step',headers=h,json={'version':0}).status_code==409

def test_choices_gated_and_saved(client):
 b,h=born(client);id=b['life']['id'];url='/api/lives/'+id;l=b['life'];l['age']=18;s.open_chapter(l,'school',['path'])
 with db() as c:c.execute('UPDATE lives SET state=? WHERE id=?',(json.dumps(l),id))
 q=client.get(url,headers=h).json()['question']
 assert client.post(url+'/choice',headers=h,json={'version':0,'question_id':q['id'],'option_id':'physician'}).status_code==409
 assert client.post(url+'/step',headers=h,json={'version':0}).status_code==409
 r=client.post(url+'/choice',headers=h,json={'version':0,'question_id':q['id'],'option_id':'work'});assert r.status_code==200
 assert r.json()['question']['key']=='career'
 assert client.get(url,headers=h).json()['life']['answers'][0]['option']=='Work now / continue working'

def test_compare_export_delete(client):
 b,h=born(client);url='/api/lives/'+b['life']['id']
 assert len(client.get(url+'/compare',headers=h).json())==51
 assert len(client.get(url+'/survival',headers=h).json())==121
 assert client.get(url+'/export',headers=h).json()['money_unit']=='USD cents'
 assert client.delete(url,headers=h).status_code==204
 assert client.get(url,headers=h).status_code==404

def test_memorial_requires_death_and_moderation(client):
 b,h=born(client);id=b['life']['id'];url='/api/lives/'+id
 assert client.post(url+'/memorial',headers=h,json={'message':'hello'}).status_code==409
 l=b['life'];l.update(complete=True,alive=False,end_reason='death')
 with db() as c:c.execute('UPDATE lives SET state=? WHERE id=?',(json.dumps(l),id))
 assert client.post(url+'/memorial',headers=h,json={'message':'A life.'}).status_code==201
 assert client.get('/api/memorials').json()==[]
 with db() as c:
  row=c.execute('SELECT id FROM memorials').fetchone();mid=row['id'];c.execute('UPDATE memorials SET approved=1')
 token={'Authorization':'Bearer '+'x'*40}
 assert client.post('/api/memorials/'+mid+'/candle',headers=token).json()['added']
 assert not client.post('/api/memorials/'+mid+'/candle',headers=token).json()['added']
 assert client.get('/api/memorials').json()[0]['candles']==1

def test_large_request_rejected(client):assert client.post('/api/lives',content='x'*17000).status_code==413
