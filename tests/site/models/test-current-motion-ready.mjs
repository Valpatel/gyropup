import assert from 'node:assert/strict';
import {test} from 'node:test';
import {runInNewContext} from 'node:vm';
import {currentRobotReady} from './current-motion-ready.mjs';

test('actual serialized readiness callback waits through bodyless/loading/wrong-source states',()=>{
  const observe=(document,window={})=>runInNewContext('('+currentRobotReady.toString()+')("expected")',{document,window});
  assert.equal(observe({body:null}),false);
  assert.equal(observe({body:{dataset:{}}}),false);
  assert.equal(observe({body:{dataset:{ready:'0'}}}),false);
  const ready={body:{dataset:{ready:'1'}}};
  for(const window of [{},{__sim:{}},{__sim:{state:{}}},{__sim:{state:{robot:{}}}},{__sim:{state:{robot:{presentation:{collectionSha256:'wrong'}}}}}])assert.equal(observe(ready,window),false);
  assert.equal(observe(ready,{__sim:{state:{robot:{presentation:{collectionSha256:'expected'}}}}}),true);
  const broken={get body(){throw new Error('Deliberate observer access failure');}};
  assert.throws(()=>observe(broken),/Deliberate observer access failure/);
});
