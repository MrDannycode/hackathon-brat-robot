"""Conservative servo-space control. No guessed poses or automatic torque release."""
from __future__ import annotations

import logging
import math
from pathlib import Path
import time

from .protocol import encode_angle, read_angle, write_angle

LOG = logging.getLogger(__name__)


class Arm:
    def __init__(self, config, *, dry_run=False, lock_path=None):
        self.config = config
        self.dry_run = dry_run
        self.bus = None
        self._lock = None
        self._retreat = None
        if config['gripper']['servo_id'] != 6:
            raise ValueError('DOFBOT foloseste servo 6 pentru gripper.')
        settings = config['motion']
        for name in ('max_speed_deg_s', 'minimum_duration_ms', 'tick_ms', 'command_gap_s',
                     'settle_s', 'feedback_tolerance_deg', 'uncommanded_drift_deg', 'manual_max_step_deg'):
            value = settings[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'Parametru de miscare invalid: {name}')
        if settings['manual_max_step_deg'] > 5:
            raise ValueError('Pasul manual nu poate depasi 5 grade.')
        self.current = list(config['simulation']['initial_angles'])
        if config['calibration'].get('simulated') and not dry_run:
            raise ValueError('Config simulata: utilizarea pe hardware este interzisa.')
        for servo_id, angle in enumerate(self.current, 1):
            encode_angle(config, servo_id, angle)
        if not dry_run:
            import fcntl
            from smbus import SMBus
            path = Path(lock_path or Path(__file__).resolve().parents[1] / '.arm.lock')
            self._lock = path.open('a')
            try:
                fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.bus = SMBus(config['arm']['bus'])
                self.read()
            except BaseException:
                self.close()
                raise
        LOG.info('Brat conectat (%s); cuplul nu este modificat la conectare.', 'SIMULAT' if dry_run else 'I2C')

    def read(self):
        if self.bus is not None:
            self.current = [read_angle(self.bus, self.config, i) for i in range(1, 7)]
        return list(self.current)

    def validate_pose(self, pose):
        if not isinstance(pose, (list, tuple)) or len(pose) != 5:
            raise ValueError('Pozitie necalibrata: sunt necesare 5 unghiuri, fara gripper.')
        for servo_id, angle in enumerate(pose, 1):
            if isinstance(angle, bool) or not isinstance(angle, (int, float)):
                raise ValueError('Unghiurile trebuie sa fie numere finite.')
            encode_angle(self.config, servo_id, angle)
        return list(pose)

    def named_pose(self, name):
        return self.validate_pose(self.config['poses'].get(name))

    def _move(self, targets):
        settings = self.config['motion']
        for servo_id, angle in targets.items():
            encode_angle(self.config, servo_id, angle)
        before = self.read()
        distance = max(abs(angle - before[servo_id - 1]) for servo_id, angle in targets.items())
        if distance <= settings['command_epsilon_deg']:
            return
        # smoothstep has a peak derivative of 1.5: account for it in speed limit.
        duration = max(settings['minimum_duration_ms'] / 1000,
                       1.5 * distance / settings['max_speed_deg_s'])
        ticks = max(1, math.ceil(duration / (settings['tick_ms'] / 1000)))
        tick_duration = duration / ticks
        segment_ms = math.ceil(tick_duration * 1000)
        if not 1 <= segment_ms <= 65535:
            raise ValueError('Durata segmentului depaseste protocolul.')
        LOG.info('%sMiscare %s, durata minima %.2fs', '[SIMULAT] ' if self.dry_run else '', targets, duration)
        started = time.monotonic()
        for tick in range(1, ticks + 1):
            u = tick / ticks
            factor = u * u * (3 - 2 * u)
            for servo_id, angle in targets.items():
                if abs(angle - before[servo_id - 1]) <= settings['command_epsilon_deg']:
                    continue
                command = before[servo_id - 1] + (angle - before[servo_id - 1]) * factor
                write_angle(self.bus, self.config, servo_id, command, segment_ms)
                if self.bus is not None:
                    time.sleep(settings['command_gap_s'])
            if self.bus is not None:
                # Wait a full final segment after the last command too.
                deadline = started + (tick + 1) * tick_duration
                time.sleep(max(0, deadline - time.monotonic()))
        if self.bus is None:
            for servo_id, angle in targets.items():
                self.current[servo_id - 1] = angle
        else:
            time.sleep(settings['settle_s'])
            measured = self.read()
            for servo_id in range(1, 7):
                expected = targets.get(servo_id, before[servo_id - 1])
                tolerance = (settings['feedback_tolerance_deg'] if servo_id in targets
                             else settings['uncommanded_drift_deg'])
                if abs(measured[servo_id - 1] - expected) > tolerance:
                    raise RuntimeError(f'S{servo_id}: feedback {measured[servo_id - 1]:.2f}, asteptat {expected:.2f}; miscare oprita.')

    def move_servo(self, servo_id, angle, *, manual=False):
        encode_angle(self.config, servo_id, angle)
        if manual:
            current = self.read()[servo_id - 1]
            if abs(angle - current) > self.config['motion']['manual_max_step_deg']:
                raise ValueError('Pas manual prea mare; foloseste pasi mici din configuratie.')
        self._move({servo_id: angle})

    def move_pose(self, pose):
        self._move(dict(enumerate(self.validate_pose(pose), 1)))

    def _grip_angle(self, name):
        angle = self.config['gripper'].get(name + '_deg')
        if angle is None:
            raise ValueError(f'Gripper {name}: pozitie necalibrata.')
        encode_angle(self.config, self.config['gripper']['servo_id'], angle)
        return angle

    def gripper_open(self):
        self.move_servo(self.config['gripper']['servo_id'], self._grip_angle('open'))

    def gripper_close(self):
        self.move_servo(self.config['gripper']['servo_id'], self._grip_angle('closed'))

    def home(self):
        transit, home = self.named_pose('transit'), self.named_pose('home')
        self.move_pose(transit)
        self.move_pose(home)

    def validate_station(self, pose):
        if not isinstance(pose, dict):
            raise ValueError('Celula necalibrata.')
        self.validate_pose(pose.get('approach'))
        self.validate_pose(pose.get('contact'))
        self.named_pose('transit')
        self._grip_angle('open')
        self._grip_angle('closed')

    def pick(self, pose):
        self.validate_station(pose)
        self.move_pose(self.named_pose('transit'))
        self.gripper_open()
        self.move_pose(pose['approach'])
        self._retreat = list(pose['approach'])
        self.move_pose(pose['contact'])
        self.gripper_close()
        self.move_pose(pose['approach'])
        self._retreat = None
        self.move_pose(self.named_pose('transit'))

    def place(self, pose):
        self.validate_station(pose)
        self.move_pose(self.named_pose('transit'))
        self.move_pose(pose['approach'])
        self._retreat = list(pose['approach'])
        self.move_pose(pose['contact'])
        self.gripper_open()
        self.move_pose(pose['approach'])
        self._retreat = None
        self.move_pose(self.named_pose('transit'))

    def safe_shutdown(self):
        if not self.config['safety']['recovery_enabled']:
            LOG.warning('Recuperare automata necalibrata: mentin cuplul, nu comand home sau gripper.')
            return False
        # Validate all recovery endpoints before starting recovery.
        self.named_pose('home')
        self.named_pose('transit')
        self._grip_angle('open')
        if self._retreat is not None:
            self.move_pose(self.validate_pose(self._retreat))
            self._retreat = None
        self.move_pose(self.named_pose('transit'))
        self.gripper_open()
        self.home()
        return True

    def close(self):
        # Closing an I2C descriptor must never release motor torque.
        if self.bus is not None:
            self.bus.close()
            self.bus = None
        if self._lock is not None:
            self._lock.close()
            self._lock = None
