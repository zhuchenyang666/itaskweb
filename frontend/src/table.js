export function daysInMonth(year, month) {
  return Number.isInteger(year) && year >= 1900 && year <= 2100 && month ? new Date(year, Number(month), 0).getDate() : 0
}
export function clampPage(page, total, size) {
  return Math.min(Math.max(1, Math.trunc(Number(page)) || 1), Math.max(1, Math.ceil(total / size)))
}
export function partialDate(parts) {
  if(parts.year === '') return ''
  const year = Number(parts.year), month = Number(parts.month), day = Number(parts.day)
  if(!Number.isInteger(year) || year < 1900 || year > 2100) return null
  if(parts.month === '') return String(year)
  if(!Number.isInteger(month) || month < 1 || month > 12) return null
  const prefix = year + '-' + String(month).padStart(2, '0')
  if(parts.day === '') return prefix
  return Number.isInteger(day) && day >= 1 && day <= daysInMonth(year, month) ? prefix + '-' + String(day).padStart(2, '0') : null
}
export function dateBoundary(parts, end = false) {
  if(partialDate(parts) === null) return null
  const year = parts.year === '' ? (end ? 2100 : 1900) : Number(parts.year)
  const month = parts.year === '' || parts.month === '' ? (end ? 12 : 1) : Number(parts.month)
  const day = parts.year === '' || parts.month === '' || parts.day === '' ? (end ? daysInMonth(year,month) : 1) : Number(parts.day)
  return [year,String(month).padStart(2,'0'),String(day).padStart(2,'0')].join('-')
}
export function recordFilterError(filters) {
  const start = dateBoundary(filters.start), end = dateBoundary(filters.end,true)
  if(start === null || end === null) return '请输入有效的年份和日期'
  if(start > end) return '起始日期不能晚于结束日期'
  for(const [prefix,max] of [['hours',24],['code',10000000]]) {
    const low = filters[prefix+'_min'], high = filters[prefix+'_max']
    for(const value of [low,high]) {
      if(value !== '' && (!Number.isFinite(Number(value)) || Number(value) < 0 || Number(value) > max || (prefix === 'code' && !Number.isInteger(Number(value))))) return '请输入有效的数值范围'
    }
    if(low !== '' && high !== '' && Number(low) > Number(high)) return '起始值不能大于结束值'
  }
  return ''
}
