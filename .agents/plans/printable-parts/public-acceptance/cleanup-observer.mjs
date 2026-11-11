// Passive local-client timing/status. One operation, original bound, no retry.
export async function observeCleanup({label,timeout,operation,snapshot,now=()=>performance.now()}){
 const receipt={label,timeoutMs:timeout,status:'pending',operationSettled:false,observerErrors:[]};
 const describe=error=>{try{return {name:error?.name??typeof error,message:String(error?.message??error)};}catch{return {name:'UnserializableError',message:'Cleanup error could not be described'};}};
 const stamp=()=>{try{return now();}catch(error){receipt.observerErrors.push(describe(error));return null;}};
 const state=()=>{try{const value=snapshot();if(value?.then)throw Error('Cleanup snapshot must be synchronous/local');return {status:'available',value};}catch(error){receipt.observerErrors.push(describe(error));return {status:'unavailable',error:describe(error)};}};
 receipt.before=state();receipt.startedMs=stamp();let timer,value,error;
 const pending=Promise.resolve().then(operation).then(result=>{receipt.operationSettled=true;receipt.operationReturnedMs=stamp();return result;},failure=>{receipt.operationSettled=true;receipt.operationRejectedMs=stamp();throw failure;});
 try{
  value=await Promise.race([pending,new Promise((_,reject)=>timer=setTimeout(()=>{const failure=Error(label+' exceeded '+timeout+' ms');failure.name='CleanupTimeoutError';reject(failure);},timeout))]);
  receipt.status='returned';
 }catch(failure){error=failure;receipt.status='failed';receipt.error=describe(failure);}
 finally{clearTimeout(timer);receipt.completedMs=stamp();receipt.durationMs=receipt.completedMs===null||receipt.startedMs===null?null:receipt.completedMs-receipt.startedMs;receipt.after=state();}
 return {receipt,value,error};
}
