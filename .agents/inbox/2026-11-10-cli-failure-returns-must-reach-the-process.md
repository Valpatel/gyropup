# A failed gate return must become the CLI process exit

On 2026-11-10, independent review of PR280 at `55c7e815` ran the actual
`robot_native_playback.py --validate` CLI with the reviewed core `011a29b6` and
its real three-box CAD fixture. The written report had `pass=false` and
`status=fail`; stdout said `Native playback has blocked or undecided paths`,
but the process returned exit0. This was a real entry-point defect, not a
passing validation. No Gyropup native collection or sweep had been submitted.

Cause: `main()` returned1 for a failed verdict, while the module entry point
called `main()` and discarded that return. Testing the Python return or only
checking report contents would miss the shell/runner contract failure.

Corrective rule: propagate the return with `raise SystemExit(main())`. Exercise
the actual script in a subprocess and require both a nonzero exit and preserved
failed report/input files. The ordinary robot test suite uses an explicitly
failed dependency double to enforce this entry-point contract without a CAD
installation; it makes no native geometry claim. A separately requested test
uses the real reviewed core three-box fixture and requires the same process and
report behavior. Keep the original exit0 counterexample in the review history.

Commands for the two controls are documented in
[the native validation runbook](../plans/assembly-staging/native-validation.md)
and implemented in `tests/site/assembly/test_robot_native_playback.py`.
The real fixture checks a small CAD negative, not Gyropup geometry, supports,
fastening, physics or physical assembly. CLI failure propagation does not
establish the correctness of a geometric verdict or qualify a robot build.
