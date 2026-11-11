<script setup>
import { computed, ref, useId } from 'vue'
import PartialDateFilter from './PartialDateFilter.vue'
import { dateBoundary } from './table'
const props = defineProps({field:String,label:String,filters:Object,sort:Object})
const id = useId(), menu = ref(null)
const rangeKeys = computed(() => props.field === 'hours' ? ['hours_min','hours_max'] : ['code_min','code_max'])
const isRange = computed(() => ['hours','code_lines'].includes(props.field))
const active = computed(() => {
  if(props.field === 'work_date') return props.filters.start.year !== '' || props.filters.end.year !== ''
  return isRange.value ? rangeKeys.value.some(key => props.filters[key] !== '') : Boolean(props.filters[props.field])
})
const error = computed(() => {
  if(props.field === 'work_date') {
    const start = dateBoundary(props.filters.start), end = dateBoundary(props.filters.end,true)
    if(start === null || end === null) return '请输入有效的年份和日期'
    if(start > end) return '起始日期不能晚于结束日期'
  } else if(isRange.value) {
    const [low,high] = rangeKeys.value.map(key => props.filters[key])
    if(low !== '' && high !== '' && Number(low) > Number(high)) return '起始值不能大于结束值'
  }
  return ''
})
function show(event) {
  const element = menu.value
  if(element.matches(':popover-open')) { element.hidePopover(); return }
  element.showPopover()
  const button = event.currentTarget.getBoundingClientRect()
  const bounds = element.getBoundingClientRect()
  element.style.left = Math.max(8,Math.min(button.left,innerWidth-bounds.width-8))+'px'
  const top = button.bottom+6
  element.style.top = Math.max(8,Math.min(top,innerHeight-bounds.height-8))+'px'
  element.querySelector('input')?.focus({preventScroll:true})
}
function clear() {
  if(props.field === 'work_date') {
    for(const parts of [props.filters.start,props.filters.end]) Object.assign(parts,{year:'',month:'',day:''})
  } else if(isRange.value) {
    for(const key of rangeKeys.value) props.filters[key]=''
  } else props.filters[props.field]=''
}
</script>
<template>
  <button type="button" class="filter-trigger" :class="{active}" :title="label+(sort?'筛选与排序':'筛选')+(active?'（已启用筛选）':'')" :aria-label="label+(sort?'筛选与排序':'筛选')" :aria-controls="id" @click="show">
    <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true" fill="currentColor"><path d="M1 2h14L9.5 8v5L6.5 15V8z" /></svg>
  </button>
  <div :id="id" ref="menu" popover="auto" class="column-filter" :class="{'date-filter':field === 'work_date'}" role="dialog" :aria-label="label+'筛选'">
    <div class="filter-heading"><b>{{ label }}筛选</b><button type="button" class="close-button" aria-label="关闭筛选" @click="menu.hidePopover()">×</button></div>
    <fieldset v-if="sort" class="sort-choices">
      <legend>排序</legend>
      <label><input v-model="sort[field]" type="radio" :name="id+'-sort'" value="asc" />升序</label>
      <label><input v-model="sort[field]" type="radio" :name="id+'-sort'" value="desc" />降序</label>
      <label><input v-model="sort[field]" type="radio" :name="id+'-sort'" value="none" />不排序</label>
    </fieldset>
    <template v-if="field === 'work_date'">
      <PartialDateFilter :parts="filters.start" label="起始日期" />
      <PartialDateFilter :parts="filters.end" label="结束日期" />
      <p class="help">留空部分表示全部，范围包含起止日期。</p>
    </template>
    <div v-else-if="isRange" class="numeric-range">
      <label>起始<input v-model.number="filters[rangeKeys[0]]" type="number" min="0" :max="field === 'hours'?24:10000000" :step="field === 'hours'?0.1:1" placeholder="不限" /></label>
      <span>～</span>
      <label>结束<input v-model.number="filters[rangeKeys[1]]" type="number" min="0" :max="field === 'hours'?24:10000000" :step="field === 'hours'?0.1:1" placeholder="不限" /></label>
    </div>
    <label v-else class="text-condition">包含文字<input v-model="filters[field]" :maxlength="field === 'description'?4000:field === 'remark'?2000:field === 'project'?200:80" placeholder="输入任意位置的文字" /></label>
    <p v-if="error" class="filter-error" role="status">{{ error }}</p>
    <button type="button" class="clear-filter" @click="clear">清除此列筛选</button>
  </div>
</template>
<style scoped>
.filter-trigger{display:inline-flex;align-items:center;flex-shrink:0;padding:2px;margin-left:4px;color:#c5dccc;border-radius:3px}
.filter-trigger:hover,.filter-trigger.active{background:#dff0e4;color:#194a2b}
.column-filter{position:fixed;inset:auto;margin:0;width:280px;max-width:calc(100vw - 16px);max-height:calc(100dvh - 16px);overflow:auto;padding:14px;border:1px solid #cce1d2;border-radius:8px;background:#fff;color:#234e34;box-shadow:0 8px 28px #244e3430;font-size:14px;line-height:1.6;font-weight:400;white-space:normal;text-align:left}
.date-filter{width:410px}
.filter-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}
.text-condition{display:block;margin:12px 0;font-weight:500}
.column-filter input{height:40px;font-size:14px;margin-top:5px}
.numeric-range{display:grid;grid-template-columns:1fr auto 1fr;align-items:end;gap:8px;margin:12px 0}
.numeric-range label{margin:0}
.numeric-range>span{padding-bottom:9px}
.clear-filter{color:#23643a;border:1px solid #cce1d2;padding:5px 9px;border-radius:5px;margin-top:12px}
.clear-filter:hover{background:#eaf5ee}
.help{color:#627b69;font-weight:400}
.filter-error{color:#b33529;font-weight:400}
.sort-choices{display:flex;gap:24px;border:0;border-bottom:1px solid #e2eae5;padding:8px 0 12px;margin:10px 0}
.sort-choices legend{font-weight:600}
.sort-choices label{display:flex;align-items:center;gap:6px;margin:0;font-weight:400;cursor:pointer}
.sort-choices input{width:15px;height:15px;margin:0;accent-color:#287646}
</style>
