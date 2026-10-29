# Removable carrier input protection — design comparison in progress

No architecture is selected by this note. This bounded study addresses the base-board U2 supply and its interface with D14; it does not release the carrier for printing or powered operation. It follows supply audit PR #80 and coordinates with carrier PR #67. Tracking: #81; integration base `154d4de035a22edd798179645d30323707b90535`.

## Frozen starting requirements

- Source: stand 15–20.5 V; robot 30–42 V. These are documented operating assumptions, not measured transient bounds.
- U2: one D36V50F12 module supplies 12 V PAN to one 12 V STS3215 servo plus the pendant/555 circuit. The other two turret servos are outside U2.
- C2: the whole 10 A fused head branch, including the downstream slip-ring loads. Protecting U2 alone does not qualify the remaining BUS loads.
- Existing model estimates: 0.15 A holding, 0.6 A moving, 1.5 A torque-capped PAN; 90% converter efficiency. These are not verified peak/stall-current guarantees.
- Manufacturer revision and exact servo identity, source impedance, inductance, transient waveform/repetition, fault energy, carrier temperature and output regeneration require explicit treatment.

## Planned evidence

Verify manufacturer specifications and compare a small number of higher-input converters and active upstream protection architectures. Record exact order identity, availability, dimensions, operating versus absolute limits, losses and unresolved physical fit. Publish standard-library calculations with inputs and outputs; no unmeasured waveform will be treated as a certified bound.

The carrier author owns connector selection, layout and catalog files. This work will not silently change those selections.
