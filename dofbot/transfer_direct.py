"""Single mechanical transfer through calibrated local approach poses.

No camera verification: this is not task1.py or an autonomous contest trial.
Real execution never asks for Enter between movements.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
import time

from common.arm import Arm
from common.settings import DEFAULT_CONFIG, load_config

LOG = logging.getLogger('transfer')


def station(config, grid_name, value):
    row, col = map(int, value.split(','))
    grid = config['grids'][grid_name]
    if not (1 <= row <= grid['rows'] and 1 <= col <= grid['cols']):
        raise ValueError(f'Celula invalida: {grid_name} {value}')
    return config['cells'][grid_name][f'{row},{col}']


def transfer(arm, config, source, destination):
    # Validate every endpoint and both gripper angles before any motion.
    for entry in (source, destination):
        arm.validate_station(entry)
    opened, closed = arm._grip_angle('open'), arm._grip_angle('closed')
    tolerance = config['motion']['feedback_tolerance_deg']
    if abs(opened - closed) <= tolerance:
        raise ValueError('Deschiderea si prinderea nu sunt distincte.')
    if max(abs(a - b) for a, b in zip(source['contact'], destination['contact'])) <= tolerance:
        raise ValueError('Sursa si destinatia au aceeasi pozitie de contact.')
    current = arm.read()
    if abs(current[5] - opened) > tolerance:
        raise ValueError('Pornire refuzata: clestele trebuie sa fie gol si deschis. '
                         'Sustine cubul inainte sa executi open in calibrate.py.')
    # Starting from arbitrary manually adjusted angles must never trigger a
    # blind route. Only one of these saved local poses is accepted.
    starts = [('source_approach', source['approach'], None),
              ('source_contact', source['contact'], source['approach']),
              ('destination_approach', destination['approach'], None),
              ('destination_contact', destination['contact'], destination['approach'])]
    matches = [(name, retreat) for name, pose, retreat in starts
               if max(abs(a - b) for a, b in zip(current[:5], pose)) <= tolerance]
    if not matches:
        raise ValueError('Pozitia actuala nu corespunde unui approach/contact salvat. '
                         'Oprit fara miscare; nu comand home sau transit.')
    start_name, retreat = matches[0]
    LOG.info('Pornire din %s; cleste deschis.', start_name)
    started = time.monotonic()
    budget = config['competition']['time_limit_s']

    def step(name, action):
        elapsed = time.monotonic() - started
        if elapsed >= budget:
            raise RuntimeError('Limita de timp atinsa; nu comand alte miscari.')
        if elapsed >= config['competition']['warning_s']:
            LOG.warning('Au trecut peste 4 minute.')
        LOG.info('[%.1fs] %s', elapsed, name)
        action()

    if retreat is not None:
        step('Retragere din contact la approach-ul aceleiasi celule', lambda: arm.move_pose(retreat))
    for name, pose in [('Apropiere sursa', source['approach']),
                       ('Coborare la cub', source['contact'])]:
        step(name, lambda pose=pose: arm.move_pose(pose))
    step('Prindere cub', arm.gripper_close)
    step('Ridicare cub', lambda: arm.move_pose(source['approach']))
    step('Deplasare spre destinatie', lambda: arm.move_pose(destination['approach']))
    step('Coborare la destinatie', lambda: arm.move_pose(destination['contact']))
    step('Eliberare cub', arm.gripper_open)
    step('Retragere deasupra destinatiei', lambda: arm.move_pose(destination['approach']))
    LOG.info('Transfer mecanic incheiat in %.1fs. Verifica fizic cubul la destinatie; '
             'nu s-a facut verificare vizuala automata.', time.monotonic() - started)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='linie,coloana')
    parser.add_argument('--target', required=True, help='linie,coloana')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    arm = None
    try:
        config = load_config(args.config)
        source = station(config, 'source', args.source)
        destination = station(config, 'destination', args.target)
        arm = Arm(config, dry_run=args.dry_run)
        if args.dry_run:
            arm.validate_station(source)
            arm.current = source['approach'][:] + [arm._grip_angle('open')]
        transfer(arm, config, source, destination)
        return 0
    except KeyboardInterrupt:
        LOG.warning('Ctrl+C: oprit. Pastrez cuplul si pozitia clestelui; '
                    'nu execut recuperare pe trasee nevalidate.')
        return 130
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        LOG.error('Transfer oprit: %s. Pastrez clestele si nu comand revenire automata.', exc)
        return 1
    finally:
        if arm is not None:
            arm.close()


if __name__ == '__main__':
    raise SystemExit(main())
