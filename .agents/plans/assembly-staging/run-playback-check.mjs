/** Repeat the existing real browser scope with a test-owned, finally-closed listener. */
import {createSiteServer} from '../../../tools/site/serve-site.mjs';
import path from 'node:path';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
const root=path.resolve(import.meta.dirname,'../../..'),server=createSiteServer(path.join(root,'dist'));
try{
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
 process.env.SITE_URL='http://127.0.0.1:'+server.address().port;
 process.env.WORKSPACE_CASE='playback';
 process.env.TEST_OUTPUT||=path.join(os.tmpdir(),'gyropup-assembly-staging-browser');
 console.log('Owned ephemeral playback test listener started');
 await import(pathToFileURL(path.join(root,'tests/site/assembly/test-build-workspace.mjs')).href);
}finally{
 server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
 console.log('Owned ephemeral playback test listener closed');
}
