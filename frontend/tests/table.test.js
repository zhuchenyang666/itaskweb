import assert from 'node:assert/strict'
import { daysInMonth, clampPage } from '../src/table.js'
assert.equal(daysInMonth(2024, 2), 29)
assert.equal(daysInMonth(2025, 2), 28)
assert.equal(daysInMonth(2026, 4), 30)
assert.equal(daysInMonth(2026, ''), 0)
assert.equal(daysInMonth('', 2), 0)
assert.equal(clampPage(99, 45, 20), 3)
assert.equal(clampPage(-1, 0, 10), 1)
assert.equal(clampPage(2, 51, 50), 2)
console.log('日历与分页检查通过')
