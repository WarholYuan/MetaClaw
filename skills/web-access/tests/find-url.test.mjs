import assert from 'node:assert/strict';
import test from 'node:test';

import { getUsage, parseArgs, parseSince } from '../scripts/find-url.mjs';

test('prints usage without touching Chrome history', () => {
  const usage = getUsage();

  assert.match(usage, /find-url - 从本地 Chrome 书签\/历史中检索 URL/);
  assert.match(usage, /--only 限定数据源/);
});

test('parses valid arguments', () => {
  const args = parseArgs(['agent', 'skills', '--only', 'history', '--limit', '3', '--sort', 'visits']);

  assert.deepEqual(args.keywords, ['agent', 'skills']);
  assert.equal(args.only, 'history');
  assert.equal(args.limit, 3);
  assert.equal(args.sort, 'visits');
});

test('rejects invalid enum values', () => {
  assert.throws(() => parseArgs(['--only', 'bad']), /--only 仅支持 bookmarks\|history/);
  assert.throws(() => parseArgs(['--sort', 'bad']), /--sort 仅支持 recent\|visits/);
});

test('rejects invalid limit values', () => {
  assert.throws(() => parseArgs(['--limit', 'abc']), /--limit 需为非负整数/);
  assert.throws(() => parseArgs(['--limit', '-1']), /--limit 需为非负整数/);
});

test('rejects invalid since values', () => {
  assert.throws(() => parseSince('nope'), /无效 --since 值/);
});
