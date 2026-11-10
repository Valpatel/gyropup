# Whole-robot guide collection records

`collection-260.json` is the unchanged public-safe collection manifest from the
single native run at `540056ba4e59b197859236cb693463e10c9c8901`.
`review-260.json` records its immutable archive identities, actual frame/control
results and scoped independent visual-asset audit. Collection meshes and local
reference meshes are retained in the sealed candidate archive named there.

Use the existing `tools/site/assembly/export_robot_guide.py --collection
<extracted-candidate>/collection.json --out <fresh-output>` for pure
serialization; it needs the original candidate's sibling `meshes/`. This does
not run CAD. Later mapper/source hashes belong to that pure serialization, not
to the original native execution. The native-produced guide archive is retained
unchanged even when conservative metadata is added afterward.

The two snapshot directories belong under `software/site/assets/build-guides`.
The product UI owner composes their exact index entries into the existing
canonical index; this data branch must not overwrite that owner's Turret rows.
New snapshot photographs/posters and actual product interaction proofs remain
owned by the product's existing renderer/test contract. Current manufacturing
correspondence is pending and physical qualification remains unresolved.
