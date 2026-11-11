<script setup>
import { ref, reactive, watch, onMounted, computed, onUnmounted } from 'vue'
import { notify } from './toast'
import { request } from './api'
import StatChart from './StatChart.vue'
import ThemeSelect from './ThemeSelect.vue'
import ThemeDialog from './ThemeDialog.vue'
import RecordHistoryField from './RecordHistoryField.vue'
import ThemeDatePicker from './ThemeDatePicker.vue'
import RecordColumnFilter from './RecordColumnFilter.vue'
import { clampPage, partialDate, recordFilterError } from './table'
const props = defineProps(['user', 'page'])
const emit = defineEmits(['updated', 'expired', 'export-state'])
const today = new Intl.DateTimeFormat('en-CA', { timeZone:'Asia/Shanghai', year:'numeric', month:'2-digit', day:'2-digit' }).format(new Date())
const currentYear = Number(today.slice(0,4))
const recordFilters = reactive({
  start:{year:'',month:'',day:''}, end:{year:'',month:'',day:''},
  name:'',project:'',task_type:'',description:'',remark:'',
  hours_min:'',hours_max:'',code_min:'',code_max:'',
  keyword:'',showInactive:true,pageNumber:1,pageSize:20,jump:1,
})
const userFilters = reactive({keyword:'', showInactive:true, pageNumber:1, pageSize:20, jump:1})
const statsFilters = reactive({year:currentYear, showInactive:true})
const pagination = computed(() => props.page === '用户管理' ? userFilters : recordFilters)
const stats = ref(null)
const filterError = computed(() => recordFilterError(recordFilters))
const exportDialog = ref(false), exportYear = ref(currentYear)
const exportIncludeInactive = ref(false)
const filteredUsers = computed(() => users.value.filter(u => (userFilters.showInactive || u.is_active) && [u.username,u.name,u.position,u.role === 'admin' ? '管理员' : '普通用户',u.is_active ? '正常' : '已停用'].some(v => v.toLowerCase().includes(userFilters.keyword.toLowerCase()))))
const userRows = computed(() => filteredUsers.value.slice((userFilters.pageNumber-1)*userFilters.pageSize,userFilters.pageNumber*userFilters.pageSize))
const rowTotal = computed(() => props.page === '用户管理' ? filteredUsers.value.length : total.value)
const pageCount = computed(() => Math.max(1,Math.ceil(rowTotal.value/pagination.value.pageSize)))
const sort = reactive({
  work_date:'asc', name:'none', project:'none', task_type:'none',
  description:'none', hours:'none', code_lines:'none',
})
const sortColumns = computed(() => [
  ['work_date', '日期'],
  ...(props.user.role === 'admin' ? [['name', '填报人']] : []),
  ['project', '所属项目'], ['task_type', '任务类型'], ['description', '任务描述'],
  ['hours', '工时(h)'], ['code_lines', '有效代码行'],
])
const primarySort = computed(() => sortColumns.value.find(([field]) => sort[field] !== 'none')?.[0])
const rows = ref([]), users = ref([]), taskTypes = ref([]), total = ref(0), hours = ref(0)
const selected = ref([])
const rowKey = row => props.page === '用户管理' ? String(row.id) : row.work_date.slice(0,4)+'/'+row.id
const selectableRows = computed(() => props.page === '用户管理'
  ? userRows.value.filter(user => user.role !== 'admin' && user.is_active)
  : props.page === '工时记录' ? rows.value : [])
const selectedRows = computed(() => selectableRows.value.filter(row => selected.value.includes(rowKey(row))))
const allSelected = computed(() => selectableRows.value.length > 0 && selectedRows.value.length === selectableRows.value.length)
function selectAll(checked) { selected.value = checked ? selectableRows.value.map(rowKey) : [] }
watch(() => selectableRows.value.map(rowKey), keys => { selected.value = selected.value.filter(key => keys.includes(key)) })
const error = ref(''), notice = ref(''), busy = ref(false)
const editor = ref(null), oldYear = ref(null), addingUser = ref(false), newUsername = ref(''), newName = ref('')
const profile = reactive({name: props.user.name, position: props.user.position})
const record = reactive({})
const tasks = ref([]), taskEditor = ref(null), taskName = ref(''), exporting = ref(false), exportStage = ref('')
const settings = reactive({standard_hours:10,annual_leave_days:7})
const statsCache = new Map()
async function saveSettings() {
  await run(async () => {
    Object.assign(settings, await request('settings','PUT',settings))
    statsCache.clear()
    notice.value = '通用设置已保存'
  })
}
watch(error, value => { if(value) notify(value,'error') })
watch(notice, value => { if(value) notify(value) })
async function saveTask() {
  await run(async () => {
    await request(taskEditor.value === 'new' ? 'tasks' : 'tasks/'+taskEditor.value, taskEditor.value === 'new' ? 'POST' : 'PUT', {name:taskName.value})
    taskEditor.value = null
    statsCache.clear()
    taskTypes.value = (await request('options')).task_types
    notice.value = '任务已保存'
  })
  if(!error.value) await load()
}
async function removeTask(task) {
  if(!await ask('确定删除任务“'+task.name+'”？历史工时将保留。')) return
  await run(async () => {
    await request('tasks/'+task.id,'DELETE')
    taskTypes.value = (await request('options')).task_types
    notice.value = '任务已删除'
    statsCache.clear()
  })
  if(!error.value) await load()
}
const confirmation = ref(''), confirmationOpen = ref(false)
let resolveConfirmation
function ask(message) {
  confirmation.value = message
  confirmationOpen.value = true
  return new Promise(resolve => { resolveConfirmation = resolve })
}
function answer(value) {
  confirmationOpen.value = false
  resolveConfirmation?.(value)
  resolveConfirmation = null
}
function filterParams() {
  const params = new URLSearchParams({keyword:recordFilters.keyword,include_inactive:recordFilters.showInactive})
  for(const field of ['start','end']) {
    const date = partialDate(recordFilters[field])
    if(date) params.set(field,date)
  }
  for(const field of ['name','project','task_type','description','remark','hours_min','hours_max','code_min','code_max']) {
    if(recordFilters[field] !== '') params.set(field,recordFilters[field])
  }
  for(const [field] of sortColumns.value) params.append('sort', field + ':' + sort[field])
  return params
}
const personOptions = computed(() => users.value.filter(u => u.role !== "admin").map(u => ({value:u.id,label:u.name+' ('+u.username+')'+(u.is_active ? '' : ' · 已停用')})))
const typeOptions = computed(() => [...new Set([...taskTypes.value,...(record.task_type ? [record.task_type] : [])])].map(t => ({value:t,label:t})))
const sizeOptions = [10,20,30,40,50,100].map(n => ({value:n,label:n+'条'}))
let generation = 0
async function run(action, success = '') {
  error.value = ''; notice.value = ''; busy.value = true
  try { await action(); if(success) notice.value = success }
  catch(e) { error.value = e.name === 'TimeoutError' ? '请求超时，请稍后重试' : e instanceof TypeError ? '无法连接后端服务' : e.message; if(e.status === 401) emit('expired') }
  finally { busy.value = false }
}
async function load() {
  clearTimeout(filterTimer)
  const current = ++generation
  if(['个人信息','账户管理'].includes(props.page)) { busy.value = false; return }
  const year = statsFilters.year
  if((props.page === '首页总览' && (!Number.isInteger(year) || year < 1900 || year > 2100)) || (props.page === '工时记录' && filterError.value)) { busy.value = false; return }
  busy.value = true; error.value = ''
  try {
    if(props.page === '通用设置') {
      const [data,config] = await Promise.all([request('tasks'),request('settings')])
      if(current === generation) { tasks.value = data; Object.assign(settings,config) }
      return
    }
    if(props.user.role === 'admin' && props.page !== '首页总览') {
      const data = await request('users')
      if(current !== generation) return
      users.value = data
    }
    if(props.page === '用户管理') {
      userFilters.pageNumber = clampPage(userFilters.pageNumber, filteredUsers.value.length, userFilters.pageSize)
      userFilters.jump = userFilters.pageNumber
      return
    }
    if(props.page === '首页总览') {
      if(props.user.role !== 'admin') return
      const key = year+'-'+statsFilters.showInactive
      const cached = statsCache.get(key)
      if(cached) { stats.value = cached.data; if(Date.now()-cached.at < 30000) return }
      else stats.value = null
      const data = await request('statistics?' + new URLSearchParams({year,include_inactive:statsFilters.showInactive}))
      if(current === generation) { stats.value = data; statsCache.set(key,{data,at:Date.now()}) }
      return
    }
    const query = filterParams()
    const { pageNumber, pageSize } = recordFilters
    query.set('page',pageNumber); query.set('page_size',pageSize)
    let data = await request('records?' + query)
    if(current !== generation) return
    const page = clampPage(pageNumber, data.total, pageSize)
    if(page !== pageNumber) {
      query.set('page',page)
      data = await request('records?' + query)
    }
    if(current !== generation) return
    recordFilters.pageNumber = recordFilters.jump = page
    rows.value = data.items; total.value = data.total; hours.value = data.hours
  } catch(e) {
    if(current !== generation) return
    error.value = e.name === 'TimeoutError' ? '请求超时，请稍后重试' : e instanceof TypeError ? '无法连接后端服务' : e.message
    rows.value = []; stats.value = null
    if(e.status === 401) emit('expired')
  } finally { if(current === generation) busy.value = false }
}
let filterTimer
function scheduleLoad() {
  selected.value = []
  clearTimeout(filterTimer)
  generation++
  if(['工时记录','用户管理'].includes(props.page)) pagination.value.pageNumber = pagination.value.jump = 1
  filterTimer = setTimeout(load, 250)
}
watch(() => [filterParams().toString(), recordFilters.pageSize], () => {
  if(props.page === '工时记录') scheduleLoad()
})
watch(() => [userFilters.keyword, userFilters.showInactive, userFilters.pageSize], scheduleLoad)
watch(() => [statsFilters.year, statsFilters.showInactive], scheduleLoad)
function reset() {
  if(props.page === '用户管理') Object.assign(userFilters, {keyword:'', showInactive:true})
  else {
    for(const parts of [recordFilters.start,recordFilters.end]) Object.assign(parts,{year:'',month:'',day:''})
    for(const field of ['name','project','task_type','description','remark','hours_min','hours_max','code_min','code_max','keyword']) recordFilters[field]=''
    recordFilters.showInactive=true
  }
  scheduleLoad()
}
function goToPage(value) {
  selected.value = []
  const table = pagination.value
  table.pageNumber = table.jump = clampPage(value,rowTotal.value,table.pageSize)
  load()
}
onUnmounted(() => { clearTimeout(filterTimer); generation++; resolveConfirmation?.(false); emit('export-state',false) })
function openEditor(row) {
  error.value = ''
  if(!row && props.user.role === 'admin' && !personOptions.value.length) { notify('请先添加普通用户，再新增工时','error'); return }
  oldYear.value = row ? Number(row.work_date.slice(0,4)) : null
  editor.value = row ? row.id : 'new'
  Object.assign(record, row ? {user_id:row.user_id, work_date:row.work_date, project:row.project, task_type:row.task_type, description:row.description, hours:row.hours, code_lines:row.code_lines, remark:row.remark} : {user_id:props.user.role === 'admin' ? (users.value.find(u => u.role !== 'admin' && u.is_active)?.id ?? personOptions.value[0]?.value) : props.user.id, work_date:today, project:'',task_type:taskTypes.value[0],description:'',hours:8,code_lines:0,remark:''})
}
async function saveRecord() {
  await run(async () => {
    const body = {...record, user_id:Number(record.user_id), hours:Number(record.hours), code_lines:Number(record.code_lines)}
    statsCache.clear()
    await request(editor.value === 'new' ? 'records' : 'records/' + oldYear.value + '/' + editor.value, editor.value === 'new' ? 'POST' : 'PUT', body)
    editor.value = null
    notice.value = '工时已保存'
  })
  if(!error.value) await load()
}
async function remove(row) {
  if(!await ask('确定删除这条工时记录？')) return
  statsCache.clear()
  await run(() => request('records/' + row.work_date.slice(0,4) + '/' + row.id, 'DELETE'), '工时已删除')
  if(!error.value) await load()
}
async function deleteSelected() {
  const targets = [...selectedRows.value]
  if(!targets.length || busy.value) return
  const page = props.page, isUsers = page === '用户管理'
  const keys = targets.map(rowKey)
  const prompt = isUsers
    ? '确定批量停用选中的 '+targets.length+' 位用户？账号和历史工时将保留。'
    : '确定删除选中的 '+targets.length+' 条工时记录？'
  if(!await ask(prompt)) return
  let deleted = 0, expired = false
  const failed = []
  await run(async () => {
    for(let index=0; index<targets.length; index++) {
      try {
        await request((isUsers ? 'users/' : 'records/')+keys[index], 'DELETE')
        deleted++
      } catch(e) {
        failed.push(keys[index])
        if(e.status === 401 || !e.status || e.status >= 500) {
          failed.push(...keys.slice(index+1))
          if(e.status === 401) { expired = true; emit('expired') }
          break
        }
      }
    }
    if(deleted) statsCache.clear()
    if(props.page === page) selected.value = failed
  })
  if(!expired) await load()
  const action = isUsers ? '停用用户' : '删除记录'
  notify(failed.length ? '已'+action+' '+deleted+' 项，'+failed.length+' 项失败，可重试' : '已'+action+' '+deleted+' 项', failed.length ? 'error' : 'success')
}
async function userAction(target, action) {
  const message = action === 'disable' ? '停用后该用户不能登录，历史工时仍保留。确定继续？' : action === 'enable' ? '确定启用该用户？启用后可使用原密码登录。' : '确定将密码重置为123456？该用户已有登录将失效。'
  if(!await ask(message)) return
  statsCache.clear()
  await run(() => request('users/' + target.id + (action === 'disable' ? '' : action === 'enable' ? '/enable' : '/reset-password'), action === 'disable' ? 'DELETE' : 'POST'))
  if(!error.value) { await load(); notice.value = action === 'disable' ? '用户已停用' : action === 'enable' ? '用户已启用' : '密码已重置为123456' }
}
async function addUser() {
  await run(async () => { await request('users','POST',{username:newUsername.value,name:newName.value || undefined}); addingUser.value = false; newUsername.value = ''; newName.value = ''; notice.value = '用户已添加' })
  if(!error.value) await load()
}
async function saveProfile() {
  await run(async () => { emit('updated', await request('profile','PUT',profile)); notice.value = '个人信息已保存' })
}
function openExport() {
  exportYear.value = currentYear
  exportDialog.value = true
}
async function exportFile() {
  if(exporting.value) return
  if(!Number.isInteger(exportYear.value) || exportYear.value < 1900 || exportYear.value > 2100) return
  const selectedYear = exportYear.value
  const includeInactive = exportIncludeInactive.value
  exportDialog.value = false
  exporting.value = true
  exportStage.value = '正在计算全年统计并生成 Excel 文件'
  emit('export-state',true)
  try {
    const response = await fetch('/api/export?' + new URLSearchParams({year:selectedYear,include_inactive:includeInactive}),{credentials:'same-origin',signal:AbortSignal.timeout(600000)})
    if(!response.ok) {
      let data; try { data = await response.json() } catch { throw new Error('导出服务响应异常') }
      const e = new Error(typeof data.detail === 'string' ? data.detail : '导出失败')
      e.status = response.status; throw e
    }
    exportStage.value = '正在接收导出文件，即将完成'
    const blob = await response.blob()
    if(!blob.size) throw new Error('导出文件为空，请重试')
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'worktime-' + selectedYear + '.xlsx'
    document.body.appendChild(a); a.click(); a.remove()
    setTimeout(() => URL.revokeObjectURL(url),30000)
    notify('年度统计文件已导出')
  } catch(e) {
    notify(e.name === 'TimeoutError' ? '导出超过10分钟，请稍后重试或检查服务日志' : e.message,'error')
    if(e.status === 401) emit('expired')
  } finally { exporting.value = false; emit('export-state',false) }
}
watch(() => props.page, () => { selected.value = []; editor.value = null; taskEditor.value = null; addingUser.value = false; exportDialog.value = false; Object.assign(profile, {name:props.user.name,position:props.user.position}); load() })
onMounted(async () => {
  await run(async () => { taskTypes.value = (await request('options')).task_types })
  await load()
})
</script>

<template>
  <section class="business" :class="{tabular: page === '工时记录' || page === '用户管理'}">
    <form v-if="page === '个人信息'" class="profile-form" @submit.prevent="saveProfile">
      <p class="subtitle">完善姓名与职位，便于工时统计。</p>
      <label for="fixed-account">登录账号</label><input id="fixed-account" :value="user.username" disabled />
      <p class="field-help">账号不可修改。</p>
      <label for="profile-name">姓名</label><input id="profile-name" v-model="profile.name" required maxlength="80" />
      <label for="profile-position">职位</label><input id="profile-position" v-model="profile.position" required maxlength="80" />
      <button class="primary submit" :disabled="busy">保存修改</button>
    </form>
    <template v-else-if="page === '通用设置' && user.role === 'admin'">
      <form class="settings-form" @submit.prevent="saveSettings"><h2>工时统计设置</h2><div class="form-grid"><label>标准日工时（小时/天）<input v-model.number="settings.standard_hours" type="number" min="0.1" max="24" step="0.1" required /></label><label>年度年假总额（天/人/年）<input v-model.number="settings.annual_leave_days" type="number" min="0" max="365" step="0.5" required /></label></div><button class="primary" :disabled="busy">保存设置</button></form>
      <h2 class="settings-heading">任务设置</h2>
      <div class="toolbar tasks-toolbar"><p class="subtitle">任务删除后不再用于新增填报，历史记录保留。</p><button class="primary" :disabled="busy" @click="taskEditor = 'new'; taskName = ''">添加任务</button></div>
      <div class="tasks-scroll"><table class="tasks-table"><colgroup><col style="width:52px" /><col style="width:288px" /><col style="width:160px" /></colgroup><thead><tr><th class="serial" title="序号">序号</th><th title="任务名称">任务名称</th><th title="操作">操作</th></tr></thead>
        <tbody><tr v-for="(task,i) in tasks" :key="task.id"><td class="serial" :title="i+1">{{ i+1 }}</td><td :title="task.name">{{ task.name }}</td><td class="actions"><button class="text-button" title="编辑" :disabled="busy" @click="taskEditor = task.id; taskName = task.name">编辑</button><button class="text-button danger" title="删除" :disabled="busy" @click="removeTask(task)">删除</button></td></tr></tbody>
      </table></div>
    </template>
    <template v-else-if="page === '用户管理'">
      <div class="toolbar"><p class="subtitle">停用用户会保留全部历史工时及账号。</p><div class="summary-actions"><button class="batch-delete" :disabled="busy || !selectedRows.length" @click="deleteSelected">批量删除</button><button class="primary" :disabled="busy" @click="addingUser = true">添加用户</button></div></div>
      <div class="filters"><label class="keyword">关键词<input id="user-search" v-model="userFilters.keyword" placeholder="账号、姓名、职位或状态" /></label><label class="checkbox"><input v-model="userFilters.showInactive" type="checkbox" />显示停用人员</label><button type="button" class="text-button" @click="reset">重置</button></div>
      <p class="subtitle">共 {{ filteredUsers.length }} 位用户</p>
      <div class="table-scroll"><table class="users-table"><colgroup><col style="width:40px" /><col style="width:52px" /><col style="width:30%" /><col /><col /><col /><col /><col style="width:190px" /></colgroup><thead><tr><th class="selection-cell"><input type="checkbox" :checked="allSelected" :indeterminate="selectedRows.length > 0 && !allSelected" :disabled="busy || !selectableRows.length" aria-label="全选当前页可停用用户" @change="selectAll($event.target.checked)" /></th><th class="serial" title="序号">序号</th><th title="账号">账号</th><th title="姓名">姓名</th><th title="职位">职位</th><th title="角色">角色</th><th title="状态">状态</th><th title="操作">操作</th></tr></thead>
      <tbody><tr v-for="(target,index) in userRows" :key="target.id" :class="{inactive: !target.is_active}">
        <td class="selection-cell"><input v-model="selected" type="checkbox" :value="String(target.id)" :disabled="busy || target.role === 'admin' || !target.is_active" :aria-label="'选择用户 '+target.name" /></td>
        <td class="serial" :title="(userFilters.pageNumber-1)*userFilters.pageSize+index+1">{{ (userFilters.pageNumber-1)*userFilters.pageSize+index+1 }}</td><td :title="target.username">{{ target.username }}</td><td :title="target.name">{{ target.name }}</td><td :title="target.position">{{ target.position }}</td><td :title="target.role === 'admin' ? '管理员' : '普通用户'">{{ target.role === 'admin' ? '管理员' : '普通用户' }}</td><td :title="target.is_active ? '正常' : '已停用'">{{ target.is_active ? '正常' : '已停用' }}</td>
        <td class="actions"><template v-if="target.role !== 'admin'"><button class="text-button" title="重置密码" aria-label="重置密码" :disabled="busy" @click="userAction(target,'reset')">重置</button><button class="text-button" :title="target.is_active ? '停用' : '启用'" :class="{danger:target.is_active,'green-button':!target.is_active}" :disabled="busy" @click="userAction(target,target.is_active ? 'disable' : 'enable')">{{ target.is_active ? '停用' : '启用' }}</button></template><span v-else title="固定管理员">固定管理员</span></td>
      </tr></tbody></table></div>
    </template>
    <template v-else-if="page === '工时记录'">
      <form class="filters" @submit.prevent>
        <label class="keyword">关键词<input v-model="recordFilters.keyword" maxlength="200" placeholder="在各列筛选结果中继续搜索" /></label>
        <label v-if="user.role === 'admin'" class="checkbox"><input v-model="recordFilters.showInactive" type="checkbox" />显示停用人员</label><button type="button" class="text-button" @click="reset">重置</button>
      </form>
      <p class="field-help">点击表头漏斗设置各列条件；日期范围留空时查询全部年份。</p>
      <p v-if="filterError" class="filter-error" role="status">{{ filterError }}</p>
      <div class="toolbar summary"><span>{{ user.role === 'admin' ? '全员' : '我的' }}工时明细 · {{ total }}条 / {{ hours }}小时</span><div class="summary-actions"><button class="batch-delete" :disabled="busy || !selectedRows.length" @click="deleteSelected">批量删除</button><button v-if="user.role === 'admin'" class="primary" :disabled="exporting" @click="openExport">导出年度统计</button><button class="primary" :disabled="busy" @click="openEditor(null)">新增记录</button></div></div>
      <div class="table-scroll records-scroll" tabindex="0" role="region" aria-label="工时记录，可左右滚动"><table class="records-table"><colgroup><col style="width:40px" /><col style="width:52px" /><col style="width:116px" /><col v-if="user.role === 'admin'" style="width:88px" /><col style="width:166px" /><col style="width:104px" /><col style="width:360px" /><col style="width:84px" /><col style="width:108px" /><col style="width:220px" /><col style="width:132px" /></colgroup>
      <thead><tr><th class="selection-cell"><input type="checkbox" :checked="allSelected" :indeterminate="selectedRows.length > 0 && !allSelected" :disabled="busy || !selectableRows.length" aria-label="全选当前页工时记录" @change="selectAll($event.target.checked)" /></th><th class="serial" title="序号">序号</th>
        <th v-for="[field, label] in sortColumns" :key="field" class="record-heading" :class="{ 'compact-heading':field === 'hours' || field === 'code_lines' }"
            :aria-sort="field === primarySort ? (sort[field] === 'desc' ? 'descending' : 'ascending') : undefined">
          <div class="column-heading">
          {{ label }}
          <RecordColumnFilter :field="field" :label="label" :filters="recordFilters" :sort="sort" />
          </div>
        </th>
        <th title="备注"><div class="column-heading">备注<RecordColumnFilter field="remark" label="备注" :filters="recordFilters" /></div></th><th title="操作">操作</th>
      </tr></thead>
      <tbody><tr v-for="(row,index) in rows" :key="row.work_date.slice(0,4) + '-' + row.id" :class="{inactive: !row.is_active}">
        <td class="selection-cell"><input v-model="selected" type="checkbox" :value="row.work_date.slice(0,4)+'/'+row.id" :disabled="busy" :aria-label="'选择 '+row.work_date+' '+row.name+' 的工时记录'" /></td>
        <td class="serial" :title="(recordFilters.pageNumber-1)*recordFilters.pageSize+index+1">{{ (recordFilters.pageNumber-1)*recordFilters.pageSize+index+1 }}</td><td :title="row.work_date">{{ row.work_date }}</td><td v-if="user.role === 'admin'" :title="row.name + (row.is_active ? '' : '（已停用）')">{{ row.name }}<span v-if="!row.is_active" class="sr-only">（已停用）</span></td>
        <td :title="row.project">{{ row.project }}</td><td :title="row.task_type">{{ row.task_type }}</td><td :title="row.description">{{ row.description }}</td><td class="compact-cell" :title="row.hours.toFixed(1)">{{ row.hours.toFixed(1) }}</td><td class="compact-cell" :title="row.code_lines">{{ row.code_lines }}</td><td :title="row.remark || null">{{ row.remark }}</td>
        <td class="actions"><button class="text-button" title="编辑" :disabled="busy" @click="openEditor(row)">编辑</button><button class="text-button danger" title="删除" :disabled="busy" @click="remove(row)">删除</button></td>
      </tr><tr v-if="!rows.length"><td :colspan="user.role === 'admin' ? 11 : 10" class="empty-row">{{ busy ? '正在加载…' : '暂无符合条件的工时记录' }}</td></tr></tbody></table></div>
    </template>
    <template v-else-if="page === '首页总览' && user.role === 'admin'">
      <div class="filters"><label>统计年份<input v-model.number="statsFilters.year" type="number" min="1900" max="2100" /></label><label class="checkbox"><input v-model="statsFilters.showInactive" type="checkbox" />显示停用人员</label><p class="subtitle">与年度 XLSX 使用相同数据和统计口径</p></div>
      <template v-if="stats">
        <p class="field-help">饱和度：低于80%为黄色，80%–100%为绿色，高于100%为红色。年假计入实际工时，不计入项目投入和有效代码行。</p>
        <div class="charts-grid">
          <StatChart title="团队月度饱和度" :rows="stats.teamMonthly" label="month" value="saturation" kind="line" unit="%" />
          <StatChart title="任务类型工时占比" :rows="stats.tasks.filter(t => t.hours > 0)" label="taskType" value="share" kind="bar" unit="%" />
          <StatChart title="月度实际工时" :rows="stats.teamMonthly" label="month" value="actualHours" kind="bar" unit="小时" />
          <StatChart title="项目投入工时（不含年假）" :rows="stats.projects" label="project" value="hours" kind="bar" unit="小时" />
          <StatChart title="个人年度饱和度" :rows="stats.personalYearly" label="person" value="saturation" kind="bar" unit="%" />
          <StatChart title="项目有效代码行" :rows="stats.projects" label="project" value="codeLines" kind="bar" unit="行" />
        </div>

      </template>
      <p v-else-if="!busy && !error" class="empty-row">该年度暂无可统计的工时记录</p>
    </template>
    <div v-if="page === '工时记录' || page === '用户管理'" class="pagination">
      <label>每页<ThemeSelect v-model="pagination.pageSize" :options="sizeOptions" label="每页条数" /></label>
      <span>共 {{ rowTotal }} 条</span><button :disabled="busy || pagination.pageNumber <= 1" @click="goToPage(pagination.pageNumber-1)">上一页</button><span>{{ pagination.pageNumber }} / {{ pageCount }}</span><button :disabled="busy || pagination.pageNumber >= pageCount" @click="goToPage(pagination.pageNumber+1)">下一页</button>
      <form @submit.prevent="goToPage(pagination.jump)"><label>跳至<input v-model.number="pagination.jump" type="number" min="1" :max="pageCount" required />页</label><button :disabled="busy">跳转</button></form>
    </div>
    <ThemeDialog :open="editor !== null || addingUser" labelledby="dialog-title" @close="!busy && (editor = null, addingUser = false)">
        <div class="toolbar"><h2 id="dialog-title">{{ addingUser ? '添加用户' : editor === 'new' ? '新增工时' : '编辑工时' }}</h2><button :disabled="busy" class="close-button" type="button" aria-label="关闭窗口" title="关闭" @click="editor = null; addingUser = false"><span aria-hidden="true">×</span></button></div>
        <form v-if="addingUser" @submit.prevent="addUser">
          <label for="new-user">用户名</label><input id="new-user" v-model="newUsername" required pattern="[A-Za-z]+" maxlength="64" placeholder="zhangsan" />
          <label for="new-name">姓名</label><input id="new-name" v-model="newName" maxlength="80" placeholder="请输入姓名" /><p class="field-help">账号使用姓名全拼，初始密码为 123456，职位为普工。</p><button class="primary submit" :disabled="busy">添加用户</button>
        </form>
        <form v-else @submit.prevent="saveRecord">
          <label v-if="user.role === 'admin'">填报人<ThemeSelect v-model="record.user_id" :options="personOptions" label="填报人" /></label>
          <div class="form-grid"><ThemeDatePicker v-model="record.work_date" :today="today" />
          <RecordHistoryField v-model="record.project" field="project" label="所属项目" :user-id="record.user_id" :suggest="editor !== null" :maxlength="200" required />
          <label>任务类型<ThemeSelect v-model="record.task_type" :options="typeOptions" label="任务类型" /></label>
          <label>花费工时<input v-model.number="record.hours" type="number" min="0" max="24" step="0.1" required /></label>
          <label>有效代码行<input v-model.number="record.code_lines" type="number" min="0" max="10000000" step="1" required /></label></div>
          <RecordHistoryField v-model="record.description" field="description" label="任务描述" :user-id="record.user_id" :suggest="editor !== null" :maxlength="4000" multiline required />
          <RecordHistoryField v-model="record.remark" field="remark" label="备注" :user-id="record.user_id" :suggest="editor !== null" :maxlength="2000" multiline />
          <button class="primary submit" :disabled="busy">保存工时</button>
        </form>
    </ThemeDialog>
    <ThemeDialog :open="taskEditor !== null" labelledby="task-title" @close="!busy && (taskEditor = null)"><div class="toolbar"><h2 id="task-title">{{ taskEditor === 'new' ? '添加任务' : '编辑任务' }}</h2><button class="close-button" type="button" aria-label="关闭窗口" title="关闭" :disabled="busy" @click="taskEditor = null"><span aria-hidden="true">×</span></button></div><form @submit.prevent="saveTask"><label for="task-name">任务名称</label><input id="task-name" v-model="taskName" required maxlength="80" /><button class="primary submit" :disabled="busy">保存任务</button></form></ThemeDialog>
    <ThemeDialog :open="exportDialog" labelledby="export-year-title" @close="exportDialog = false">
      <div class="toolbar"><h2 id="export-year-title">选择年度统计年份</h2><button type="button" class="close-button" aria-label="关闭" @click="exportDialog = false">×</button></div>
      <form @submit.prevent="exportFile">
        <div class="export-options">
          <label for="export-year">导出年份<input id="export-year" v-model.number="exportYear" type="number" min="1900" max="2100" required /></label>
          <label class="checkbox"><input v-model="exportIncludeInactive" type="checkbox" />包含停用人员</label>
        </div>
        <p class="field-help">导出所选年份的完整年度统计。导出设置独立于浏览页面的筛选。</p>
        <div class="confirmation-actions"><button type="button" class="cancel-button" @click="exportDialog = false">取消</button><button class="primary">导出年度统计</button></div>
      </form>
    </ThemeDialog>
    <ThemeDialog :open="exporting" labelledby="export-progress-title"><section class="export-progress" aria-busy="true"><h2 id="export-progress-title">正在导出年度统计</h2><p role="status">{{ exportStage }}</p><progress aria-label="年度统计导出进行中"></progress><p class="field-help">数据较多时可能需要几分钟，请勿刷新或关闭页面。完成后将自动下载。</p></section></ThemeDialog>
    <ThemeDialog :open="confirmationOpen" labelledby="confirmation-title" @close="answer(false)"><h2 id="confirmation-title">请确认操作</h2><p class="confirmation-message">{{ confirmation }}</p><div class="confirmation-actions"><button class="cancel-button" @click="answer(false)">取消</button><button class="primary" @click="answer(true)">确定</button></div></ThemeDialog>
  </section>
</template>

<style scoped>
.business{min-width:0}
.business.tabular{display:flex;flex-direction:column}
.toolbar{display:flex;justify-content:space-between;align-items:center;gap:16px;margin:14px 0;flex-wrap:wrap;flex-shrink:0}
.filters{display:flex;gap:12px;align-items:end;flex-wrap:wrap;margin:16px 0;flex-shrink:0}
.filters label{margin:0;min-width:90px}
.filters .keyword{flex:1;min-width:160px}
.filters input{height:40px}
.filters input[type=number]{width:100px}
.filters button{height:40px}
.checkbox{display:flex;align-items:center;gap:8px;white-space:nowrap;min-height:40px;font-weight:500}
.checkbox input{width:16px;height:16px;margin:0;accent-color:#287646}
.summary{background:#edf7ef;padding:10px 14px;font-weight:600}
.summary-actions{display:flex;align-items:center;gap:14px}
.table-scroll{overflow-x:auto;border:1px solid #dfe7e1;margin-top:8px}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:14px}
.records-scroll{width:100%;min-width:0;overflow-x:auto}
.records-table{table-layout:fixed;min-width:1470px}
.users-table{table-layout:fixed;min-width:840px}
.batch-delete{padding:11px 24px;background:#fde7e4;color:#b33529;border:1px solid #efc0ba;border-radius:6px;font-weight:600}
.batch-delete:hover:not(:disabled){background:#f9d6d0}
th,td{padding:8px 12px;border-right:1px solid #e2e9e4;border-bottom:1px solid #e2e9e4;text-align:left;line-height:1.45}
.compact-cell{padding-inline:8px}
.record-heading{padding-inline:8px}
.compact-heading{padding-inline:4px}
.column-heading{display:flex;align-items:center;gap:2px;flex-wrap:nowrap;white-space:nowrap}
.export-options{display:flex;align-items:end;gap:24px;flex-wrap:wrap}
.export-options #export-year{width:120px}
.export-options .checkbox input{width:16px;height:16px}
.filter-error{color:#b33529;font-size:14px}
th{background:#194a2b;color:#fff;font-weight:500;white-space:nowrap;position:sticky;top:0;z-index:2;height:40px}
td:not(.actions,.empty-row){overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
tbody tr{background:#fff;transition:background .12s}
tbody tr:nth-child(even){background:#f4f8f5}
tbody tr:hover{background:#e4f2e9}
tbody tr.inactive{background:#fff4ce}
tbody tr.inactive:hover{background:#ffebb0}
.serial{position:sticky;left:0;width:52px;min-width:52px;max-width:52px;text-align:center;background:inherit;z-index:1;padding:8px 6px}
th.serial{background:#194a2b;z-index:3}
.selection-cell{position:sticky;left:0;width:40px;text-align:center;background:inherit;z-index:1;padding:8px}
th.selection-cell{background:#194a2b;z-index:3}
.selection-cell input{width:16px;height:16px;margin:auto;cursor:pointer;accent-color:#287646}
.selection-cell input:disabled{cursor:default}
.records-table .serial,.users-table .serial{left:40px}
.actions{white-space:nowrap}
td .text-button{background:#e0f1e5;color:#206b38;border-radius:5px;padding:4px 9px;margin:1px;font-size:13px}
td .text-button.danger{background:#fde7e4;color:#b33529;margin-left:5px}
.text-button:hover{text-decoration:none;filter:brightness(.96)}
.empty-row{text-align:center;padding:26px;color:#73877b}
.pagination{align-self:stretch;display:flex;justify-content:flex-end;align-items:center;flex-wrap:wrap;gap:12px;margin:10px 0 0;flex:0 0 auto;font-size:14px}
.pagination label,.pagination form{display:flex;align-items:center;gap:7px;margin:0}
.pagination :deep(.theme-select){width:86px}
.pagination :deep(.select-trigger){height:34px;padding:5px 9px}
.pagination input{width:62px;height:34px;padding:5px}
.pagination button{border:1px solid #d0e0d5;border-radius:5px;padding:5px 10px;background:#f7fbf8}
.profile-form{max-width:500px}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 18px}
:deep(.theme-dialog) form{margin-top:8px}
:deep(.theme-dialog) label{margin:14px 0 7px}
:deep(.theme-dialog) input{height:40px}
:deep(.theme-dialog) .toolbar{margin:0}
:deep(.theme-dialog) h2{font-size:21px}
.confirmation-message{margin:22px 0;line-height:1.8}
.confirmation-actions{display:flex;justify-content:flex-end;gap:12px}
.charts-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px 36px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap;border:0}
@media(max-width:1000px){.charts-grid{grid-template-columns:1fr}}
@media(max-width:600px){.form-grid{grid-template-columns:1fr}.filters .keyword{flex-basis:100%}.pagination{justify-content:flex-start}}

.settings-form{max-width:650px;margin:20px 0 32px}.settings-form h2,.settings-heading{font-size:20px}.settings-form button{margin-top:18px}
.export-progress{text-align:center;padding:16px 4px}.export-progress p{margin:18px 0}.export-progress progress{display:block;width:100%;height:10px;accent-color:#287646}.export-progress progress::-webkit-progress-bar{background:#e2efe6;border-radius:6px}.export-progress progress::-webkit-progress-value{background:#287646;border-radius:6px}
.tasks-toolbar{width:500px;max-width:100%}.tasks-scroll{max-width:100%;overflow-x:auto}.tasks-table{table-layout:fixed;width:500px;min-width:500px;max-width:500px;align-self:flex-start}
td .text-button.green-button{background:#206d37;color:#fff}
</style>
