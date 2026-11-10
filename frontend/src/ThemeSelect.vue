<script setup>
import { computed, nextTick, ref, useId, onMounted, onUnmounted } from 'vue'
const props = defineProps({modelValue:[String,Number,Boolean],options:{type:Array,required:true},disabled:Boolean,label:String})
const emit = defineEmits(['update:modelValue'])
const opened = ref(false), active = ref(0), root = ref(null)
const id = useId()
const upward = ref(false)
function outside(event) { if(!root.value?.contains(event.target)) opened.value = false }
onMounted(() => document.addEventListener('pointerdown',outside))
onUnmounted(() => document.removeEventListener('pointerdown',outside))
const selected = computed(() => props.options.findIndex(o => o.value === props.modelValue))
const text = computed(() => props.options[selected.value]?.label || '请选择')
let typed = '', typedAt = 0
async function reveal() {
  if(props.disabled) return
  const rect = root.value?.getBoundingClientRect()
  upward.value = rect && window.innerHeight-rect.bottom < 245 && rect.top > 245
  opened.value = true
  active.value = Math.max(0, selected.value)
  await scrollActive()
}
async function scrollActive() {
  await nextTick()
  root.value?.querySelector('[data-active="true"]')?.scrollIntoView({block:'nearest'})
}
function choose(index) {
  emit('update:modelValue',props.options[index].value)
  opened.value = false
}
function keydown(event) {
  if(props.disabled) return
  const key = event.key
  if(key === 'Tab') { opened.value = false; return }
  if(key === 'Escape') { opened.value = false; event.preventDefault(); return }
  if(['ArrowDown','ArrowUp','Home','End'].includes(key)) {
    event.preventDefault()
    if(!opened.value) { reveal(); return }
    active.value = key === 'Home' ? 0 : key === 'End' ? props.options.length-1 : Math.max(0,Math.min(props.options.length-1,active.value+(key === 'ArrowDown' ? 1 : -1)))
    scrollActive()
  } else if(key === 'Enter' || key === ' ') {
    event.preventDefault()
    if(opened.value) choose(active.value)
    else reveal()
  } else if(key.length === 1) {
    const now = Date.now()
    typed = now-typedAt > 700 ? key : typed+key
    typedAt = now
    const index = props.options.findIndex(o => String(o.label).toLowerCase().startsWith(typed.toLowerCase()))
    if(index >= 0) { active.value = index; if(opened.value) scrollActive(); else choose(index) }
  }
}
function blur(event) {
  if(!root.value?.contains(event.relatedTarget)) opened.value = false
}
</script>
<template>
<div ref="root" class="theme-select" @focusout="blur">
  <button type="button" class="select-trigger" role="combobox" aria-haspopup="listbox" :aria-expanded="opened" :aria-controls="id" :aria-activedescendant="opened ? id+'-'+active : undefined" :aria-label="label" :disabled="disabled" @click="opened ? opened = false : reveal()" @keydown="keydown">{{ text }}<span aria-hidden="true" class="chevron"></span></button>
  <Transition name="select-menu">
    <ul v-if="opened" :id="id" role="listbox" :aria-label="label" class="select-options" :class="{upward}">
      <li v-for="(o,i) in options" :id="id+'-'+i" :key="String(o.value)" role="option" :aria-selected="o.value === modelValue" :data-active="i === active" @mousedown.prevent @click.prevent.stop="choose(i)" @mousemove="active = i">{{ o.label }}</li>
    </ul>
  </Transition>
</div>
</template>
<style scoped>
.theme-select{position:relative;min-width:90px;width:100%;font-weight:400}
.select-trigger{display:flex;align-items:center;justify-content:space-between;gap:16px;width:100%;height:40px;padding:8px 12px;color:#234e34;border:1px solid #c9ddcf;border-radius:6px;background:#f7fbf8;text-align:left;font-size:14px}
.select-trigger:hover:not(:disabled){border-color:#73aa82;background:#eff8f1}.select-trigger:focus-visible{outline:2px solid #9ecfac;outline-offset:2px}
.chevron{width:7px;height:7px;flex-shrink:0;border:solid #548665;border-width:0 1.5px 1.5px 0;transform:rotate(45deg);margin-top:-4px}
.select-options{position:absolute;top:calc(100% + 5px);left:0;z-index:20;min-width:100%;width:max-content;max-width:320px;max-height:230px;overflow:auto;list-style:none;margin:0;padding:5px;background:#fff;border:1px solid #cce1d2;border-radius:7px;box-shadow:0 5px 18px #244e341c}
.select-options.upward{top:auto;bottom:calc(100% + 5px)}
.select-options li{padding:7px 14px;border-radius:4px;cursor:pointer;font-size:14px;color:#31543b;white-space:normal}
.select-options li[aria-selected=true]{background:#dff0e4;color:#17572d;font-weight:600}.select-options li[data-active=true]{background:#287646;color:#fff}
.select-menu-enter-active,.select-menu-leave-active{transition:opacity .12s,transform .12s}.select-menu-enter-from,.select-menu-leave-to{opacity:0;transform:translateY(-4px)}
@media(prefers-reduced-motion:reduce){.select-menu-enter-active,.select-menu-leave-active{transition:none}}
</style>
