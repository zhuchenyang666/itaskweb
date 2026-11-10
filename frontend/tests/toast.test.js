import assert from 'node:assert/strict'
import { notify, toast } from '../src/toast.js'
const originalSet = globalThis.setTimeout
const originalClear = globalThis.clearTimeout
const timers = new Map()
let id = 0
try {
  globalThis.setTimeout = (callback, delay) => { assert.equal(delay, 3000); timers.set(++id, callback); return id }
  globalThis.clearTimeout = key => timers.delete(key)
  notify('已保存')
  notify('操作失败', 'error')
  assert.equal(timers.size, 1)
  assert.equal(toast.value.message, '操作失败')
  assert.equal(toast.value.kind, 'error')
  for (const callback of timers.values()) callback()
  assert.equal(toast.value, null)
  console.log('提示替换及3秒自动消失检查通过')
} finally {
  globalThis.setTimeout = originalSet
  globalThis.clearTimeout = originalClear
}
