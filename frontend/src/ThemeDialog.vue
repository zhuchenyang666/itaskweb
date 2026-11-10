<script setup>
import { ref, watch, nextTick } from 'vue'
const props = defineProps({open:Boolean,labelledby:String})
const emit = defineEmits(['close'])
const element = ref(null), shown = ref(false)
let opener
watch(() => props.open, async value => {
  if(value) {
    opener = document.activeElement
    shown.value = true
    await nextTick()
    element.value?.showModal()
  } else shown.value = false
}, {immediate:true})
function finish() { element.value?.close(); opener?.focus?.() }
</script>
<template>
<Transition name="dialog-fade" @after-leave="finish">
  <dialog v-if="shown" ref="element" class="theme-dialog" :aria-labelledby="labelledby" @cancel.prevent="emit('close')"><slot /></dialog>
</Transition>
</template>
<style>
.theme-dialog{margin:auto;border:1px solid #d8e5dc;border-radius:10px;color:#193e29;background:#fff;padding:24px;width:min(620px,calc(100% - 32px));max-height:90svh;overflow:auto;box-shadow:0 20px 70px #183d2933}
.theme-dialog::backdrop{background:#173e2a55}
.dialog-fade-enter-active,.dialog-fade-leave-active{transition:opacity .18s,transform .18s}
.dialog-fade-enter-from,.dialog-fade-leave-to{opacity:0;transform:translateY(8px) scale(.985)}
.dialog-fade-enter-active::backdrop{animation:backdrop-in .18s}
.dialog-fade-leave-active::backdrop{animation:backdrop-out .18s forwards}
@keyframes backdrop-in{from{background:#173e2a00}to{background:#173e2a55}}
@keyframes backdrop-out{to{background:#173e2a00}}
@media(prefers-reduced-motion:reduce){.dialog-fade-enter-active,.dialog-fade-leave-active{transition:none}.dialog-fade-enter-active::backdrop,.dialog-fade-leave-active::backdrop{animation:none}}
</style>
