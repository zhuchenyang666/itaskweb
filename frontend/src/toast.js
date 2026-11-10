import { ref } from 'vue'
export const toast = ref(null)
let timer
export function notify(message, kind = 'success') {
  clearTimeout(timer)
  toast.value = { message, kind }
  timer = setTimeout(() => { toast.value = null }, 3000)
}
