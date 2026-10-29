// Browser-test policy: only the requested document's known canonical route is valid.
export function isDocumentReturn(value,{base,docPath,search}) {
  const url=new URL(value,base),origin=new URL(base);
  return url.origin===origin.origin&&!url.username&&!url.password&&!url.hash
    &&[docPath,docPath.replace(/\.html$/,'')].includes(url.pathname)
    &&(search===undefined?['','?live=0'].includes(url.search):url.search===search);
}

export function classifyCancellation(record,{base,pendingAtNavigation=false}) {
  if(!['net::ERR_ABORTED','Load request cancelled'].includes(record.error))return null;
  const url=new URL(record.url),origin=new URL(base);
  if(url.origin!==origin.origin||url.username||url.password||url.hash||url.search)return null;
  const hosted=origin.protocol==='https:'&&(origin.hostname==='gyropup.com'
    ||/^(?:[a-z0-9-]+\.)?gyropup\.pages\.dev$/.test(origin.hostname));
  if(hosted&&url.pathname==='/cdn-cgi/rum'&&record.method==='POST'
    &&['ping','beacon','xhr'].includes(record.type))return 'hostingTelemetry';
  if(pendingAtNavigation&&record.method==='GET'&&record.type==='fetch'
    &&['/site/models.json','/site/nav.json'].includes(url.pathname))return 'cancelledOnNavigation';
  return null;
}

// Snapshot request identities before an explicit navigation. Requests started by
// the new page, asset failures and cancellations while staying put remain fatal.
export function trackNavigationRequests(page,base,report) {
  const pending=new Set(),leaving=new WeakMap();
  report.hostingTelemetry=[];report.cancelledOnNavigation=[];
  page.on('request',request=>pending.add(request));
  page.on('requestfinished',request=>pending.delete(request));
  page.on('requestfailed',request=>{
    const record={url:request.url(),method:request.method(),type:request.resourceType(),error:request.failure()?.errorText};
    const from=leaving.get(request),category=classifyCancellation(record,{base,pendingAtNavigation:from!==undefined});
    if(from!==undefined)record.navigationFrom=from;
    (category?report[category]:report.requestFailures).push(record);pending.delete(request);
  });
  return async action=>{
    for(const request of pending)leaving.set(request,page.url());
    return action();
  };
}
