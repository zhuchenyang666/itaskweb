const routes = [
  { page:'首页总览', path:'/overview' },
  { page:'工时记录', path:'/records' },
  { page:'用户管理', path:'/users', role:'admin' },
  { page:'个人信息', path:'/profile', role:'user' },
  { page:'通用设置', path:'/settings', role:'admin' },
  { page:'账户管理', path:'/account' },
]

export function navigationFor(role) {
  return routes.filter(route => !route.role || route.role === role)
}

export function resolvePage(path, role) {
  const available = navigationFor(role)
  return available.find(route => route.path === path.replace(/\/$/, '')) ?? available[0]
}
