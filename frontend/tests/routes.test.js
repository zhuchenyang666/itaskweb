import assert from 'node:assert/strict'
import { navigationFor, resolvePage } from '../src/routes.js'

assert.deepEqual(navigationFor('admin').map(({path}) => path), ['/overview','/records','/users','/settings','/account'])
assert.deepEqual(navigationFor('user').map(({path}) => path), ['/records','/profile','/account'])
assert.equal(resolvePage('/', 'admin').path, '/overview')
assert.equal(resolvePage('/', 'user').path, '/records')
assert.equal(resolvePage('/users/', 'admin').path, '/users')
assert.equal(resolvePage('/account', 'user').path, '/account')
assert.equal(resolvePage('/settings', 'user').path, '/records')
assert.equal(resolvePage('/unknown', 'admin').path, '/overview')
