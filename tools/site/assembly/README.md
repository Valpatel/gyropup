# Assembly guide adaptation

`export_turret_guide.py` reads only the exact committed mesh scene, BOM and
literal existing turret assembly recipe. It never imports CAD, invokes a solver
or changes existing manufacturing outputs. It bakes the existing zero-angle
joint translations once into ordinary binary STL, with exact hashes and explicit
coverage/exclusions. Shared viewer/controller behaviour belongs to cad-agent.

Run `python3 -B tools/site/assembly/export_turret_guide.py`; use `--check` to reject
stale derived outputs. Source-bound guide assets are educational WIP, not proof
of physical fit or fabrication readiness.
