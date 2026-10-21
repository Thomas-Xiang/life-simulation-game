<script setup>
import {computed} from 'vue';
const props=defineProps({states:Array,current:String,home:String,selected:String,moves:Array});
const emit=defineEmits(['select']);
const coords=code=>{const s=props.states.find(x=>x.code===code);return s?{x:s.x*40+19,y:s.y*32+15}:null;};
const routes=computed(()=>(props.moves||[]).map(m=>({a:coords(m.from),b:coords(m.to)})).filter(r=>r.a&&r.b));
</script>
<template>
 <div class="map-wrap">
  <div class="tile-map" role="group" aria-label="Interactive U.S. state tile map, approximate positions, Alaska and Hawaii inset">
   <svg class="routes" viewBox="0 0 520 288" preserveAspectRatio="none" aria-hidden="true"><line v-for="(r,i) in routes" :key="i" :x1="r.a.x" :y1="r.a.y" :x2="r.b.x" :y2="r.b.y" stroke="#5c4bd8" stroke-width="2" stroke-dasharray="4 3" /></svg>
   <button v-for="s in states" :key="s.code" class="tile" :class="{current:s.code===current,home:s.code===home,selected:s.code===selected}" :style="{gridColumn:s.x+1,gridRow:s.y+1}" :aria-label="`${s.name}${s.code===current?', current state':''}${s.code===home?', home state':''}`" :aria-pressed="s.code===selected" :title="s.name+' · fictional '+s.sector+' scenario'" @click="emit('select',s.code)">{{s.code}}</button>
  </div>
  <div class="legend"><span>● Current</span><span>⌂ Family home</span><span>Dashed lines: moves</span></div>
 </div>
</template>
