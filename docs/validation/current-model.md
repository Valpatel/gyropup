# Current robot presentation and recorded snapshots

Landing, the full robot playground and the talk demo use `buildRobotV2`. Its current turret uses the same 48 hashed turret STLs as the Orin bench. The bench's 18 J501/adapter parts remain bench-specific. The best committed v2 body rig is still the interim body export; this change does not imply that later body CAD, mass or physics has been regenerated.

Current presentation also attaches four output adapters and 36 individually named output-screw envelopes to the moving upper links. Recorded playback retains the archived fixed-adapter placement. See [leg attachment ownership and evidence](leg-adapter-motion.md); this correction does not make the interim body a complete mechanical assembly.

`designer/current_turret.js` owns the shared current mechanism. CAD `(x forward,y left,z up)` millimetres map to page `(y,z,x)` metres. The shared turret root is the TM plane. The robot's actual committed deck has its top at z 216 mm; the cylindrical pan bearing's center is x−54.65,y 0 mm. `tests/fixtures/current-robot-mount.json` pins the independently inspected deck/bearing STL hashes. The later `cad/body_params.py` riser is not present in that rig and is not its placement oracle.

The current turret's tilt shaft is 140 mm above TM; its muzzle is `(147,0,−15)` mm in the tilt frame, at the actual barrel mouth. Its configured ball speed is 15.85 m/s. Rotor groups retain the independently audited CAD axes and ownership: fixed motor cases stay on tilt, flywheels counterrotate, the feed dial rotates about its own shaft and the fill flap turns about its hinge. Full-robot wheel/feed motion is illustrative, not a measured motor RPM simulation. Reload opens/closes the actual flap while the existing full-robot magazine counter fills immediately; the full-robot reload does not claim the bench's jar-pouring sequence.

Recorded MuJoCo trajectories retain their original cached 31-part turret, 123 mm shaft height and `(194,0,−15)` mm muzzle. `robot.setPresentation('recorded')` loads those meshes only when requested and keeps the current model visible until all required parts succeed. A later `setPresentation('current')` takes effect synchronously and invalidates the older request. Failed loads preserve the usable model and permit retry. Historical recordings and reports retain their own provenance. Current autoplay uses current geometry and live projectile integration, not relabeled historical trajectories.

`robot.setExplode(amount)` is a presentation-only inspection. Normal firing/reload controls reassemble it. The landing eases the amount; no labels attach to the exploded parts. `robot.head` is a stable face anchor for the shared character system.

## Verification

Run `SITE_URL=http://127.0.0.1:8890 npm run test:models` against a built site. The test:

- Captures actual 48-part STL vertices through their rendered world matrices at all 46 poses of the independently audited [turret motion reference](turret-motion.md), plus 90 operating frames with wheel/feed/flap movement.
- Removes only the robot free-body pose, then converts the independent body mount into the reference box assembly frame. It never removes the turret root, which would hide mounting errors. The tolerance is 0.02 mm for exported float geometry.
- Rejects seeded wrong-pivot (correct at home), wrong-owner, reversed-axis, missing-parent and millimetre/metre failures. Restores and rechecks the actual assembly.
- Compares the visible barrel mouth with ball emission at compound pan/tilt; checks current and recorded muzzle/shaft/speed frames, explosion restoration, failed archive fetch, stale asynchronous archive selection, cached swaps and missing current meshes.
- Compares actual loaded geometry fingerprints on landing, playground and talk routes. A missing required current mesh leaves the matching landing poster instead of a partial robot.

The test writes `contract.json`, browser trace and summary under `/tmp/gyropup-current-model` by default. The contract filters the audited 66-part reference to the 48 shared turret parts; it does not derive expectations from the new animation manifest. The standalone `cad-agent motion-trace contract.json chromium-trace.json --tolerance-mm 0.02 --output report.json` can validate the same capture independently.

Passing these checks establishes sampled rendered kinematics, attachment frames and presentation consistency. It does not establish continuous collision clearance on the interim body, revised deck-clearance tables, physical fit, new full-robot mass, FEA, dynamic balance or hardware safety. The old full-robot mass remains explicitly labeled as a recorded physics snapshot.

## Evidence receipt

Local integrated build on 2026-10-29, Chromium and WebKit: 48 components × 46 independent required poses + 90 operating frames passed; maximum landmark error 0.000010 mm at 0.02 mm tolerance. The standalone `cad-agent motion-trace` command also passed all 136 samples/46 required poses. The current turret manifest SHA-256 is `3e52510898a387fd2a31fbbb3132460d792d23058d7b5d783b9231ad1fafcf18`; the filtered independent contract SHA-256 is `e42c6533f6f5d3bceed31854103d2bf2828af0c2d5f5e0f18aedc09ce21c70e9`. The manifest receipt contains every STL's content hash; browser source-hashes.json receipts also pin the delivered renderer, body manifest and talk route. The full traces and close-up shot-at-mouth images remain in the CI evidence artifacts. Local source builds include worktree changes; release verification must recapture after the final commit/build rather than interpreting the earlier version.json revision as the complete source identity.

Required-pose angles are preserved exactly, including endpoint 360° and pinion multi-turn limits. Only continuously rotating wheel/dial phases in the operating-frame trace are reduced modulo 360°, because the independent contract represents one cycle; the summary retains their unwrapped operation angles. Limited pan/tilt/flap and parent relationships are never normalized. This is a trace representation choice, not an animation change.

Talk presentation also runs the portal viewport suite with visible speech/chat obstruction checks, fresh 844×390 startup, compact event/chat exclusivity and minimum useful model size. The UI-only invisible speech envelope does not alter CAD geometry or the independent mechanism capture. Screenshots at 320×568 and short landscape are inspected alongside the projected bounds.
