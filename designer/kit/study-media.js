// A static structural result is an image, not a zero-second video. Keep each
// selection's loading/error state separate from the report table and old clips.
export function mountStudyMedia(host,{staticRender=false}={}) {
  host.innerHTML = `<div class="study-media-stage"><img class="study-still" alt="">
    <video id="feavid" controls loop muted playsinline preload="auto" hidden></video></div>
    <div class="study-media-toolbar"><span class="study-media-kind"></span>
    <button type="button" class="study-play" hidden>Play deformation</button>
    <button type="button" class="study-retry" hidden>Retry animation</button></div>
    <p class="study-media-status" role="status" aria-live="polite"></p>`;
  const video=host.querySelector('video'),still=host.querySelector('img'),kind=host.querySelector('.study-media-kind'),
    status=host.querySelector('.study-media-status'),play=host.querySelector('.study-play'),retry=host.querySelector('.study-retry');
  if(staticRender)return{show(record,media,{problem=''}={}){
    still.src='../'+(media?.poster||record.png);still.alt=`${record.part} ${record.case}: recorded static stress result`;
    const source=media?.video||record.animation;
    kind.textContent=source?'Animated static deformation':'Recorded static result';
    status.textContent=source?'Static load scaling, not elapsed physical time. Deformation is exaggerated; the recorded safety factor is unchanged.':problem?'Animation metadata unavailable; recorded static result shown.':'No animation was published for this case.';
    if(media)status.append(' Recorded 37.5 kg baseline; this does not validate the 100 lb design target.');
    if(source){const link=host.ownerDocument.createElement('a');link.href='../'+source;link.textContent='Watch the deformation animation';status.append(' ',link);}
    if(media?.webm){const link=host.ownerDocument.createElement('a');link.href='../'+media.webm;link.textContent='WebM alternative';status.append(' · ',link);}
  }};
  let selection=0,events,timer,current;
  const state=(value,message)=>{host.dataset.state=value;status.textContent=message;};
  function show(record,media,{problem=''}={}) {
    current=[record,media,{problem}];selection++;const own=selection;
    events?.abort();clearTimeout(timer);events=new AbortController();const signal=events.signal;
    video.pause();video.hidden=true;video.removeAttribute('src');video.removeAttribute('poster');video.load();
    play.hidden=retry.hidden=true;play.textContent='Play deformation';still.hidden=false;
    still.alt=`${record.part} ${record.case}: recorded static stress result`;
    still.src='../'+record.png;
    const source=media?(video.canPlayType('video/mp4; codecs="avc1.64001f"')?media.video:media.webm):record.animation,
      poster=media?.poster||record.png;
    kind.textContent=source?'Animated static deformation':'Recorded static result';
    const failure=()=>{
      if(own!==selection)return;
      clearTimeout(timer);video.pause();video.hidden=true;play.hidden=true;still.hidden=false;retry.hidden=false;
      state('error','Animation unavailable. The recorded static result and its strength assessment remain visible.');
    };
    still.addEventListener('error',()=>{
      if(own!==selection)return;still.hidden=true;
      if(!source||host.dataset.state==='error')state('error','The result image is unavailable. The recorded values remain in the table.');
    },{signal});
    if(!source){state(problem?'error':'still',problem?'Animation metadata is unavailable. Showing the recorded static result.':'No animation was published for this case.');return;}
    state('loading','Loading the deformation animation…');
    video.poster='../'+poster;
    video.addEventListener('error',failure,{signal});
    video.addEventListener('loadedmetadata',()=>{
      if(own!==selection||video.currentSrc!==new URL('../'+source,location.href).href)return;
      if(!Number.isFinite(video.duration)||video.duration<=0)failure();
    },{signal});
    video.addEventListener('loadeddata',()=>{
      if(own!==selection||video.currentSrc!==new URL('../'+source,location.href).href)return;
      if(!Number.isFinite(video.duration)||video.duration<=0)return failure();
      clearTimeout(timer);still.hidden=true;video.hidden=false;play.hidden=false;
      state('ready',`${Math.round(video.duration)}-second presentation loop · static load scaling, not elapsed physical time. Deformation is exaggerated; the recorded safety factor is unchanged.${media?' Recorded 37.5 kg baseline; this does not validate the 100 lb design target.':''}`);
      if(!matchMedia('(prefers-reduced-motion: reduce)').matches)video.play().catch(()=>{});
    },{signal});
    video.addEventListener('play',()=>{if(own===selection)play.textContent='Pause animation';},{signal});
    video.addEventListener('pause',()=>{if(own===selection)play.textContent='Play deformation';},{signal});
    timer=setTimeout(failure,20000);video.src='../'+source;video.load();
  }
  play.addEventListener('click',()=>{if(video.paused)video.play().catch(()=>state('ready','Use the video play control to start the animation.'));else video.pause();});
  retry.addEventListener('click',()=>{if(current)show(...current);});
  return{show,dispose(){selection++;events?.abort();clearTimeout(timer);video.pause();video.removeAttribute('src');video.load();host.replaceChildren();}};
}

export function matchingStudyMedia(record,index) {
  const item=index?.cases?.[`${record.part}/${record.case}`];
  if(!item)return null;
  // A report edit cannot silently attach a visualization with different results.
  for(const key of ['safety_factor','target','max_displacement_mm','von_mises_design_mpa','load_from']) {
    if(item.recorded?.[key]!==record[key])throw new Error('Animation belongs to a different structural result.');
  }
  for(const key of ['video','webm','poster','fields']) {
    if(typeof item[key]!=='string'||!item[key].startsWith('exports/leg/fea/')||item[key].includes('..'))throw new Error('Invalid structural media path.');
  }
  if(item.kind!=='static-deformation'||item.transient_simulation!==false)throw new Error('Unsupported structural animation evidence.');
  return item;
}
