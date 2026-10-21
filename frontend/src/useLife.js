import {ref,computed,onMounted,onUnmounted,watch} from 'vue';
import {api} from './api';
export function useLife(){
 const data=ref(null),session=ref(null),states=ref([]),busy=ref(false),error=ref('');
 const running=ref(false),autoResume=ref(true),speed=ref(4),comparisons=ref([]),curve=ref([]);
 const life=computed(()=>data.value?.life),question=computed(()=>data.value?.question);
 let timer,epoch=0,disposed=false;
 function remember(){try{if(session.value)localStorage.setItem('life-atlas-v2',JSON.stringify(session.value));else localStorage.removeItem('life-atlas-v2');}catch{error.value='Browser storage unavailable; access lasts only in this tab.';}}
 async function guarded(task){
  if(busy.value)return;
  busy.value=true;error.value='';
  try{await task();}catch(e){error.value=e.message||String(e);running.value=false;}
  finally{busy.value=false;}
 }
 async function compare(){
  if(!session.value)return;
  comparisons.value=await api(`/lives/${session.value.id}/compare`,{token:session.value.token});
 }
async function born() {
  running.value = false;

  await guarded(async () => {
    const result = await api('/lives', {
      method: 'POST',
      body: {},
    });

    // Preserve the previous journey's access credentials before switching.
    // This does not delete the previous journey from SQLite.
    try {
      if (session.value) {
        const stored = JSON.parse(
          localStorage.getItem('life-atlas-v2-archive') || '[]'
        );

        const archived = Array.isArray(stored) ? stored : [];

        if (!archived.some(item => item.id === session.value.id)) {
          archived.push({ ...session.value });
        }

        localStorage.setItem(
          'life-atlas-v2-archive',
          JSON.stringify(archived)
        );
      }
    } catch {
      // Archiving failure must not discard the new journey's token.
    }

    session.value = {
      id: result.life.id,
      token: result.token,
    };

    remember();
    data.value = result;

    curve.value = await api(
      `/lives/${session.value.id}/survival`,
      { token: session.value.token }
    );

    await compare();
    running.value = true;
  });
}
 async function refresh(){
  running.value=false;
  await guarded(async()=>{
   if(!session.value)return;
   data.value=await api(`/lives/${session.value.id}`,{token:session.value.token});
   curve.value=await api(`/lives/${session.value.id}/survival`,{token:session.value.token});
   await compare();
  });
 }
 async function step(){
  if(!life.value||life.value.complete||question.value||busy.value)return;
  await guarded(async()=>{
   data.value=await api(`/lives/${session.value.id}/step`,{method:'POST',token:session.value.token,body:{version:life.value.version}});
   if(question.value||life.value.complete)running.value=false;
   await compare();
  });
 }
 async function choose(option){
  if(!question.value||busy.value)return;
  await guarded(async()=>{
   data.value=await api(`/lives/${session.value.id}/choice`,{method:'POST',token:session.value.token,body:{version:life.value.version,question_id:question.value.id,option_id:option}});
   await compare();
   // Final choice in a chapter resumes automatically; intermediate questions stay paused.
   if(!question.value&&!life.value.complete&&autoResume.value)running.value=true;
  });
 }
 async function erase(){
  running.value=false;
  await guarded(async()=>{
   if(session.value)await api(`/lives/${session.value.id}`,{method:'DELETE',token:session.value.token});
   session.value=null;data.value=null;comparisons.value=[];curve.value=[];remember();
  });
 }
 function schedule(){
  const generation=++epoch;clearTimeout(timer);
  if(disposed||!running.value||!life.value||life.value.complete||question.value)return;
  timer=setTimeout(async()=>{await step();if(generation===epoch&&!disposed)schedule();},1400/speed.value);
 }
 watch([running,speed],schedule);
 onMounted(async()=>{
  await guarded(async()=>{
   states.value=await api('/states');
   try{const saved=JSON.parse(localStorage.getItem('life-atlas-v2')||'null');if(saved&&typeof saved.id==='string'&&typeof saved.token==='string')session.value=saved;}catch{}
   if(session.value){
    data.value=await api(`/lives/${session.value.id}`,{token:session.value.token});
    curve.value=await api(`/lives/${session.value.id}/survival`,{token:session.value.token});await compare();
   }
  });
 });
 onUnmounted(()=>{disposed=true;epoch++;clearTimeout(timer);});
 return {data,session,states,busy,error,running,autoResume,speed,comparisons,curve,life,question,born,refresh,step,choose,erase};
}
