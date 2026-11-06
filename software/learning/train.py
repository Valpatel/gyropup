"""Train the Gyropup velocity policy with mjlab + RSL-RL (PPO) on the GPU.

    cd rl && .venv/bin/python train.py --design designs/default.json [mjlab train options]
    e.g. .venv/bin/python train.py --design designs/flexvolt-2x20v.json --env.scene.num-envs 4096 --agent.max-iterations 3000

The design is built with sim/model.py (main venv) into rl/build/<design>/ first. Logs and checkpoints go to
rl/logs/rsl_rl/gyropup_velocity/<date>_<design>/ (TensorBoard). Any option after the design is passed to mjlab's
`train` (see `--help`).
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    args = sys.argv[1:]
    design = 'designs/default.json'
    if '--design' in args:
        i = args.index('--design')
        design = args[i + 1]
        del args[i:i + 2]
    os.environ['GYROPUP_DESIGN'] = design
    os.chdir(HERE)
    sys.path.insert(0, str(HERE))
    from gyropup_rl.tasks import TASK
    if not any(a.startswith('--agent.run-name') for a in args):
        args += ['--agent.run-name', Path(design).stem]
    from mjlab.scripts.train import main as mjlab_train
    sys.argv = [sys.argv[0], TASK, *args]
    mjlab_train()


if __name__ == '__main__':
    main()
