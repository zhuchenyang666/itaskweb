<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, useId } from 'vue'
import ThemeSelect from './ThemeSelect.vue'
import { daysInMonth } from './table'

const props = defineProps({ today: { type: String, required: true } })
const value = defineModel({ type: String, required: true })
const id = useId()
const root = ref(null), trigger = ref(null), opened = ref(false)
const year = ref(0), month = ref(0), activeDay = ref(1)
const months = Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: (i + 1) + '月' }))
const weekdays = ['一', '二', '三', '四', '五', '六', '日']
const offset = computed(() => (new Date(year.value, month.value - 1, 1).getDay() + 6) % 7)
const dayCount = computed(() => daysInMonth(year.value, month.value))
const iso = day => [year.value, month.value, day].map(n => String(n).padStart(2, '0')).join('-')

function close(restoreFocus = false) {
  opened.value = false
  if (restoreFocus) trigger.value?.focus()
}

function outside(event) {
  if (!root.value?.contains(event.target)) close()
}

function onBlur(event) {
  if (event.relatedTarget && !root.value?.contains(event.relatedTarget)) close()
}

onMounted(() => document.addEventListener('pointerdown', outside))
onUnmounted(() => document.removeEventListener('pointerdown', outside))

async function focusDay() {
  await nextTick()
  root.value?.querySelector('[tabindex="0"][data-day]')?.focus({ preventScroll: true })
}

function showMonth(y, m, day = activeDay.value) {
  year.value = y
  month.value = m
  activeDay.value = Math.min(day, daysInMonth(y, m))
}

function toggle() {
  if (opened.value) { close(); return }
  showMonth(...(value.value || props.today).split('-').map(Number))
  opened.value = true
  focusDay()
}

function changeYear(event) {
  const input = event.target
  const y = input.valueAsNumber
  if (Number.isInteger(y) && y >= 1900 && y <= 2100) showMonth(y, month.value)
  input.value = year.value
}

function shiftMonth(step) {
  const date = new Date(year.value, month.value - 1 + step, 1)
  showMonth(date.getFullYear(), date.getMonth() + 1)
}

function choose(date) {
  value.value = date
  close(true)
}

function onKeydown(event) {
  if (!opened.value || event.defaultPrevented) return
  if (event.key === 'Escape') {
    event.preventDefault()
    close(true)
    return
  }
  const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[event.key]
  const day = Number(event.target.dataset.day)
  if (!step || !day) return
  event.preventDefault()
  const date = new Date(year.value, month.value - 1, day + step)
  if (date.getFullYear() < 1900 || date.getFullYear() > 2100) return
  showMonth(date.getFullYear(), date.getMonth() + 1, date.getDate())
  focusDay()
}
</script>

<template>
  <div ref="root" class="date-picker" @keydown="onKeydown" @focusout="onBlur">
    <label :for="id">
      日期
      <button :id="id" ref="trigger" type="button" class="date-trigger" aria-haspopup="dialog"
              :aria-expanded="opened" :aria-controls="opened ? id + '-calendar' : undefined"
              :aria-label="'日期：' + (value || '请选择日期')" @click="toggle">
        {{ value || '请选择日期' }}
        <svg aria-hidden="true" viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.7">
          <rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4m8-4v4m-8 7h2m4 0h2m-8 4h2" />
        </svg>
      </button>
    </label>
    <div v-if="opened" :id="id + '-calendar'" class="date-calendar" role="dialog" aria-label="选择日期">
      <div class="date-navigation">
        <button type="button" aria-label="上个月" :disabled="year === 1900 && month === 1" @click="shiftMonth(-1)">‹</button>
        <input :value="year" type="number" min="1900" max="2100" inputmode="numeric" aria-label="年份"
               @change="changeYear" @keydown.enter.prevent="changeYear" />
        <ThemeSelect :model-value="month" :options="months" label="月份" @update:model-value="showMonth(year, $event)" />
        <button type="button" aria-label="下个月" :disabled="year === 2100 && month === 12" @click="shiftMonth(1)">›</button>
      </div>
      <div class="date-grid">
        <span v-for="weekday in weekdays" :key="weekday" class="date-weekday">{{ weekday }}</span>
        <span v-for="blank in offset" :key="'blank-' + blank" aria-hidden="true"></span>
        <button v-for="day in dayCount" :key="day" type="button" :data-day="day"
                :tabindex="day === activeDay ? 0 : -1" :aria-label="iso(day)"
                :aria-current="iso(day) === today ? 'date' : undefined" :aria-pressed="iso(day) === value"
                @focus="activeDay = day" @click="choose(iso(day))">{{ day }}</button>
      </div>
      <button type="button" class="date-today" @click="choose(today)">今天</button>
    </div>
  </div>
</template>

<style scoped>
.date-picker { position: relative; min-width: 0; }
.date-trigger { display: flex; align-items: center; justify-content: space-between; width: 100%; height: 40px; padding: 0 12px; background: #f7fbf8; color: #234e34; border: 1px solid #c9ddcf; border-radius: 6px; font-size: 16px; font-weight: 600; }
.date-trigger:hover { border-color: #73aa82; background: #eff8f1; }
.date-calendar { position: absolute; top: calc(100% + 5px); left: 0; z-index: 25; width: min(300px, 100%); padding: 9px; background: #fff; color: #234e34; border: 1px solid #cce1d2; border-radius: 7px; box-shadow: 0 5px 18px #244e3426; font-size: 15px; }
.date-navigation { display: grid; grid-template-columns: 28px minmax(50px, 1fr) minmax(64px, 1.3fr) 28px; gap: 5px; margin-bottom: 7px; }
.date-navigation button { padding: 0; font-size: 22px; background: #eff8f1; border-radius: 5px; }
.date-navigation input { padding: 0 3px; text-align: center; font-size: 15px; appearance: textfield; }
.date-navigation input::-webkit-inner-spin-button, .date-navigation input::-webkit-outer-spin-button { appearance: none; }
.date-navigation :deep(.theme-select) { min-width: 0; }
.date-navigation :deep(.select-trigger) { gap: 5px; padding: 6px; font-size: 15px; }
.date-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 3px; text-align: center; }
.date-weekday { padding: 4px 0; color: #426951; font-weight: 600; }
.date-grid button { height: 32px; padding: 0; border-radius: 5px; font-size: 15px; }
.date-grid button:hover, .date-today:hover { background: #e4f2e8; }
.date-grid button[aria-current="date"] { box-shadow: inset 0 0 0 1px #73aa82; font-weight: 700; }
.date-grid button[aria-pressed="true"] { background: #287646; color: #fff; }
.date-today { margin-top: 6px; padding: 4px 9px; color: #206d37; border-radius: 5px; font-weight: 600; }
</style>
