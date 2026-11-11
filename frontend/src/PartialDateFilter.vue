<script setup>
import { computed, watch } from 'vue'
import ThemeSelect from './ThemeSelect.vue'
import { daysInMonth } from './table'
const props = defineProps({ parts:Object, label:String })
const months = [{value:'',label:'全部月份'}, ...Array.from({length:12},(_,i)=>({value:i+1,label:(i+1)+'月'}))]
const days = computed(() => [{value:'',label:'全部日期'}, ...Array.from({length:daysInMonth(props.parts.year,props.parts.month)},(_,i)=>({value:i+1,label:(i+1)+'日'}))])
watch(() => [props.parts.year,props.parts.month], () => {
  if(props.parts.year === '') props.parts.month = ''
  if(props.parts.month === '' || props.parts.day > daysInMonth(props.parts.year,props.parts.month)) props.parts.day = ''
}, {flush:'sync'})
</script>
<template>
<fieldset class="partial-date"><legend>{{ label }}</legend>
  <input v-model.number="parts.year" type="number" min="1900" max="2100" placeholder="全部年份" :aria-label="label+'年份'" />
  <ThemeSelect v-model="parts.month" :disabled="parts.year === ''" :options="months" :label="label+'月份'" />
  <ThemeSelect v-model="parts.day" :disabled="parts.month === ''" :options="days" :label="label+'日'" />
</fieldset>
</template>
<style scoped>
.partial-date{display:grid;grid-template-columns:100px 1fr 1fr;gap:8px;min-width:0;border:0;padding:0;margin:12px 0}
legend{font-weight:600;font-size:14px;margin-bottom:6px}
input{height:40px;padding-inline:8px;font-size:14px}
</style>
