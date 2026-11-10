# Study the declared arrivals against original CAD

This project diagnostic projects the existing guide onto the existing core
finite pair sweeper. It generates no order or trajectory and changes no CAD.
The [pure plan](plan.json) retains all 1126 installed-predecessor rows for 16
changed arrivals, 1052 CAD swept-box exclusions, 74 candidates and 22 labelled
mesh-witness/current/old-order/wrong-side controls. There are 90 unique probes.
Query identity includes moving/fixed instances, offset, direction, finite travel,
seat handling and the complete installed set. The six reused controls have the
same full current context; old-order contexts use the exact source-bound
[baseline guide](baseline-guide.json) from 33c4464b.

The [source receipt](plan-source.json) and [pure preflight](pure-preflight.json)
bind exact helper, guide, binding, frame, witness and baseline bytes to core 5c29.
The [repeatable preparation harness](prepare.py) forbade CAD/OCP/VTK imports
throughout actual CLI execution. It executed no
native path. The 74 CAD candidates include both hip-frame/spacer-screw pairs
omitted by the earlier 72-row STL broadphase. Exclusions state only a CAD swept
box axis gap for this translation; they do not qualify the assembly.

`tools/site/assembly/robot_native_pairs.py` defaults to pure binding/planning.
`--execute` is only for the separately reviewed detached outer phase cap. It
uses the exact pinned core loader, `AssemblySequenceWorld` and `sweep_pair`;
there is no new planner, public core API, repair, alternate geometry or overlap
exemption. Before a query it verifies the retained 263 member/byte/mode contract,
original-byte binding, complete accepted frame receipt, case mesh hashes,
authored/reversed offsets and source installation contexts. The loaded native
bounds must reproduce the accepted native frames to 1e-7mm.

```text
python3 -B prepare.py <product-checkout> <original263-frame-output> <reviewed-core-checkout> <fresh-output>

python3 -B tools/site/assembly/robot_native_pairs.py   --frame-bundle <original263-frame-output>   --frame-manifest <sealed263-member-manifest> --frame-manifest-sha <sha256>   --frame-report-sha <accepted263-report-sha256>   --witnesses <arrival-witnesses.json> --witnesses-sha <sha256>   --baseline-guide <sealed-baseline-guide>   --toolkit <exact-clean-reviewed-core> --toolkit-revision <reviewed-core-sha>   --out <fresh-external-output>
```

Every actual native attempt requires its own reviewed source/action packet;
append `--execute --max-samples 256` only in that bounded procedure. The cap is
per-pair samples plus an external whole native-phase timer, not an unsupported
per-pair kernel timer. A stopped run retains its started-pair/progress prefix,
partial report, unchecked query IDs and complete plan. Every event is flushed;
fsync acknowledgement is recorded separately. A callback/storage/finalization
failure stops with nonzero status and preserves earlier evidence conservatively.

Results remain distinct: clear, blocked, terminal seat, unknown and unchecked.
A seat row checks no transient path; only a clear row records a completed finite
path probe. Any non-clear or incomplete study returns nonzero, including expected
diagnostic negatives. Completion and findings are separate. No product native
pair run, continuous-clearance, whole-assembly, gravity/support, physical build
or manufacturing qualification is represented by the pure plan or box fixtures.
