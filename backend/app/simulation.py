"""Milestone life game. All dollar amounts, support distributions and state multipliers
are synthetic scenario parameters, not statistics or advice. Money uses integer cents.
"""
from pathlib import Path
import copy, hashlib, json, random

STATES = {s['code']:s for s in json.loads((Path(__file__).resolve().parents[1]/'data/states.json').read_text())}
MAJORS = {'computing':'Computing','finance':'Finance / business','biology':'Biology',
          'engineering':'Engineering','education':'Education','nursing':'Nursing',
          'humanities':'Humanities / communications','arts':'Arts / design'}
BASE_PAY = {'retail':34000,'logistics':40000,'office':42000,'trade':62000,
 'it_support':50000,'developer':85000,'finance':78000,'lab':49000,'engineer':76000,
 'teacher':52000,'nurse':69000,'communications':50000,'designer':48000,
 'resident':60000,'physician':180000,'retired':0,'caregiving':0,'student':0,'none':0}
SECTORS = {'developer':'technology','it_support':'technology','finance':'finance','lab':'biotech',
 'engineer':'manufacturing','teacher':'public_service','nurse':'healthcare','physician':'healthcare',
 'logistics':'logistics','retail':'hospitality','designer':'technology','communications':'public_service','trade':'manufacturing'}
PROGRAMS = {'cc':(2,6000),'bachelor':(4,18000),'certificate':(1,4500),
 'trade':(4,2000),'medical':(4,45000),'residency':(3,0),'prep':(2,10000)}

def rng(seed,label):
 return random.Random(int.from_bytes(hashlib.sha256(f'{seed}:{label}'.encode()).digest(),'big'))

def cents(value): return round(value*100)
def dollars(value): return round(value/100,2)
def event(l,title,text): l['history'].append({'age':l['age'],'title':title,'text':text})

def new_life(home,seed,life_id):
 if home not in STATES: raise ValueError('Unknown home state')
 r=rng(seed,'family')
 # Deliberately uniform fictional support scenarios, independent of state and identity.
 level=r.choice(['limited','moderate','strong'])
 gift,tuition,starter={'limited':(0,0,500),'moderate':(2400,3500,2500),'strong':(6000,10000,8000)}[level]
 housing=r.random()<.75
 l={'id':life_id,'version':0,'age':0,'alive':True,'complete':False,'end_reason':None,
 'home_state':home,'state':home,'career':'none','major':'','credentials':[], 'program':None,
 'housing':'parents' if housing else 'shared','family':{'level':level,'housing':housing,
 'annual_gift':cents(gift),'tuition_gift':cents(tuition),'starter':cents(starter),'until_age':26},
 'cash':0,'student_debt':0,'other_debt':0,'mortgage':0,'home_value':0,'mortgage_payment':0,
 'income':0,'expenses':0,'tax':0,'annual_support':0,'cashflow':0,'experience':0,
 'relationship':'independent','dependents':0,'wellbeing':'routine','retired':False,
 'scores':{'health':80,'happiness':60,'knowledge':0,'relationships':60},
 'chapter':None,'queue':[],'answers':[],'history':[],'ledger':[],'moves':[],
 'dependent_ages':[], 'education_reviewed':False,'job_due':False,'transfer_intent':'','last_milestone':None}
 event(l,'A new beginning',f"Home: {STATES[home]['name']}. Fictional family support: {level}; housing support {'available' if housing else 'unavailable'}.")
 return l

def balance(l):
 return {'assets':l['cash']+l['home_value'],'debt':l['student_debt']+l['other_debt']+l['mortgage'],
 'net_worth':l['cash']+l['home_value']-l['student_debt']-l['other_debt']-l['mortgage']}

def spend(l,amount,student=False):
 amount=max(0,int(amount)); paid=min(l['cash'],amount);l['cash']-=paid
 l['student_debt' if student else 'other_debt']+=amount-paid

def salary(l,state=None):
 if l['retired']:return 0
 code=state or l['state'];s=STATES[code];role=l['career']
 if l['program']:
  role={'trade':'trade','residency':'resident'}.get(l['program']['kind'],'student')
  if role=='trade':return cents(26000*s['wage'])
  if role=='student':return cents(9000*s['wage']) # explicit part-time study income scenario
 base=BASE_PAY.get(role,0)
 premium=1.22 if SECTORS.get(role)==s['sector'] else 1.0
 if role=='developer' and code=='CA':premium=1.35
 if role=='finance' and code=='NY':premium=1.35
 growth=1+min(l['experience'],25)*.015
 return cents(base*s['wage']*premium*growth)

def annual_cost(l,state=None,housing=None):
 code=state or l['state'];s=STATES[code];h=housing or l['housing']
 base=cents(12000*s['cost'])
 if h=='parents' and code==l['home_state'] and l['family']['housing']:
  home=cents(3000*s['cost'])
 elif h=='own':home=l['mortgage_payment']+round(l['home_value']*.025)
 else:home=cents((10800 if h=='shared' else 18000)*s['cost'])
 health={'routine':300,'active':650,'support':1000}.get(l['wellbeing'],300)
 return base+home+cents(health)+cents(l['dependents']*6500*s['cost'])

def support(l):
 if l['age']>=l['family']['until_age']:return 0
 return l['family']['annual_gift']+(l['family']['tuition_gift'] if l['program'] and l['program']['kind']!='residency' else 0)

def quote(l,code,housing='shared'):
 if code not in STATES:raise ValueError('Unknown state')
 if housing=='parents' and not (code==l['home_state'] and l['family']['housing']):raise ValueError('Family housing unavailable')
 income=cents(18000) if l['retired'] else salary(l,code);tax=round(income*.22) # game-wide combined effective deduction, not state tax law
 costs=annual_cost(l,code,housing)
 tuition=cents(PROGRAMS[l['program']['kind']][1]) if l['program'] else 0
 move=0 if code==l['state'] else moving_cost(l['state'],code)
 debt_service=round(l['student_debt']*.08)+round(l['other_debt']*.18)
 return {'state':code,'housing':housing,'income':income,'tax':tax,'living_cost':costs,
 'tuition':tuition,'support':support(l),'debt_service_estimate':debt_service,
 'surplus':income-tax-costs-tuition+support(l)-debt_service,'moving_cost':move,
 'note':'Synthetic annual comparison; debt-service estimate is approximate. No state tax law, real job offer or affordability guarantee.'}

def moving_cost(a,b):
 # Flat fictional interstate cost; tile coordinates are not geographic distances.
 return 0 if a==b else cents(3500)


def buy_terms(l):
 price=cents(220000*STATES[l['state']]['cost']);loan=round(price*.8)
 rate=.06/12;n=360;monthly=round(loan*rate/(1-(1+rate)**-n))
 return {'price':price,'cash_needed':round(price*.23),'loan':loan,'annual_payment':monthly*12,
 'eligible':not l['program'] and salary(l)>0 and l['cash']>=round(price*.23) and monthly*12<=salary(l)*.30 and not l['home_value']}

def sell(l):
 if not l['home_value']:return
 proceeds=round(l['home_value']*.94)-l['mortgage']
 if proceeds>=0:l['cash']+=proceeds
 else:spend(l,-proceeds)
 l['home_value']=l['mortgage']=l['mortgage_payment']=0

def move(l,code):
 if code==l['state']:return
 cost=moving_cost(l['state'],code);old=l['state'];sell(l);spend(l,cost)
 l['state']=code;l['housing']='shared'
 l['moves'].append({'age':l['age'],'from':old,'to':code,'cost':cost})
 event(l,'A new state',f"Moved from {old} to {code}; modeled moving cost ${cost/100:,.0f}. Shared renting replaces family housing.")

def enroll(l,kind,years=None):
 duration,_=PROGRAMS[kind]
 l['program']={'kind':kind,'remaining':duration if years is None else years,'major':l['major']}
 l['career']='resident' if kind=='residency' else 'student';l['education_reviewed']=False
 event(l,'Education begins',f"{kind}: {l['program']['remaining']} modeled years. Tuition and living costs accrue annually; no credential granted yet.")

def jobs(l):
 c=set(l['credentials']);o=([('keep','Keep the current career and experience')] if l['career'] not in {'none','student','resident'} else [])+[('retail','Retail / service'),('logistics','Logistics'),('office','Office support'),('caregiving','Unpaid caregiving')]
 if 'certificate' in c or 'cc:computing' in c:o+=[('it_support','IT support')]
 if 'trade' in c:o+=[('trade','Skilled electrical-trade scenario (modeled qualification)')]
 for major,role,label in [('computing','developer','Software / web development'),('finance','finance','Finance / business analyst'),('biology','lab','Laboratory support'),('engineering','engineer','Graduate engineering-team role'),('education','teacher','Teaching scenario (modeled certification)'),('nursing','nurse','Nursing scenario (modeled licensure)'),('humanities','communications','Communications'),('arts','designer','Design')]:
  if 'bachelor:'+major in c or (major=='nursing' and 'cc:nursing' in c):o.append((role,label))
 if {'physician_license','medical','residency'}.issubset(c) and any(x.startswith('bachelor:') for x in c):o.append(('physician','Primary-care physician'))
 return o

def q(l,key,title,opts,help=''):
 return {'id':f"{l['chapter']}:{key}",'key':key,'title':title,'help':help,
 'options':[{'id':i,'label':label,'impact':impact(l,key,i)} for i,label in opts]}

def impact(l,key,value):
 if key=='path' and value in PROGRAMS:
  years,tuition=PROGRAMS[value];return f'{years} modeled years; tuition ${tuition:,}/year + living costs. Shortfalls become debt; family support may offset costs.'
 if key=='major':return 'Changes eligible graduate career paths; no degree awarded until completion.'
 if key=='career':
  temp=copy.deepcopy(l);temp['career']=l['career'] if value=='keep' else value;temp['program']=None
  return f"Modeled gross ${salary(temp)/100:,.0f}/year here; taxes and living costs deducted annually."
 if key=='relocate':
  r=quote(l,value,'parents' if value==l['home_state'] and l['family']['housing'] else 'shared')
  return f"Gross ${r['income']/100:,.0f}/yr; estimated surplus ${r['surplus']/100:,.0f}/yr; moving ${r['moving_cost']/100:,.0f}. Housing chosen next."
 if key=='housing':
  if value=='buy':
   t=buy_terms(l);return f"Cash ${t['cash_needed']/100:,.0f} (20% down + 3% closing); loan ${t['loan']/100:,.0f}; payments ${t['annual_payment']/100:,.0f}/yr + upkeep."
  return f"Modeled total living cost ${annual_cost(l,housing=value)/100:,.0f}/yr, including housing, basics, wellbeing and dependents."
 if key=='transfer':return 'Transfer adds tuition years and changes future job eligibility; keeping the associate credential avoids new tuition.'
 if key=='family':return 'Parenting chapter adds one modeled dependent and $6,500 × state cost/year until the modeled dependent reaches 18; no partner income is assumed.' if value=='parent' else 'No new dependent costs; existing dependents remain.'
 if key=='wellbeing':return {'routine':'$300/year support budget.','active':'$650/year activity budget.','support':'$1,000/year professional-support budget.'}[value]+' Fictional happiness index +1/+3/+2 for routine/activity/support; no mortality effect or medical promise.'
 if key=='relationship':return 'Narrative relationship state only; no assumed spouse income, debt or joint assets.'
 if key=='retire':return 'Retirement stops wages; a synthetic $18,000/year income replaces them. Not an actual benefit estimate.' if value=='yes' else 'Continue modeled wages and annual expenses.'
 if key=='premed':return 'Adds prerequisite preparation to this degree; not automatic medical-school admission.'
 if key=='license':return 'A modeled completion scenario, not a real license; costs $1,500 and opens the physician direction.' if value=='complete' else 'No fee; physician direction remains unavailable.'
 return 'Saved story choice; its effect is reflected in the next available options.'

def question(l):
 if not l['chapter'] or l['complete']:return None
 while l['queue']:
  key=l['queue'][0];c=set(l['credentials'])
  if key=='path':
   opts=[('work','Work now / continue working')]
   if not l['program']:
    if not any(x.startswith('bachelor:') for x in c):opts += [('cc','Community college'),('bachelor','Four-year college'),('certificate','IT certificate'),('trade','Apprenticeship')]
    if any(x.startswith('bachelor:') for x in c) and 'medical' not in c:
     opts += [('medical','Medical-school scenario')] if 'premed' in c else [('prep','Post-baccalaureate medical prerequisites')]
    if 'medical' in c and 'residency' not in c:opts.append(('residency','Begin primary-care residency'))
    if 'residency' in c and 'physician_license' not in c:opts.append(('licensing','Revisit the physician licensing chapter'))
   return q(l,key,'Your next major direction',opts,'Admissions/placements are player-selected fictional scenarios, not predicted acceptance. Choosing work does not close later learning.')
  if key=='major':return q(l,key,'Choose your field of study',list(MAJORS.items()))
  if key=='premed':return q(l,key,'Prepare medical-school prerequisites alongside your degree?',[('yes','Add premedical preparation'),('no','Focus on this major')],'Any major can lead toward medicine with prerequisites; biology alone does not qualify a physician.')
  if key=='transfer':return q(l,key,'Associate pathway completed: what next?',[('same','Transfer in the same field: 2 modeled years'),('change','Transfer and change field: 3 modeled years'),('work','Use this credential and pursue work')],'Credit acceptance and admission are simplified scenario assumptions, not guaranteed real transfers.')
  if key=='residency':return q(l,key,'Medical school completed',[('residency','Begin primary-care residency: 3 modeled years'),('work','Pursue non-physician work for now')])
  if key=='license':return q(l,key,'Residency completed: licensing chapter',[('complete','Complete modeled exams and state-licensing requirements'),('later','Defer; physician role stays unavailable')])
  if key=='career':return q(l,key,'Choose a qualified career direction',jobs(l),'Career offers and licensure for non-physician regulated roles are simplified story scenarios; actual requirements vary.')
  if key=='relocate':return q(l,key,'Stay near home or move for opportunity?',[(code,STATES[code]['name']+(' · current' if code==l['state'] else '')) for code in STATES], 'All 50 states + DC. The map previews the same synthetic salary/cost model. A higher salary can leave less after costs.')
  if key=='housing':
   opts=[('shared','Rent with roommates'),('rent','Rent independently')]
   if l['state']==l['home_state'] and l['family']['housing']:opts.insert(0,('parents','Live with parents / family support'))
   if l['home_value']:opts.insert(0,('own','Keep your owned home'))
   elif buy_terms(l)['eligible']:opts.append(('buy','Buy the modeled starter home'))
   return q(l,key,'Choose your housing',opts,'Buying appears only with enough cash and the game affordability gate. Not mortgage approval. Moving or renting after ownership sells at carrying value minus 6% fee.')
  if key=='wellbeing':return q(l,key,'Choose a wellbeing budget',[('routine','Everyday routine'),('active','Activity and recreation'),('support','Access to professional support')])
  if key=='relationship':return q(l,key,'Choose your relationship chapter',[('independent','Independent life'),('community','Friendships and community'),('partner','Committed partnership'),('married','Marriage story')])
  if key=='family':return q(l,key,'Family and caregiving chapter',[('parent','Add one dependent in this fictional story'),('later','No additional dependent now'),('care','Support relatives / chosen family')],'This is a player-authored story, not a prediction about family formation.')
  if key=='retire':return q(l,key,'Work and retirement',[('yes','Retire in this scenario'),('no','Keep working')])
  l['queue'].pop(0)
 l['chapter']=None
 return None

def open_chapter(l,label,keys):
 l['chapter']=f"{l['age']}:{label}";l['queue']=list(keys);l['last_milestone']=label

def choose(l,question_id,option_id):
 current=question(l)
 if not current or current['id']!=question_id:raise ValueError('Question changed; reload the life')
 opts={o['id']:o for o in current['options']}
 if option_id not in opts:raise ValueError('Ineligible choice')
 key=current['key'];l['queue'].pop(0);value=option_id
 if key=='path':
  if value=='work':l['program']=None;l['queue']=['career','relocate','housing']+l['queue']
  elif value=='licensing':l['queue']=['license']+l['queue']
  else:
   enroll(l,value)
   if value in {'cc','bachelor'}:l['queue']=['major']+(['premed'] if value=='bachelor' else [])+['housing']+l['queue']
   else:l['queue']=['housing']+l['queue']
 elif key=='major':l['major']=value;l['program']['major']=value
 elif key=='premed':l['program']['premed']=value=='yes'
 elif key=='transfer':
  if value=='work':l['queue']=['career','relocate','housing']+l['queue']
  else:
   enroll(l,'bachelor',2 if value=='same' else 3)
   l['queue']=(['major'] if value=='change' else [])+['premed','housing']+l['queue']
 elif key=='residency':
  if value=='residency':enroll(l,'residency')
  else:l['queue']=['career','relocate','housing']+l['queue']
 elif key=='license':
  if value=='complete':
   spend(l,cents(1500));l['credentials'].append('physician_license')
  l['queue']=['career','relocate','housing']+l['queue']
 elif key=='career':
  if value!='keep':l['career']=value;l['experience']=0
 elif key=='relocate':move(l,value)
 elif key=='housing':
  if value=='buy':
   terms=buy_terms(l)
   if not terms['eligible']:raise ValueError('Home purchase no longer eligible')
   l['cash']-=terms['cash_needed'];l['home_value']=terms['price'];l['mortgage']=terms['loan'];l['mortgage_payment']=terms['annual_payment'];l['housing']='own'
  else:
   if l['home_value'] and value!='own':sell(l)
   l['housing']=value
 elif key=='wellbeing':l['wellbeing']=value;l['scores']['happiness']=min(100,l['scores']['happiness']+{'routine':1,'active':3,'support':2}[value])
 elif key=='relationship':l['relationship']=value
 elif key=='family':
  if value=='parent':l['dependents']+=1;l['dependent_ages'].append(0)
  if value=='care':l['scores']['relationships']=min(100,l['scores']['relationships']+3)
 elif key=='retire':
  l['retired']=value=='yes'
 l['answers'].append({'age':l['age'],'question':current['title'],'option':opts[value]['label'],'impact':opts[value]['impact']})
 event(l,current['title'],opts[value]['label']+'. '+opts[value]['impact'])
 l['queue']=list(dict.fromkeys(l['queue']))
 l['version']+=1;question(l)
 return l

def annual_finance(l,seed):
 if l['age']<18:return
 income=cents(18000) if l['retired'] else salary(l)
 taxes=round(income*.22);living=annual_cost(l);tuition=cents(PROGRAMS[l['program']['kind']][1]) if l['program'] else 0
 gifts=support(l);r=rng(seed,f"support:{l['age']}")
 if l['age']<26 and l['family']['level']!='limited' and r.random()<.18:
  extra=cents(r.choice([500,1000,1500]));gifts+=extra
  event(l,'A family boost',f'Fictional extra family gift: ${extra/100:,.0f}.')
 l['cash']+=income-taxes+gifts
 # Tuition financed separately to distinguish education debt from living deficits.
 spend(l,tuition,student=True)
 # Mortgage is included in living outflow; principal reduces liability, not an expense twice.
 if l['mortgage']:
  scheduled=l['mortgage_payment'];actual=0
  for _ in range(12):
   interest=round(l['mortgage']*.06/12);payment=min(l['mortgage_payment']//12,l['mortgage']+interest)
   actual+=payment
   l['mortgage']=max(0,l['mortgage']-(payment-interest))
  living+=actual-scheduled
  if not l['mortgage']:l['mortgage_payment']=0
 spend(l,living)
 student_interest=round(l['student_debt']*.05);other_interest=round(l['other_debt']*.12)
 l['student_debt']+=student_interest;l['other_debt']+=other_interest
 debt_paid=0
 # Pay only from available cash; never invent a loan to make a loan payment.
 for field,rate in [('other_debt',.12),('student_debt',.08)]:
  payment=min(l['cash'],l[field],round(l[field]*rate));l['cash']-=payment;l[field]-=payment;debt_paid+=payment
 l.update(income=income,expenses=living+tuition+debt_paid,tax=taxes,annual_support=gifts,
  cashflow=income-taxes+gifts-living-tuition-debt_paid)
 l['ledger'].append({'age':l['age'],'state':l['state'],'income':income,'tax':taxes,'support':gifts,
 'living':living,'tuition':tuition,'debt_paid':debt_paid,'interest_accrued':student_interest+other_interest,
 'cashflow':l['cashflow'],**balance(l)})
 if not l['program'] and not l['retired']:l['experience']+=1

def advance(l,seed,mortality):
 if l['complete']:raise ValueError('Life complete')
 if l['chapter']:raise ValueError('Complete the milestone choices first')
 age=l['age'];table=mortality[l['sex']]
 if age>=len(table):l['complete']=True;l['end_reason']='table_end';l['version']+=1;return l
 if rng(seed,f'death:{age}').random()<table[age]:
  l['alive']=False;l['complete']=True;l['end_reason']='death';l['version']+=1
  event(l,'A life remembered',f'This simulated life ended during age {age} to {age+1}.');return l
 # Finance/training accrue during the completed interval, not a free year at enrollment.
 annual_finance(l,seed)
 l['age']+=1
 l['dependent_ages']=[age+1 for age in l['dependent_ages'] if age+1<18]
 l['dependents']=len(l['dependent_ages'])
 completed=None
 if l['program']:
  p=l['program'];p['remaining']-=1
  if p['remaining']<=0:
   kind=p['kind'];major=p['major'];l['program']=None
   credential=(kind+':'+major) if kind in {'cc','bachelor'} else kind
   if credential not in l['credentials']:l['credentials'].append(credential)
   if p.get('premed') or kind=='prep':
    if 'premed' not in l['credentials']:l['credentials'].append('premed')
   l['scores']['knowledge']=min(100,l['scores']['knowledge']+15)
   event(l,'Training completed',f'{credential} completed after modeled study years. New choices are now available.')
   completed=kind
 if l['age']==18:
  l['cash']+=l['family']['starter'];event(l,'Starting support',f"Fictional starting gift: ${l['family']['starter']/100:,.0f}.")
  open_chapter(l,'after-high-school',['path','wellbeing'])
 elif completed:
  keys={'cc':['transfer'],'medical':['residency'],'residency':['license'],'prep':['path'],'bachelor':['path']}.get(completed,['career','relocate','housing'])
  open_chapter(l,'after-'+completed,keys)
 elif l['age'] in {30,40,50,60}:
  # Do not interrupt an active degree with an annual education menu.
  keys=['housing','wellbeing','relationship']+(['family'] if l['age'] in {30,40} else [])
  if not l['program']:keys=['path']+keys
  open_chapter(l,'life-review',keys)
 elif l['age']==65:open_chapter(l,'later-life',['retire','housing','wellbeing'])
 l['version']+=1
 return l
