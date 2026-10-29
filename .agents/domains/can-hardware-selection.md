# CAN hardware selection

Evaluate three independent layers: power/mechanics, CAN physical/data-link compatibility, and application commands. Different application protocols can share a physical bus when frame formats, bitrate, identifiers, receiver behavior and traffic coexist. A host can implement multiple drivers; matching protocol names is not a prerequisite.

Treat an existing rail as a recorded design choice with an intent, not an immutable input to a new architecture. If direct battery power is proposed, check the candidate's full input range, the motor and downstream parts, current/thermal limits, transients and regeneration. Record any previous physical limiting function that the change would revise.

Use exact manufacturer model/revision documents; separate nominal, continuous, peak and provisional ratings. Record unknowns as unknowns. Consult the source-linked [2026-10-29 candidate assessment](../../research/can-actuator-candidates-2026-10-29.md) before repeating MAD/Hitec/MYACTUATOR research. This is research guidance, not hardware qualification.
