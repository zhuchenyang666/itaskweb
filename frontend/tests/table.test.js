import assert from 'node:assert/strict'
import { daysInMonth, clampPage, partialDate, dateBoundary, recordFilterError } from '../src/table.js'
assert.equal(daysInMonth(2024, 2), 29)
assert.equal(daysInMonth(2025, 2), 28)
assert.equal(daysInMonth(2026, 4), 30)
assert.equal(daysInMonth(2026, ''), 0)
assert.equal(daysInMonth('', 2), 0)
assert.equal(clampPage(99, 45, 20), 3)
assert.equal(clampPage(-1, 0, 10), 1)
assert.equal(clampPage(2, 51, 50), 2)
const blank = {year:'',month:'',day:''}
assert.equal(partialDate(blank), '')
assert.equal(dateBoundary(blank), '1900-01-01')
assert.equal(dateBoundary(blank,true), '2100-12-31')
assert.equal(dateBoundary({year:2026,month:'',day:''}), '2026-01-01')
assert.equal(dateBoundary({year:2026,month:'',day:''},true), '2026-12-31')
assert.equal(dateBoundary({year:2024,month:2,day:''},true), '2024-02-29')
assert.equal(partialDate({year:2025,month:2,day:29}), null)
const filters = {start:blank,end:blank,hours_min:'',hours_max:'',code_min:'',code_max:''}
assert.equal(recordFilterError(filters), '')
assert.ok(recordFilterError({...filters,hours_min:10,hours_max:2}))
assert.ok(recordFilterError({...filters,start:{year:2027,month:'',day:''},end:{year:2026,month:'',day:''}}))
console.log('日历与分页检查通过')
