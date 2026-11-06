"""Registers the Gyropup tasks with mjlab. The design comes from GYROPUP_DESIGN (default designs/default.json)."""
from pathlib import Path

from mjlab.rl.runner import MjlabOnPolicyRunner
from mjlab.tasks.registry import register_mjlab_task

from gyropup_rl.velocity_env_cfg import GyropupVelocityRlCfg, gyropup_velocity_env_cfg

TASK = 'Gyropup-Velocity'


class GyropupRunner(MjlabOnPolicyRunner):
    """Saves an ONNX copy of the policy next to every checkpoint (model_N.pt -> model_N.onnx)."""

    def save(self, path: str, infos=None):
        super().save(path, infos)
        p = Path(path)
        try:
            self.export_policy_to_onnx(str(p.parent), p.with_suffix('.onnx').name)
        except Exception as e:  # never stop training for an export problem
            print(f'[WARN] ONNX export failed (training continues): {e}')


register_mjlab_task(
    task_id=TASK,
    env_cfg=gyropup_velocity_env_cfg(),
    play_env_cfg=gyropup_velocity_env_cfg(play=True),
    rl_cfg=GyropupVelocityRlCfg,
    runner_cls=GyropupRunner,
)
