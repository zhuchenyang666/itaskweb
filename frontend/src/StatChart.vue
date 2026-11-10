<script setup>
import { computed } from 'vue'
const props = defineProps(['title','rows','label','value','kind','unit'])
const colors = ['#267846','#56a878','#8ac3a1','#285e6a','#78aeb3','#bd9b55','#9d7ca8','#516bb0']
const values = computed(() => props.rows.map(r => Number(r[props.value]) || 0))
const max = computed(() => Math.max(1,...values.value))
const sum = computed(() => values.value.reduce((a,b) => a+b,0))
const points = computed(() => values.value.map((v,i) => (50+i*640/Math.max(1,values.value.length-1))+','+(230-v/max.value*190)).join(' '))
function offset(i) { return -values.value.slice(0,i).reduce((a,b) => a+b,0) / (sum.value || 1) * 100 }
function color(v) { return props.unit === '%' ? (v < .8 ? '#b59842' : v > 1 ? '#d32f2f' : '#267846') : '#459563' }
function display(v) { return props.unit === '%' ? (Number(v)*100).toFixed(1)+'%' : Number(v).toLocaleString('zh-CN',{maximumFractionDigits:1}) }
</script>
<template>
<section class="chart-section">
  <h2>{{ title }}</h2>
  <p v-if="!rows.length" class="subtitle">暂无数据</p>
  <template v-else>
    <svg v-if="kind === 'line'" viewBox="0 0 740 280" role="img" :aria-label="title + '图表'">
      <g v-for="n in 5" :key="n"><line x1="50" :y1="230-(n-1)*47.5" x2="700" :y2="230-(n-1)*47.5" stroke="#e3ebe6"/><text x="43" :y="235-(n-1)*47.5" text-anchor="end">{{ display(max*(n-1)/4) }}</text></g>
      <polyline :points="points" fill="none" stroke="#267846" stroke-width="3" />
      <g v-for="(r,i) in rows" :key="i"><circle :cx="50+i*640/Math.max(1,rows.length-1)" :cy="230-values[i]/max*190" r="4" :fill="color(values[i])"><title>{{ r[label] }}：{{ display(values[i]) }}</title></circle><text :x="50+i*640/Math.max(1,rows.length-1)" y="260" text-anchor="middle">{{ String(r[label]).slice(-2) }}月</text></g>
    </svg>
    <div v-else-if="kind === 'pie'" class="pie-layout">
      <svg viewBox="0 0 220 220" role="img" :aria-label="title + '图表'">
        <circle v-for="(r,i) in rows" :key="i" cx="110" cy="110" r="76" fill="none" stroke-width="34" pathLength="100" :stroke="colors[i%colors.length]" :stroke-dasharray="values[i]/(sum||1)*100 + ' ' + (100-values[i]/(sum||1)*100)" :stroke-dashoffset="offset(i)" transform="rotate(-90 110 110)"><title>{{ r[label] }}：{{ display(values[i]) }}</title></circle>
        <text x="110" y="108" text-anchor="middle">总工时</text><text x="110" y="132" text-anchor="middle">{{ display(sum) }}</text>
      </svg>
      <ul><li v-for="(r,i) in rows" :key="i"><span :style="{background:colors[i%colors.length]}"></span>{{ r[label] }} · {{ (values[i]/(sum||1)*100).toFixed(1) }}%</li></ul>
    </div>
    <div v-else class="bars"><div v-for="(r,i) in rows" :key="i" class="bar-row"><span>{{ r[label] }}</span><div class="bar-track"><div :style="{width:values[i]/max*100+'%',background:color(values[i])}"></div></div><b>{{ display(values[i]) }}{{ unit === '%' ? '' : unit }}</b></div></div>
  </template>
</section>
</template>
<style scoped>
.chart-section{min-width:0;padding:24px 0;border-top:1px solid #dfe8e2}.chart-section h2{font-size:18px;margin-bottom:20px}svg{width:100%;max-height:300px}svg text{font:12px "Microsoft YaHei",sans-serif;fill:#425d4c}.pie-layout{display:flex;align-items:center;gap:20px;flex-wrap:wrap}.pie-layout svg{width:230px}.pie-layout ul{padding:0;list-style:none;font-size:13px}.pie-layout li{margin:8px 0}.pie-layout li span{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:8px}.bars{max-height:340px;overflow:auto}.bar-row{display:grid;grid-template-columns:minmax(90px,1fr) 2fr 85px;gap:10px;align-items:center;margin:13px 0;font-size:13px}.bar-row>span{overflow-wrap:anywhere}.bar-row b{text-align:right;font-weight:500}.bar-track{height:13px;background:#eef4ef;border-radius:3px;overflow:hidden}.bar-track div{height:100%;background:#459563;min-width:0}


</style>
