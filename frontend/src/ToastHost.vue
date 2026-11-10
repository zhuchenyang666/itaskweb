<script setup>
import { ref, watch, nextTick } from 'vue'
import { toast } from './toast'
const popup = ref(null)
watch(toast, async value => { await nextTick(); if(value) popup.value?.showPopover?.() })
</script>
<template>
<Teleport to="body"><Transition name="toast"><div v-if="toast" ref="popup" popover="manual" class="toast-popup" :class="toast.kind" :role="toast.kind === 'error' ? 'alert' : 'status'">{{ toast.message }}</div></Transition></Teleport>
</template>
<style>
.toast-popup{position:fixed;inset:auto;margin:0;left:50%;top:50%;transform:translate(-50%,-50%);z-index:10000;max-width:min(480px,90vw);padding:15px 25px;border-radius:9px;background:#eff9f2;border:1px solid #99c9a8;color:#215a34;box-shadow:0 8px 30px #183d2926;line-height:1.7;pointer-events:none}
.toast-popup.error{background:#fff1ee;border-color:#e4aba1;color:#a43528}
.toast-enter-active,.toast-leave-active{transition:opacity .18s}.toast-enter-from,.toast-leave-to{opacity:0}
@media(prefers-reduced-motion:reduce){.toast-enter-active,.toast-leave-active{transition:none}}
</style>
