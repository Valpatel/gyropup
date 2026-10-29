# Mesher runtime selection must happen before Python starts

On 2026-10-29 an isolated ARM CAD runner used a manually installed Gmsh 4.15.2 binary and its matching OpenSSL libraries from an existing read-only mesher prefix. The first bounded E1 launch failed before meshing with an OpenSSL version/symbol mismatch. Moving `import gmsh` above CadQuery was insufficient: the script already imported `hashlib`, which had loaded system `libcrypto`.

Corrective launch, with the actual prefix supplied from private host configuration:

```bash
LD_PRELOAD="$CAD_MESHER_PREFIX/lib/libcrypto.so.3:$CAD_MESHER_PREFIX/lib/libssl.so.3" \
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  "$ISOLATED_CAD_PYTHON" tools/export-hip-frame-e1.py
```

The successful `831532a951ae55df4d1f09470382ba7779c71fa3` run checked `/proc/self/maps` and recorded actual mapped `libgmsh`, `libcrypto`, `libssl` and `libs2n` hashes in `field-receipt.json`; it reproduced the single E1 case. A separate post-solve failure was `PackageNotFoundError` from `importlib.metadata.version('gmsh')`: this mesher is manually installed, so its runtime version comes from `gmsh.__version__`. The clean rerun completed with exit 0. Exact logs and run commands are linked from issue #69.

Corrective rule: preflight the complete import order, including stdlib crypto users, and record the libraries actually mapped. If the pinned mesher requires paired libraries, select them in that process's launch environment before Python starts. Do not alter global loader configuration, unrelated environments or system libraries. A Python module can be usable without wheel distribution metadata; distinguish runtime identity from package-manager metadata.

Limits: this is a known pinned runner configuration, not a general recommendation to preload arbitrary OpenSSL libraries. Revalidate compatibility after any binary/runtime upgrade; do not change a working shared environment to satisfy one job.
