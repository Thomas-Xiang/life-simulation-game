<script setup>
import {computed} from 'vue';
import {money} from '../api';
const props=defineProps({ledger:Array,curve:Array,mode:String});
const points=computed(()=>props.mode==='survival'?(props.curve||[]).map(p=>({x:p.age,y:p.survival})):(props.ledger||[]).map(p=>({x:p.age,y:p.net_worth})));
const range=computed(()=>{const ys=points.value.map(p=>p.y);return {lo:Math.min(0,...ys),hi:Math.max(props.mode==='survival'?1:100,...ys)};});
const path=computed(()=>points.value.map((p,i)=>`${i?'L':'M'} ${30+p.x/120*400} ${115-(p.y-range.value.lo)/(range.value.hi-range.value.lo)*95}`).join(' '));
</script>
<template><div class="trend"><svg viewBox="0 0 450 140" role="img" :aria-label="mode==='survival'?'National life-table survival curve':'Modeled net worth by age'"><path d="M30 15 V115 H435" fill="none" stroke="#9ba1af"/><path :d="path" fill="none" stroke="#5c4bd8" stroke-width="2.5"/><text x="30" y="135">Age 0</text><text x="390" y="135">120</text></svg><small>{{mode==='survival'?'National SSA proxy, same in every state. Not a personal forecast.':`Net worth range: ${money(range.lo)} to ${money(range.hi)} · fictional dollars`}}</small></div></template>
