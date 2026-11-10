<script setup>
import { computed, nextTick, ref, useId, watch } from 'vue'
import { request } from './api'

const props = defineProps({
  field: String, label: String, userId: Number, maxlength: Number,
  multiline: Boolean, required: Boolean, suggest: Boolean,
})
const value = defineModel({ type: String, required: true })
const id = useId()
const open = ref(false), options = ref([]), active = ref(-1), list = ref(null)
const search = ref('')
const status = ref('')
const visible = computed(() => open.value && options.value.length > 0)
const listId = id + '-history'
const attributes = computed(() => ({
  id, maxlength: props.maxlength, required: props.required, autocomplete: 'off',
  'aria-autocomplete': props.suggest ? 'list' : undefined,
  'aria-controls': visible.value ? listId : undefined,
  'aria-activedescendant': visible.value && active.value >= 0 ? listId + '-' + active.value : undefined,
}))

watch([open, search, () => props.userId, () => props.suggest], (_, __, onCleanup) => {
  options.value = []
  active.value = -1
  status.value = ''
  if (!open.value || !props.suggest || !props.userId) return

  const term = search.value
  const query = new URLSearchParams({ field: props.field, user_id: props.userId, q: term })
  let stale = false
  const timer = setTimeout(async () => {
    try {
      const matches = await request('records/suggestions?' + query)
      if (stale) return
      options.value = matches.filter(option => option.toLowerCase().includes(term.toLowerCase()))
    } catch (error) {
      if (stale) return
      status.value = error.status === 404 ? '当前后端未提供历史候选接口' : '历史候选加载失败，可手动填写'
    }
  }, 180)
  onCleanup(() => { stale = true; clearTimeout(timer) })
})

function reveal(event) {
  if (!props.suggest || open.value || event.target.composing) return
  search.value = value.value.trim()
  open.value = true
}

function onInput(event) {
  if (!props.suggest || event.isComposing || event.target.composing) return
  search.value = event.target.value.trim()
  open.value = true
}

function pick(option) {
  value.value = option
  open.value = false
}

async function onKeydown(event) {
  if (!visible.value || event.isComposing || event.keyCode === 229) return
  if (event.key === 'Escape') {
    event.preventDefault()
    open.value = false
  } else if (event.key === 'Enter' && active.value >= 0) {
    event.preventDefault()
    pick(options.value[active.value])
  } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    const last = options.value.length - 1
    active.value = event.key === 'ArrowDown' ? Math.min(last, active.value + 1) : active.value <= 0 ? last : active.value - 1
    await nextTick()
    list.value?.children[active.value]?.scrollIntoView({ block: 'nearest' })
  }
}
</script>

<template>
  <div class="history-field" :class="{ 'opens-up': field === 'remark' }" @focusin="reveal" @focusout="open = false"
       @compositionstart="open = false" @compositionend="onInput"
       @input="onInput" @keydown="onKeydown">
    <label :for="id">
      {{ label }}
      <textarea v-if="multiline" v-model="value" v-bind="attributes" @click="reveal" />
      <input v-else v-model="value" v-bind="attributes" :role="suggest ? 'combobox' : undefined"
             :aria-expanded="suggest ? visible : undefined" @click="reveal" />
    </label>
    <ul v-if="visible" :id="listId" ref="list" class="history-options"
        role="listbox" :aria-label="label + '历史候选'">
      <li v-for="(option, index) in options" :id="listId + '-' + index" :key="option" :title="option"
          role="option" :aria-selected="active === index" @mousedown.prevent @click="pick(option)">
        {{ option }}
      </li>
    </ul>
    <p v-else-if="open && status" class="history-options history-status" role="status">{{ status }}</p>
  </div>
</template>

<style scoped>
.history-field { position: relative; min-width: 0; }
.history-field input:not(:focus) { text-overflow: ellipsis; }
textarea { font: inherit; color: inherit; background: #fff; border: 1px solid #d9e2dc; border-radius: 6px; width: 100%; padding: 10px; display: block; min-height: 70px; resize: vertical; }
.history-options {
  position: absolute;
  z-index: 20;
  top: calc(100% + 4px);
  inset-inline: 0;
  max-height: min(120px, 25dvh);
  overflow: auto;
  overscroll-behavior: contain;
  list-style: none;
  margin: 0;
  padding: 5px;
  background: #fff;
  border: 1px solid #cce1d2;
  border-radius: 7px;
  box-shadow: 0 5px 18px #244e341c;
}
.opens-up .history-options { top: auto; bottom: calc(100% + 4px); }
.history-status { padding: 9px 12px; color: #426951; font-size: 14px; pointer-events: none; }
.history-options li { padding: 7px 14px; border-radius: 4px; cursor: pointer; color: #31543b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-options li:hover, .history-options li[aria-selected="true"] { background: #287646; color: #fff; }
</style>
