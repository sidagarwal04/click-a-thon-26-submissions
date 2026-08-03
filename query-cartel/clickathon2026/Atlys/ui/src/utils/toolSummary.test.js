/**
 * Lightweight node asserts (no vitest in this package).
 * Run: node src/utils/toolSummary.test.js
 */
import { summarizeToolCall } from './toolSummary.js'
import { splitThinkTags } from '../api/client.js'

function assert(cond, msg) {
  if (!cond) throw new Error(msg || 'assertion failed')
}

assert(
  summarizeToolCall('db_schema', '{}').includes('Listing tables'),
  'db_schema empty',
)
assert(
  summarizeToolCall('db_schema', { table: ['a', 'b'] }).includes('2 tables'),
  'db_schema multi',
)
assert(
  summarizeToolCall('aggregate', {
    table: 'events',
    metrics: [{ fn: 'count' }],
    group_by: ['os'],
  }).includes('events'),
  'aggregate',
)
assert(
  summarizeToolCall('aggregate_mcp_atlys-orchestrator', { table: 'x', metrics: [{ fn: 'uniq', column: 'user_id' }] })
    .includes('uniq(user_id)'),
  'bare mcp suffix',
)

let st = { mode: 'text', buf: '' }
let r = splitThinkTags('Hello <think>secret', st)
assert(r.text === 'Hello ', `text got ${r.text}`)
assert(r.thinking === 'secret', `think got ${r.thinking}`)
st = r.state
r = splitThinkTags(' more</think> world', st)
assert(r.thinking === ' more', `think2 got ${JSON.stringify(r.thinking)}`)
assert(r.text === ' world', `text2 got ${JSON.stringify(r.text)}`)

console.log('toolSummary + splitThinkTags ok')
