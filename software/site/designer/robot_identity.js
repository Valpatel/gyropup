// Product readouts follow the completely committed presentation, never a stale
// report's mass or a zero-valued fallback for an unmeasured current model.
export function robotIdentity(robot){
  const current=robot.presentation?.mode==='current'&&robot.presentation?.nativeSource==='3a40891962b0b0a04625e070700f1d130bea3c7b';
  const info=robot.info;
  return {
    massRow:current||!Number.isFinite(info.massKg)?['current mass','Pending mass/COM; current physics not recomputed']:
      ['recorded rig mass',`${info.massKg.toFixed(1)} kg (earlier physics snapshot)`],
    body:current?'Collection266 end-pack CAD · unqualified WIP':'Recorded interim body · earlier physics snapshot',
    deck:current?'Current optical/continuous clearance pending':info.deck?
      `Earlier lidar/turret study: ${info.deck.tilt_max_forward_deg}° down, ${info.deck.lidar_hidden_deg}° hidden`:'Earlier turret snapshot',
    movingCoverage:current?'Complete meshes; combined hub/motor internals unresolved':'Recorded rig joint ownership',
  };
}
