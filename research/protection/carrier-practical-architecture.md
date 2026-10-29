# Practical PAN architecture — focused decision in progress

[Issue91](https://github.com/Valpatel/gyropup/issues/91) follows the reviewed circuit candidate merged at `912439f`. The next checkpoint chooses a practical direction before committing board area. No existing circuit, catalog, geometry, supply or actuator contract is changed here.

Candidate B's conditional 15 V corner leaves only 69 mV enable headroom, while its series-diode loss screen reaches approximately 5.98 W. The diode's free-air condition does not support the declared load. A compact build cannot assume those limits away. Compare a small number of exact lower-loss protected paths and appropriately rated converter/module alternatives, including charged-output reverse stress and obtainable parts. Preserve the 15–20.5 V stand /30–42 V robot sources and 12 V servo requirement.

Mechanical author confirmation on 2026-10-29: **no additional protection-board envelope is allocated**. The legacy25.4×25.4×9.5 mm U2 reservation remains unqualified. The opt-in C3 support occupies turret X56..93,Y−27..19,Z6..56 mm and is not spare PCB area. Package dimensions below will be selection evidence only until a complete available-volume and thermal layout is reviewed.

Next: primary differential/thermal checks and dated supplier observations, reproducible screening, one recommendation, then independent review. No purchases, energized tests, large schematic revision or PCB placement is authorized by this note.
