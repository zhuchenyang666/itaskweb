export function daysInMonth(year, month) {
  return Number.isInteger(year) && year >= 1900 && year <= 2100 && month ? new Date(year, Number(month), 0).getDate() : 0
}
export function clampPage(page, total, size) {
  return Math.min(Math.max(1, Math.trunc(Number(page)) || 1), Math.max(1, Math.ceil(total / size)))
}
