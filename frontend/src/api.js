export async function api(path,{method='GET',body,token}={}){
 const base=(import.meta.env.VITE_API_BASE_URL||'').replace(/\/$/,'');
 const response=await fetch(base+'/api'+path,{method,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(30000)});
 if(!response.ok){const error=await response.json().catch(()=>({}));throw new Error(typeof error.detail==='string'?error.detail:`Request failed (${response.status})`);}
 return response.status===204?null:response.json();
}
export const money=n=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format((n||0)/100);
