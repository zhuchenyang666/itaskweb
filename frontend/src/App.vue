<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import ToastHost from './ToastHost.vue'
import ThemeDialog from './ThemeDialog.vue'
import { notify } from './toast'
import BusinessView from './BusinessView.vue'
import { request } from './api'
const username = ref(''), password = ref(''), user = ref(null)
const loading = ref(true), busy = ref(false), error = ref(''), notice = ref(''), page = ref('')
const exportLocked = ref(false)
const authStage = ref('')
const currentPassword = ref(''), newPassword = ref(''), confirmPassword = ref('')
watch(error, value => { if(value) notify(value,'error') })
watch(notice, value => { if(value) notify(value) })
let expiryTimer
async function api(path, body) {
  try { return await request('auth/' + path, body === undefined ? 'GET' : 'POST', body) }
  catch(e) {
    if (e.status === 401 && user.value) { user.value = null; password.value = '' }
    throw e
  }
}
function scheduleExpiry() {
  clearTimeout(expiryTimer)
  const now = Date.now(), day = 86400000
  const midnight = Math.floor((now + 8 * 3600000) / day + 1) * day - 8 * 3600000
  expiryTimer = setTimeout(restoreSession, midnight - now + 100)
}
async function restoreSession() {
  try { user.value = await api('me'); if (!page.value) page.value = user.value.role === 'admin' ? '首页总览' : '工时记录'; if (user.value.role !== 'admin' && page.value === '首页总览') page.value = '工时记录'; scheduleExpiry() }
  catch { user.value = null }
  finally { loading.value = false }
}
async function submit() {
  if (busy.value) return
  error.value = ''; notice.value = ''
  busy.value = true
  authStage.value = '正在验证账号…'
  try {
    const account = await api('login', { username: username.value.trim(), password: password.value })
    authStage.value = '正在进入工作台…'
    await new Promise(resolve => setTimeout(resolve, 400))
    password.value = ''
    page.value = account.role === 'admin' ? '首页总览' : '工时记录'
    user.value = account
    scheduleExpiry()
  } catch (e) { error.value = e.name === 'TimeoutError' ? '请求超时，请稍后重试' : e instanceof TypeError ? '暂时无法连接服务，请稍后重试' : e.message }
  finally { authStage.value = ''; busy.value = false }
}
async function logout() {
  if (busy.value || exportLocked.value) return
  busy.value = true; error.value = ''
  authStage.value = '正在返回首页…'
  try {
    await api('logout', {})
    clearTimeout(expiryTimer)
    await new Promise(resolve => setTimeout(resolve, 400))
    user.value = null
    password.value = ''; currentPassword.value = newPassword.value = confirmPassword.value = ''
  } catch { error.value = '退出失败，请重试' }
  finally { authStage.value = ''; busy.value = false }
}
async function changePassword() {
  error.value = notice.value = ''
  if (newPassword.value !== confirmPassword.value) { error.value = '两次输入的新密码不一致'; return }
  busy.value = true
  try {
    await api('password', { current_password: currentPassword.value, new_password: newPassword.value })
    user.value = null; clearTimeout(expiryTimer); currentPassword.value = newPassword.value = confirmPassword.value = ''
    notice.value = '密码已修改，请使用新密码重新登录。'
  } catch (e) { error.value = e instanceof TypeError ? '暂时无法连接服务' : e.message }
  finally { busy.value = false }
}
function goPage(value) {
  page.value = value; error.value = notice.value = ''
  currentPassword.value = newPassword.value = confirmPassword.value = ''
}
function onVisible() { if (document.visibilityState === 'visible' && !authStage.value) restoreSession() }
onMounted(() => { restoreSession(); document.addEventListener('visibilitychange', onVisible) })
onUnmounted(() => { clearTimeout(expiryTimer); document.removeEventListener('visibilitychange', onVisible) })
</script>

<template>
  <ToastHost />
  <ThemeDialog :open="Boolean(authStage)" labelledby="auth-progress">
    <div class="login-progress" role="status">
      <span class="login-spinner" aria-hidden="true"></span>
      <p id="auth-progress">{{ authStage }}</p>
    </div>
  </ThemeDialog>
  <div v-if="loading" class="loading" role="status">正在恢复登录状态…</div>
  <main v-else-if="!user" class="auth-layout">
    <section class="brand-panel">
      <div class="brand"><img src="/itime.png" alt="" />iTime<span>工时管理</span></div>
      <div class="brand-copy">
        <span class="eyebrow">让每一份投入，清晰可见</span>
        <h1>专注工作，<br />记录每一份价值。</h1>
        <p>从日常工时填报到年度工作饱和度统计，<br />让记录更简单，让协作更有序。</p>
        <div class="brand-features"><span>便捷填报</span><span>清晰统计</span><span>年度归档</span></div>
      </div>
      <footer>iTime · 工时与工作饱和度管理</footer>
    </section>
    <section class="auth-content">
      <div class="auth-form-wrap">
        <span class="eyebrow">欢迎回到 iTime</span>
        <h2>登录工时工作台</h2>
        <p class="subtitle">使用您的账号，继续今天的工作记录。</p>
        <form @submit.prevent="submit">
          <label for="username">登录账号</label>
          <input id="username" v-model="username" name="username" autocomplete="username" required maxlength="64" placeholder="请输入账号，例如 zhangsan" :disabled="busy" />
          <label for="password">密码</label>
          <input id="password" v-model="password" name="password" type="password" autocomplete="current-password" required maxlength="128" placeholder="请输入密码" :disabled="busy" />
          <p class="field-help">登录状态保留至当天结束，无需重复登录。</p>
          <button class="primary submit" :disabled="busy">{{ busy ? '正在登录…' : '登录' }}</button>
        </form>
        <p class="auth-note">账号由管理员统一开通</p>
      </div>
      <footer>简洁记录 · 有序工作</footer>
    </section>
  </main>
  <main v-else class="workspace">
    <aside class="sidebar">
      <div class="brand"><img src="/itime.png" alt="" />iTime</div>
      <nav aria-label="主导航" :inert="exportLocked">
        <button v-if="user.role === 'admin'" :class="{ active: page === '首页总览' }" @click="goPage('首页总览')">首页总览</button>
        <button :class="{ active: page === '工时记录' }" @click="goPage('工时记录')">工时记录</button>
        <button :class="{ active: page === (user.role === 'admin' ? '用户管理' : '个人信息') }" @click="goPage(user.role === 'admin' ? '用户管理' : '个人信息')">{{ user.role === 'admin' ? '用户管理' : '个人信息' }}</button>
<button v-if="user.role === 'admin'" :class="{active: page === '通用设置'}" @click="goPage('通用设置')">通用设置</button>
        <button :class="{ active: page === '账户管理' }" @click="goPage('账户管理')">账户管理</button>
      </nav>

    </aside>
    <section class="workspace-content">
      <header><button :disabled="busy || exportLocked" class="text-button" @click="logout">返回首页</button><span class="role-badge">{{ user.role === 'admin' ? '管理员' : '普通用户' }}</span></header>
      <h1>{{ page }}</h1>
      <template v-if="page === '工时记录' || page === '首页总览'">
        <p class="subtitle">{{ user.role === 'admin' ? '全员工时记录' : '我的工时记录 · 仅展示本人填报内容' }}</p>


      </template>
      <form v-if="page === '账户管理'" class="password-form" @submit.prevent="changePassword">
        <p class="subtitle">修改自己的登录密码，修改后需要重新登录。</p>
        <label for="current-password">当前密码</label><input id="current-password" v-model="currentPassword" type="password" autocomplete="current-password" required maxlength="128" />
        <label for="new-password">新密码</label><input id="new-password" v-model="newPassword" type="password" autocomplete="new-password" required minlength="6" maxlength="128" /><p class="field-help">6–128位字符</p>
        <label for="confirm-password">确认新密码</label><input id="confirm-password" v-model="confirmPassword" type="password" autocomplete="new-password" required minlength="6" maxlength="128" />
        <button class="primary submit" :disabled="busy">{{ busy ? '正在保存…' : '保存新密码' }}</button>
      </form>
      <BusinessView v-if="page !== '账户管理'" :user="user" :page="page" @updated="user = $event" @expired="user = null" @export-state="exportLocked = $event" />
    </section>
  </main>
</template>

<style scoped>
.login-progress { display: grid; justify-items: center; gap: 16px; padding: 16px; }
.login-progress p { margin: 0; }
.login-spinner { width: 32px; height: 32px; border: 3px solid #dceee2; border-top-color: #287646; border-radius: 50%; animation: login-spin .75s linear infinite; }
@keyframes login-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .login-spinner { animation: none; } }
</style>
