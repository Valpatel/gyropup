"""The single-leg rig's software: the RS-04 driver, the CAN transports, the motor-bus abstraction (CAN or MuJoCo), the
controller port, the runner and its logs (docs/leg-prototype-plan.md section 4).

Nothing here imports MuJoCo except rig/sim_bus.py, so the laptop that drives the motors needs only numpy.
"""
