import copy,json,math,random
from pathlib import Path
import pytest
from app import simulation as s
ZERO={'male':[0.0]*120,'female':[0.0]*120}
def life(age=18):
 l=s.new_life('TX','seed','test');l['sex']='female';l['age']=age;return l

def finish(l,choices=None):
 choices=choices or {}
 for _ in range(30):
  q=s.question(l)
  if not q:return l
  ids=[o['id'] for o in q['options']];assert len(ids)==len(set(ids))
  value=choices.get(q['key'],ids[0]);assert value in ids,(q['key'],value,ids)
  s.choose(l,q['id'],value)
 raise AssertionError('Chapter did not terminate')

def test_all_states_and_tiles_unique():
 assert len(s.STATES)==51
 assert len({(x['x'],x['y']) for x in s.STATES.values()})==51
 assert all(x['cost']>0 and x['wage']>0 for x in s.STATES.values())

def test_no_yearly_questions():
 l=life(17);s.advance(l,'seed',ZERO)
 assert s.question(l)['key']=='path'
 finish(l,{'path':'work','career':'retail','relocate':'TX','housing':'shared'})
 for age in range(19,30):
  s.advance(l,'seed',ZERO);assert l['age']==age;assert s.question(l) is None
 s.advance(l,'seed',ZERO);assert l['age']==30 and s.question(l)

def test_bachelor_completion_at22():
 l=life();s.open_chapter(l,'school',['path'])
 finish(l,{'path':'bachelor','major':'computing','premed':'no','housing':'shared'})
 for age in (19,20,21):s.advance(l,'seed',ZERO);assert l['age']==age and not l['chapter']
 s.advance(l,'seed',ZERO)
 assert l['age']==22 and 'bachelor:computing' in l['credentials'] and l['chapter']
 assert 'developer' in dict(s.jobs(l))
 assert 'physician' not in dict(s.jobs(l))

def test_cc_transfer():
 l=life();s.open_chapter(l,'school',['path'])
 finish(l,{'path':'cc','major':'computing','housing':'shared'})
 s.advance(l,'seed',ZERO);s.advance(l,'seed',ZERO)
 assert s.question(l)['key']=='transfer'
 finish(l,{'transfer':'same','premed':'no','housing':'shared'})
 s.advance(l,'seed',ZERO);assert not l['chapter']
 s.advance(l,'seed',ZERO);assert 'bachelor:computing' in l['credentials']

def test_cc_change_major_extra_year():
 l=life(20);l['credentials']=['cc:finance'];l['major']='finance';s.open_chapter(l,'cc',['transfer'])
 finish(l,{'transfer':'change','major':'computing','premed':'no','housing':'shared'})
 assert l['program']['remaining']==3 and l['program']['major']=='computing'

def test_medicine_chain():
 l=life();s.open_chapter(l,'school',['path'])
 finish(l,{'path':'bachelor','major':'humanities','premed':'yes','housing':'shared'})
 for _ in range(4):s.advance(l,'seed',ZERO)
 finish(l,{'path':'medical','housing':'shared'})
 for _ in range(4):s.advance(l,'seed',ZERO)
 assert l['age']==26 and 'medical' in l['credentials']
 finish(l,{'residency':'residency'})
 for _ in range(3):s.advance(l,'seed',ZERO)
 assert l['age']==29 and s.question(l)['key']=='license'
 finish(l,{'license':'complete','career':'physician','relocate':'TX','housing':'shared'})
 assert l['career']=='physician' and 'physician_license' in l['credentials']

def test_forged_career_rejected():
 l=life();s.open_chapter(l,'job',['career']);before=copy.deepcopy(l)
 with pytest.raises(ValueError):s.choose(l,s.question(l)['id'],'physician')
 assert l==before

def test_license_alone_not_physician():
 l=life();l['credentials']=['physician_license'];assert 'physician' not in dict(s.jobs(l))

def test_state_pay_premiums_and_costs():
 l=life();l['career']='developer';assert s.salary(l,'CA')>s.salary(l,'TX')
 l['career']='finance';assert s.salary(l,'NY')>s.salary(l,'TX')
 assert s.annual_cost(l,'CA','shared')>s.annual_cost(l,'TX','shared')

def test_parents_save_costs_and_move_loses_housing():
 l=life();l['family']['housing']=True;l['housing']='parents';l['cash']=s.cents(10000)
 assert s.annual_cost(l,housing='parents')<s.annual_cost(l,housing='shared')
 old=l['cash'];cost=s.moving_cost('TX','CA');s.move(l,'CA')
 assert l['cash']==old-cost and l['housing']=='shared'
 with pytest.raises(ValueError):s.quote(l,'CA','parents')

def test_family_reproducible_independent_of_state():
 a=s.new_life('TX','same','a');b=s.new_life('CA','same','b')
 assert a['family']==b['family']
 assert len({s.new_life('TX',str(i),'x')['family']['level'] for i in range(50)})==3

def test_support_stops_at26():
 l=life(25);l['family']['annual_gift']=10000;assert s.support(l)>0
 l['age']=26;assert s.support(l)==0

def test_tuition_and_deficits_create_debt():
 l=life();l['family']['annual_gift']=l['family']['tuition_gift']=0;s.enroll(l,'medical');s.annual_finance(l,'seed')
 assert l['student_debt']>0 and l['other_debt']>0 and l['cash']>=0
 assert s.balance(l)['net_worth']<0

def test_home_buy_cash_and_networth_identity():
 l=life(30);l['career']='developer';l['cash']=s.cents(150000)
 t=s.buy_terms(l);assert t['eligible'];old=s.balance(l)['net_worth']
 s.open_chapter(l,'home',['housing']);finish(l,{'housing':'buy'})
 assert l['mortgage']==t['loan'] and l['home_value']==t['price']
 assert abs(s.balance(l)['net_worth']-(old-round(t['price']*.03)))<=1
 old_m=l['mortgage'];s.annual_finance(l,'seed');assert l['mortgage']<old_m

def test_home_gate_prevents_purchase():
 l=life();l['career']='retail';s.open_chapter(l,'home',['housing'])
 assert 'buy' not in [o['id'] for o in s.question(l)['options']]

def test_sell_repays_mortgage_and_fee():
 l=life();l.update(cash=1000000,home_value=20000000,mortgage=15000000,mortgage_payment=1000000)
 before=s.balance(l)['net_worth'];s.sell(l)
 assert s.balance(l)['net_worth']==before-1200000
 assert not l['home_value'] and not l['mortgage']

def test_dependent_cost_expires():
 l=life(40);l['dependent_ages']=[17];l['dependents']=1;before=s.annual_cost(l)
 s.advance(l,'seed',ZERO);assert l['dependents']==0 and s.annual_cost(l)<before

def test_debt_interest_not_negative():
 l=life();l['career']='caregiving';l['student_debt']=100000;s.annual_finance(l,'seed')
 assert l['student_debt']>=105000 and l['other_debt']>0 and l['cash']==0

def test_retirement_projection_consistent():
 l=life(65);l['retired']=True;q=s.quote(l,'TX','shared');s.annual_finance(l,'seed')
 assert q['income']==l['income']==s.cents(18000)

def test_national_table_survivor_crosscheck():
 m=json.loads((Path(__file__).parents[1]/'data/mortality.json').read_text())
 for sex,expected in [('male',50785),('female',64606)]:
  assert len(m[sex])==120
  assert abs(100000*math.prod(1-q for q in m[sex][:80])-expected)<2

def test_random_paths_no_negative_balances_or_infinite_chapters():
 r=random.Random(7)
 for seed in range(20):
  l=life(17)
  for _ in range(104):
   for _ in range(30):
    q=s.question(l)
    if not q:break
    s.choose(l,q['id'],r.choice(q['options'])['id'])
   else:raise AssertionError('Infinite chapter')
   if l['complete']:break
   s.advance(l,str(seed),ZERO)
   assert all(l[k]>=0 for k in ['cash','student_debt','other_debt','mortgage','home_value'])
   b=s.balance(l);assert b['net_worth']==b['assets']-b['debt']
