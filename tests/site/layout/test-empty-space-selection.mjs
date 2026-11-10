/** CI partitions must cover every size and reject selections that would omit work. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {SIZES,SCHEMES} from '../../../tools/site/site-empty-space.mjs';

const root=new URL('../../../',import.meta.url),harness=fileURLToPath(new URL('tests/site/layout/test-empty-space.mjs',root));
test('CI size partitions retain every page, both themes and every canonical size exactly once',()=>{
  assert.deepEqual(SIZES.map(size=>size.name),['phone-360','iphone-13','tablet-768','laptop-1024','desktop-1440']);
  assert.deepEqual(SCHEMES,['light','dark']);
  const workflow=readFileSync(new URL('.github/workflows/web-scene.yml',root),'utf8');
  const commands=workflow.split('\n').map(line=>line.trim()).filter(line=>line.startsWith('npm run test:empty-space'));
  assert.deepEqual(commands.sort(),SIZES.map(size=>`npm run test:empty-space -- --sizes=${size.name}`).sort());
  assert.match(workflow,/name: browser-validation \(layout\)[\s\S]*?needs: browser-validation/,'The retained check name must depend on the full partition result');
});

for(const [name,values]of [['sizes',['','unknown','phone-360,unknown','phone-360,phone-360']],['schemes',['','unknown','light,unknown','light,light']]]){
  test(`invalid ${name} selections fail before a browser or listener starts`,()=>{
    for(const value of values){
      const result=spawnSync(process.execPath,[harness,`--${name}=${value}`],{cwd:root,encoding:'utf8',timeout:5000,
        env:{...process.env,SITE_URL:'http://127.0.0.1:9',PLAYWRIGHT_BROWSERS_PATH:'/nonexistent-empty-space-negative-control'}});
      assert.equal(result.error,undefined);
      assert.notEqual(result.status,0);
      assert.match(result.stderr,new RegExp(`Invalid empty-space ${name} selection`));
      assert.doesNotMatch(result.stderr,/Executable doesn't exist|browserType\.launch|ECONNREFUSED/);
    }
  });
}
