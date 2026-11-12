<script setup>
import { computed, ref, useId } from 'vue'
const props = defineProps(['title','rows','label','value','kind','unit'])
const direction = ref('desc'), barList = ref(null)
const sortId = useId()
const values = computed(() => props.rows.map(r => Number(r[props.value]) || 0))
const max = computed(() => Math.max(1,...values.value))
const points = computed(() => values.value.map((v,i) => (50+i*640/Math.max(1,values.value.length-1))+','+(230-v/max.value*190)).join(' '))
const bars = computed(() => {
  const entries = props.rows.map((row, i) => ({ label: row[props.label], value: values.value[i] }))
  if(direction.value === 'asc') entries.sort((a,b) => a.value - b.value)
  if(direction.value === 'desc') entries.sort((a,b) => b.value - a.value)
  return entries
})
function sortBy(next) {
  direction.value = next
  if(barList.value) barList.value.scrollTop = 0
}
function color(v) { return props.value === 'saturation' ? (v < .8 ? '#b59842' : v > 1 ? '#d32f2f' : '#267846') : '#459563' }
function display(v) { return props.unit === '%' ? (Number(v)*100).toFixed(1)+'%' : Number(v).toLocaleString('zh-CN',{maximumFractionDigits:1}) }
</script>
<template>
<section class="chart-section">
  <div class="chart-heading">
    <h2>{{ title }}</h2>
    <slot name="controls" />
    <div v-if="kind === 'bar' && rows.length > 1" class="chart-order" role="group" :aria-label="title + '排序'">
      <label><input type="radio" :name="sortId" value="asc" :checked="direction === 'asc'" @change="sortBy('asc')" />升序</label>
      <label><input type="radio" :name="sortId" value="desc" :checked="direction === 'desc'" @change="sortBy('desc')" />降序</label>
      <label><input type="radio" :name="sortId" value="none" :checked="direction === 'none'" @change="sortBy('none')" />不排序</label>
    </div>
  </div>
  <p v-if="!rows.length" class="subtitle">暂无数据</p>
  <template v-else>
    <svg v-if="kind === 'line'" viewBox="0 0 740 280" role="img" :aria-label="title + '图表'">
      <g v-for="n in 5" :key="n"><line x1="50" :y1="230-(n-1)*47.5" x2="700" :y2="230-(n-1)*47.5" stroke="#e3ebe6"/><text x="43" :y="235-(n-1)*47.5" text-anchor="end">{{ display(max*(n-1)/4) }}</text></g>
      <polyline :points="points" fill="none" stroke="#267846" stroke-width="3" />
      <g v-for="(r,i) in rows" :key="i"><circle :cx="50+i*640/Math.max(1,rows.length-1)" :cy="230-values[i]/max*190" r="4" :fill="color(values[i])"><title>{{ r[label] }}：{{ display(values[i]) }}</title></circle><text :x="50+i*640/Math.max(1,rows.length-1)" y="260" text-anchor="middle">{{ String(r[label]).slice(-2) }}月</text></g>
    </svg>
    <div v-else ref="barList" class="bars">
      <div v-for="bar in bars" :key="bar.label" class="bar-row">
        <span>{{ bar.label }}</span>
        <div class="bar-track" aria-hidden="true"><div :style="{width:bar.value/max*100+'%',background:color(bar.value)}"></div></div>
        <b>{{ display(bar.value) }}{{ unit === '%' ? '' : unit }}</b>
      </div>
    </div>
  </template>
</section>
</template>
<style scoped>
.chart-section{min-width:0;padding:24px 0;border-top:1px solid #dfe8e2}
.chart-heading{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:20px}
.chart-section h2{font-size:18px}
.chart-order{display:flex;gap:14px}
.chart-order label{display:flex;align-items:center;gap:5px;margin:0;color:#23643a;font-size:13px;font-weight:400;cursor:pointer}
.chart-order input{width:15px;height:15px;margin:0;padding:0;accent-color:#287646}
svg{width:100%;max-height:300px}svg text{font:12px "Microsoft YaHei",sans-serif;fill:#425d4c}
.bars{max-height:340px;overflow:auto}.bar-row{display:grid;grid-template-columns:minmax(90px,1fr) 2fr 85px;gap:10px;align-items:center;margin:13px 0;font-size:13px}.bar-row>span{overflow-wrap:anywhere}.bar-row b{text-align:right;font-weight:500}.bar-track{height:13px;background:#eef4ef;border-radius:3px;overflow:hidden}.bar-track div{height:100%;background:#459563;min-width:0}


</style>
