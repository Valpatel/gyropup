# A finite-element address-space cap must accommodate assembly temporaries

On 2026-11-07, PR #259's first genuine E1 reproduction used the recovered historical toolkit, package versions and four mapped-library hashes. The actual worker preflight and six source-path controls passed. The one-case 4 mm P2 solve then exited 1 after 144.6 seconds in scikit-fem/SciPy COO-to-CSR stiffness assembly:

```text
prlimit --as=12884901888 --cpu=3600:3610 -- <retained-cad-python> -B tools/engineering/legs/export-hip-frame-e1.py
numpy._core._exceptions._ArrayMemoryError: Unable to allocate 1.29 GiB for an array with shape (173155659,) and data type float64
```

The configured 12 GiB cap limits virtual address space, including mappings and transient arrays; it is not a resident-memory reservation. The host preflight recorded 52.75 GiB available, but no contemporaneous process RSS/virtual peak was captured. The allocation exception under this cap supports reviewing resource adequacy; it does not establish a physical host OOM, a solver/geometry defect, or the exact sufficient replacement bound.

The original run remains **FAILED**. No solved output was produced. All original media bytes were unchanged; the observed partial archive adds only the temporary copied summary input. Both sealed archives, the original traceback and complete project/hardware/retained-runtime before/after inventories were collected. All owned phase groups and the outer group were gone; restoration checks were exact with no cleanup errors. [Command, seals, raw/redacted log hashes and observations](../plans/leg-control/e1-field-attempt1.json).

Corrective rule: distinguish virtual-address limits from resident-memory headroom when bounding native assembly. Retain the failed attempt and partial outputs, check the actual assembly allocation and available capacity, and obtain an exact independently reviewed resource correction before another invocation. Keep the same source, physics, mesh and acceptance thresholds unless a separate demonstrated defect requires changing them. Do not convert a failed run into success, alter the old receipt, automatically retry, or reduce the problem to fit an arbitrary cap.

The separately reviewed 24 GiB continuation subsequently completed the same genuine field and unchanged strict checks. A read-only observation of that actual process reported virtual peak 13,771,272 KiB and resident high-water 10,089,100 KiB at that point: virtual peak exceeded the old cap while resident high-water was lower. This corroborates the virtual-address distinction; it is not a claimed final whole-run resident peak. The first failed attempt remains failed. [Independent candidate review](https://github.com/Valpatel/gyropup/issues/8#issuecomment-6712047515) and [field-only adoption record](../plans/leg-control/e1-field-adoption.json) retain the still-failed strength target and pending video/artwork limits.
