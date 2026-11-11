import { readCaptureDiagnostic } from '../assembly/capture-diagnostics.mjs';

const expected = Object.freeze({samples:15, timeoutMs:15000});

/** Retain the original browser wait and collect its test-only trace on failure. */
export async function waitForUpperHold(page, writeFailure) {
  const finish = () => readCaptureDiagnostic(() => page.evaluate(() => window.finishUpperHoldTrace()));
  try {
    await page.waitForFunction(() => window.upperHoldSamples.length >= 15, {}, {timeout:expected.timeoutMs});
  } catch (error) {
    const trace = await finish();
    const write = await readCaptureDiagnostic(() => writeFailure({expected, error, trace}));
    if (write.status !== 'available') console.error('Upper-stop hold diagnostic write failed:', write.error.message);
    throw error;
  }
  const trace = await finish();
  if (trace.status !== 'available') console.error('Upper-stop hold trace unavailable:', trace.error.message);
}
