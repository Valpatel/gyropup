import assert from 'node:assert/strict';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import { waitForUpperHold } from './upper-hold-observation.mjs';

function fakePage(samples, trace) {
  const timeout = new Error('simulated browser wait timeout');
  let waits = 0, reads = 0;
  const window = {
    upperHoldSamples: Array(samples),
    finishUpperHoldTrace() {
      reads++;
      if (trace instanceof Error) throw trace;
      return trace;
    },
  };
  const invoke = fn => runInNewContext(`(${fn})()`, {window});
  return {
    timeout,
    counts: () => ({waits,reads}),
    page: {
      async waitForFunction(fn, args, options) {
        waits++;
        assert.deepEqual(args, {});
        assert.deepEqual(options, {timeout:15000});
        if (!invoke(fn)) throw timeout;
      },
      async evaluate(fn) { return invoke(fn); },
    },
  };
}

test('the actual predicate accepts 15 samples and closes the observer once', async () => {
  const control = fakePage(15, {frames:32});
  await waitForUpperHold(control.page, () => assert.fail('successful wait must not write a failure'));
  assert.deepEqual(control.counts(), {waits:1, reads:1});
});

test('zero and fourteen samples retain the original timeout plus actual trace', async () => {
  for (const samples of [0,14]) {
    const trace = {frames:samples,stageSeconds:samples * .05,end:{samples}};
    const control = fakePage(samples, trace);
    const reports = [];
    await assert.rejects(waitForUpperHold(control.page, report => reports.push(report)), error => error === control.timeout);
    assert.deepEqual(control.counts(), {waits:1,reads:1});
    assert.deepEqual(reports, [{expected:{samples:15,timeoutMs:15000},error:control.timeout,trace:{status:'available',value:trace}}]);
  }
});

test('a failed diagnostic read and writer cannot replace the original timeout', async () => {
  const control = fakePage(0, new Error('closed page'));
  let actual;
  await assert.rejects(waitForUpperHold(control.page, report => {
    actual = report;
    throw Error('unwritable report');
  }), error => error === control.timeout);
  assert.deepEqual(control.counts(), {waits:1,reads:1});
  assert.equal(actual.trace.status, 'unavailable');
  assert.equal(actual.trace.error.message, 'closed page');
});
