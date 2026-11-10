export async function request(path, method = 'GET', body) {
  const response = await fetch('/api/' + path, {
    method, credentials: 'same-origin', signal: AbortSignal.timeout(30000),
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const raw = response.status === 204 ? '' : await response.text()
  let data
  try { data = raw ? JSON.parse(raw) : null }
  catch { throw new Error('服务响应异常，请确认后端已启动及代理配置正确') }
  if (!response.ok) {
    const detail = data?.detail
    const message = Array.isArray(detail) ? detail.map(x => x.msg).join('；') : detail
    const error = new Error(message || '服务暂时不可用，请稍后重试')
    error.status = response.status
    throw error
  }
  return data
}
