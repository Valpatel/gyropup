"""Gyropup velocity task: balance on two wheels and track a forward speed and a yaw rate.

Modelled on mjlab_upkie's velocity task (Apache-2.0, rl/vendor/mjlab_upkie), adapted to Gyropup:

- Actions (50 Hz): 4 leg joint position targets around the standing pose (scale 0.5 rad) and 2 wheel velocity
  targets (scale 20 rad/s), run through DcMotor actuators built from the design's motors (see robot.py).
- Actor observations (what the robot has): IMU projected gravity and angular velocity, leg joint positions,
  all joint velocities, the previous action and the command. The critic also sees the true base linear velocity
  and height (asymmetric actor-critic).
- Rewards: track forward speed and yaw rate, stay upright, hold the standing height and leg pose, smooth actions,
  an electrical-energy proxy and a torque cost.
- Domain randomisation: mass +-10 % (mass and inertia together), centre of mass +-2 cm, wheel friction, motor
  strength +-10 %, Kp/Kd +-20 %, 0-20 ms command latency, encoder bias, pushes (curriculum).
"""
from __future__ import annotations

import math

import torch

from mjlab.envs import ManagerBasedRlEnv, ManagerBasedRlEnvCfg
from mjlab.envs import mdp
from mjlab.envs.mdp import dr
from mjlab.envs.mdp.actions import JointPositionActionCfg, JointVelocityActionCfg
from mjlab.managers.curriculum_manager import CurriculumTermCfg
from mjlab.managers.event_manager import EventTermCfg
from mjlab.managers.observation_manager import ObservationGroupCfg, ObservationTermCfg
from mjlab.managers.reward_manager import RewardTermCfg
from mjlab.managers.scene_entity_config import SceneEntityCfg
from mjlab.managers.termination_manager import TerminationTermCfg
from mjlab.rl import RslRlModelCfg, RslRlOnPolicyRunnerCfg, RslRlPpoAlgorithmCfg
from mjlab.scene import SceneCfg
from mjlab.sim import MujocoCfg, SimulationCfg
from mjlab.tasks.velocity import mdp as mdp_vel
from mjlab.tasks.velocity.mdp import UniformVelocityCommandCfg
from mjlab.terrains import TerrainEntityCfg
from mjlab.utils.noise import UniformNoiseCfg as Unoise
from mjlab.viewer import ViewerConfig

from gyropup_rl import robot as rb

LEG_ACTION_SCALE = 0.5        # rad per unit action
WHEEL_ACTION_SCALE = 20.0     # rad/s per unit action (no-load speed is ~33 rad/s on the default design)
LIN_VEL_RANGE = (-1.0, 1.0)   # m/s
YAW_RATE_RANGE = (-1.5, 1.5)  # rad/s

ROBOT = SceneEntityCfg('robot')
LEGS = SceneEntityCfg('robot', joint_names=rb.LEG_JOINTS)
ALL_JOINTS = SceneEntityCfg('robot', joint_names=rb.LEG_JOINTS + rb.WHEEL_JOINTS, preserve_order=True)


# ---------------------------------------------------------------------------------------------------------------
# Terms written for Gyropup
# ---------------------------------------------------------------------------------------------------------------

def base_height(env: ManagerBasedRlEnv, asset_cfg: SceneEntityCfg = ROBOT) -> torch.Tensor:
    return env.scene[asset_cfg.name].data.root_link_pos_w[:, 2:3]


def base_lin_vel(env: ManagerBasedRlEnv, asset_cfg: SceneEntityCfg = ROBOT) -> torch.Tensor:
    return env.scene[asset_cfg.name].data.root_link_lin_vel_b


def base_height_reward(env: ManagerBasedRlEnv, target: float, std: float, asset_cfg: SceneEntityCfg = ROBOT) -> torch.Tensor:
    z = env.scene[asset_cfg.name].data.root_link_pos_w[:, 2]
    return torch.exp(-torch.square(z - target) / std ** 2)


def leg_pose_reward(env: ManagerBasedRlEnv, std: float, asset_cfg: SceneEntityCfg = LEGS) -> torch.Tensor:
    asset = env.scene[asset_cfg.name]
    err = asset.data.joint_pos[:, asset_cfg.joint_ids] - asset.data.default_joint_pos[:, asset_cfg.joint_ids]
    return torch.exp(-torch.sum(torch.square(err), dim=1) / std ** 2)


def mechanical_power(env: ManagerBasedRlEnv, asset_cfg: SceneEntityCfg = ALL_JOINTS) -> torch.Tensor:
    """Sum of |torque x speed| over the six motors (W): a proxy for battery drain."""
    asset = env.scene[asset_cfg.name]
    tau = asset.data.qfrc_actuator[:, asset_cfg.joint_ids]
    return torch.sum(torch.abs(tau * asset.data.joint_vel[:, asset_cfg.joint_ids]), dim=1)


def torque_sq(env: ManagerBasedRlEnv, asset_cfg: SceneEntityCfg = ALL_JOINTS) -> torch.Tensor:
    asset = env.scene[asset_cfg.name]
    return torch.sum(torch.square(asset.data.qfrc_actuator[:, asset_cfg.joint_ids]), dim=1)


def motor_strength(env: ManagerBasedRlEnv, env_ids: torch.Tensor | None, scale_range: tuple[float, float],
                   asset_cfg: SceneEntityCfg = ROBOT) -> None:
    """Scale each motor's peak torque (and with it the whole torque-speed line) per environment."""
    asset = env.scene[asset_cfg.name]
    if env_ids is None:
        env_ids = torch.arange(env.num_envs, device=env.device)
    for act in asset.actuators:
        if not hasattr(act, 'saturation_effort'):
            continue
        if not hasattr(act, '_gp_default_sat'):
            act._gp_default_sat = act.saturation_effort.clone()
            act._gp_default_lim = act.force_limit.clone()
        s = torch.empty(len(env_ids), act.saturation_effort.shape[1], device=env.device).uniform_(*scale_range)
        act.saturation_effort[env_ids] = act._gp_default_sat[env_ids] * s
        act.force_limit[env_ids] = act._gp_default_lim[env_ids] * s


def push_intensity(env: ManagerBasedRlEnv, env_ids: torch.Tensor, stages: list[tuple[int, float]]) -> torch.Tensor:
    """Scale the push velocity range with training progress (steps are env steps)."""
    cfg = env.event_manager.get_term_cfg('push_robot')
    if not hasattr(push_intensity, 'base'):
        push_intensity.base = {k: tuple(v) for k, v in cfg.params['velocity_range'].items()}
    k = 0.0
    for step, val in stages:
        if env.common_step_counter >= step:
            k = val
    cfg.params['velocity_range'] = {key: (lo * k, hi * k) for key, (lo, hi) in push_intensity.base.items()}
    return torch.tensor(k)


# ---------------------------------------------------------------------------------------------------------------

def gyropup_velocity_env_cfg(play: bool = False) -> ManagerBasedRlEnvCfg:
    g = rb.load()

    actor_terms = {
        'projected_gravity': ObservationTermCfg(func=mdp.projected_gravity, noise=Unoise(n_min=-0.05, n_max=0.05)),
        'base_ang_vel': ObservationTermCfg(func=mdp.base_ang_vel, noise=Unoise(n_min=-0.2, n_max=0.2)),
        'leg_pos': ObservationTermCfg(func=mdp.joint_pos_rel, params={'biased': True, 'asset_cfg': LEGS},
                                      noise=Unoise(n_min=-0.01, n_max=0.01)),
        'joint_vel': ObservationTermCfg(func=mdp.joint_vel_rel, params={'asset_cfg': ALL_JOINTS},
                                        noise=Unoise(n_min=-1.0, n_max=1.0), scale=0.1),
        'actions': ObservationTermCfg(func=mdp.last_action),
        'command': ObservationTermCfg(func=mdp.generated_commands, params={'command_name': 'twist'}),
    }
    critic_terms = {
        **actor_terms,
        'leg_pos': ObservationTermCfg(func=mdp.joint_pos_rel, params={'asset_cfg': LEGS}),
        'base_lin_vel': ObservationTermCfg(func=base_lin_vel),
        'base_height': ObservationTermCfg(func=base_height),
    }
    observations = {
        'actor': ObservationGroupCfg(terms=actor_terms, concatenate_terms=True, enable_corruption=not play),
        'critic': ObservationGroupCfg(terms=critic_terms, concatenate_terms=True, enable_corruption=False),
    }

    actions = {
        'leg_pos': JointPositionActionCfg(entity_name='robot', actuator_names=rb.LEG_JOINTS, scale=LEG_ACTION_SCALE,
                                          use_default_offset=True, preserve_order=True),
        'wheel_vel': JointVelocityActionCfg(entity_name='robot', actuator_names=rb.WHEEL_JOINTS,
                                            scale=WHEEL_ACTION_SCALE, use_default_offset=True, preserve_order=True),
    }

    commands = {
        'twist': UniformVelocityCommandCfg(
            entity_name='robot', resampling_time_range=(3.0, 8.0), rel_standing_envs=0.1, rel_heading_envs=0.0,
            heading_command=False, debug_vis=True,
            ranges=UniformVelocityCommandCfg.Ranges(lin_vel_x=LIN_VEL_RANGE, lin_vel_y=(0.0, 0.0),
                                                    ang_vel_z=YAW_RATE_RANGE)),
    }

    alpha = (0.5 * math.log(0.9), 0.5 * math.log(1.1))     # pseudo-inertia: mass x e^(2 alpha) -> 0.9 .. 1.1
    events = {
        'reset_base': EventTermCfg(func=mdp.reset_root_state_uniform, mode='reset', params={
            'pose_range': {'x': (-0.5, 0.5), 'y': (-0.5, 0.5), 'pitch': (-0.1, 0.1), 'yaw': (-math.pi, math.pi)},
            'velocity_range': {'x': (-0.2, 0.2), 'pitch': (-0.3, 0.3)}}),
        'reset_joints': EventTermCfg(func=mdp.reset_joints_by_offset, mode='reset', params={
            'position_range': (-0.05, 0.05), 'velocity_range': (0.0, 0.0),
            'asset_cfg': SceneEntityCfg('robot', joint_names=('.*',))}),
        'push_robot': EventTermCfg(func=mdp.push_by_setting_velocity, mode='interval', interval_range_s=(2.0, 4.0),
                                   params={'velocity_range': {'x': (-0.5, 0.5), 'y': (-0.3, 0.3), 'yaw': (-0.5, 0.5)}}),
        'wheel_friction': EventTermCfg(func=dr.geom_friction, mode='startup', params={
            'asset_cfg': SceneEntityCfg('robot', geom_names=('wheel_l_col0', 'wheel_r_col0')),
            'operation': 'abs', 'axes': [0], 'ranges': (0.5, 1.25), 'shared_random': True}),
        'mass': EventTermCfg(func=dr.pseudo_inertia, mode='startup', params={
            'alpha_range': alpha, 'asset_cfg': SceneEntityCfg('robot', body_names=('.*',))}),
        'base_com': EventTermCfg(func=dr.body_com_offset, mode='startup', params={
            'asset_cfg': SceneEntityCfg('robot', body_names=('base',)), 'operation': 'add',
            'ranges': {0: (-0.02, 0.02), 1: (-0.01, 0.01), 2: (-0.02, 0.02)}}),
        'motor_strength': EventTermCfg(func=motor_strength, mode='reset', params={'scale_range': (0.9, 1.1)}),
        'pd_gains': EventTermCfg(func=dr.pd_gains, mode='reset', params={'kp_range': (0.8, 1.2), 'kd_range': (0.8, 1.2)}),
        'encoder_bias': EventTermCfg(func=dr.encoder_bias, mode='startup', params={
            'asset_cfg': SceneEntityCfg('robot', joint_names=rb.LEG_JOINTS), 'bias_range': (-0.01, 0.01)}),
    }

    rewards = {
        'track_linear_velocity': RewardTermCfg(func=mdp_vel.track_linear_velocity, weight=2.0,
                                               params={'command_name': 'twist', 'std': math.sqrt(0.1)}),
        'track_angular_velocity': RewardTermCfg(func=mdp_vel.track_angular_velocity, weight=2.0,
                                                params={'command_name': 'twist', 'std': math.sqrt(0.2)}),
        'upright': RewardTermCfg(func=mdp_vel.upright, weight=1.0,
                                 params={'std': math.sqrt(0.2), 'asset_cfg': SceneEntityCfg('robot', body_names=('base',))}),
        'base_height': RewardTermCfg(func=base_height_reward, weight=0.5, params={'target': g.base_height, 'std': 0.05}),
        'leg_pose': RewardTermCfg(func=leg_pose_reward, weight=0.3, params={'std': math.sqrt(0.5)}),
        'action_rate_l2': RewardTermCfg(func=mdp.action_rate_l2, weight=-0.05),
        'power': RewardTermCfg(func=mechanical_power, weight=-1e-3),
        'torque': RewardTermCfg(func=torque_sq, weight=-1e-4),
        'joint_limits': RewardTermCfg(func=mdp.joint_pos_limits, weight=-1.0, params={'asset_cfg': LEGS}),
        'termination': RewardTermCfg(func=mdp.is_terminated, weight=-50.0),
    }

    terminations = {
        'time_out': TerminationTermCfg(func=mdp.time_out, time_out=True),
        'fell_over': TerminationTermCfg(func=mdp.bad_orientation, params={'limit_angle': math.radians(50.0)}),
        'too_low': TerminationTermCfg(func=mdp.root_height_below_minimum, params={'minimum_height': 0.6 * g.base_height}),
    }

    it = 24   # env steps per PPO iteration
    curriculum = {
        'command_vel': CurriculumTermCfg(func=mdp_vel.commands_vel, params={
            'command_name': 'twist',
            'velocity_stages': [
                {'step': 0, 'lin_vel_x': (-0.5, 0.5), 'ang_vel_z': (-0.5, 0.5)},
                {'step': 300 * it, 'lin_vel_x': (-0.75, 0.75), 'ang_vel_z': (-1.0, 1.0)},
                {'step': 700 * it, 'lin_vel_x': LIN_VEL_RANGE, 'ang_vel_z': YAW_RATE_RANGE},
            ]}),
        'push_intensity': CurriculumTermCfg(func=push_intensity, params={
            'stages': [(0, 0.0), (1000 * it, 0.5), (2000 * it, 1.0)]}),
    }

    cfg = ManagerBasedRlEnvCfg(
        scene=SceneCfg(terrain=TerrainEntityCfg(terrain_type='plane'), num_envs=1, extent=2.0,
                       entities={'robot': rb.robot_cfg(g)}),
        observations=observations, actions=actions, commands=commands, events=events, rewards=rewards,
        terminations=terminations, curriculum=curriculum if not play else {},
        viewer=ViewerConfig(origin_type=ViewerConfig.OriginType.ASSET_BODY, entity_name='robot', body_name='base',
                            distance=2.2, elevation=-12.0, azimuth=120.0),
        sim=SimulationCfg(nconmax=None, njmax=200,
                          mujoco=MujocoCfg(timestep=rb.PHYSICS_DT, iterations=10, ls_iterations=20)),
        decimation=rb.DECIMATION,
        episode_length_s=20.0,
    )
    if play:
        cfg.episode_length_s = 1e9
        cfg.events.pop('push_robot', None)
    return cfg


GyropupVelocityRlCfg = RslRlOnPolicyRunnerCfg(
    actor=RslRlModelCfg(hidden_dims=(256, 128, 64), activation='elu', obs_normalization=True,
                        distribution_cfg={'class_name': 'GaussianDistribution', 'init_std': 0.5, 'std_type': 'scalar'}),
    critic=RslRlModelCfg(hidden_dims=(256, 128, 64), activation='elu', obs_normalization=True),
    algorithm=RslRlPpoAlgorithmCfg(value_loss_coef=1.0, use_clipped_value_loss=True, clip_param=0.2, entropy_coef=0.005,
                                   num_learning_epochs=5, num_mini_batches=4, learning_rate=1.0e-3, schedule='adaptive',
                                   gamma=0.99, lam=0.95, desired_kl=0.01, max_grad_norm=1.0),
    logger='tensorboard',
    experiment_name='gyropup_velocity',
    save_interval=250,
    num_steps_per_env=24,
    max_iterations=4000,
)
