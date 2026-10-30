"""Interactive physical calibration. GUI commands run from the Pi VNC desktop."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime
import logging
import math
import os
from pathlib import Path
import shlex

from common.arm import Arm
from common.camera import Camera
from common.settings import DEFAULT_CONFIG, load_config, save_config

LOG = logging.getLogger('calibrate')
HELP = '''
read                               unghiuri curente S1..S6
j ID UNGHI                         miscare manuala, pas maxim din config
limit ID MIN MAX                   limite conservative; NU executa miscare
save home|transit|view_source|view_destination
save source|destination RAND,COL approach|contact
save tower RAND,COL NIVEL approach|contact
grip open|closed                   salveaza unghiul CURENT S6, fara miscare
open / close                       executa pozitia calibrata a gripperului
goto home|transit|view_source|view_destination
preview                            camera live; S salveaza imagine, Q revine
hsv CULOARE [BANDA]                 praguri HSV live; S salveaza, Q anuleaza
grid source|destination            4 clickuri: stanga-sus, dreapta-sus,
                                   dreapta-jos, stanga-jos; S salveaza, R reia
height MM                          inaltime cub; nu calculeaza unghiuri servo
recovery on|off                    permite/refuza revenire automata calibrata
test SURSA_R,C DESTINATIE_R,C       un pick/place mecanic, necesita calibrare
status / help / exit
Liniile/coloanele sunt 1..3. Nivelurile turnului sunt 1..5.
Nu exista eliberare automata a cuplului la iesire.
'''


def cell_key(value, config):
    row, col = (int(part) for part in value.split(','))
    grid = config['grids']['source']
    if not 1 <= row <= grid['rows'] or not 1 <= col <= grid['cols']:
        raise ValueError('Celula este in afara grilei.')
    return f'{row},{col}'


def require_gui():
    if os.name != 'nt' and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        raise RuntimeError('Preview necesita desktop: deschide un terminal in sesiunea VNC a Pi-ului.')


def gui(config, path, mode, arguments):
    require_gui()
    import cv2
    import numpy as np
    window = 'Calibrare DOFBOT'
    candidate = copy.deepcopy(config)
    points = []
    if mode == 'hsv':
        color = arguments[0]
        band_index = int(arguments[1]) - 1 if len(arguments) > 1 else 0
        bands = candidate['vision']['hsv'][color]
        if not 0 <= band_index < len(bands):
            raise ValueError('Banda HSV inexistenta.')
        band = bands[band_index]
    elif mode == 'grid':
        grid_name = arguments[0]
        if grid_name not in candidate['grids']:
            raise ValueError('Grila trebuie sa fie source sau destination.')
    camera = Camera(config)
    try:
        cv2.namedWindow(window)
        if mode == 'hsv':
            for prefix, values in (('low', band['lower']), ('high', band['upper'])):
                for axis, value, maximum in zip('HSV', values, (179, 255, 255)):
                    cv2.createTrackbar(prefix + axis, window, value, maximum, lambda _: None)
        if mode == 'grid':
            def clicked(event, x, y, flags, parameter):
                if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
                    points.append([x, y])
            cv2.setMouseCallback(window, clicked)
        while True:
            frame = camera.read(flush=False)
            display = frame.copy()
            if mode == 'hsv':
                band['lower'] = [cv2.getTrackbarPos('low' + axis, window) for axis in 'HSV']
                band['upper'] = [cv2.getTrackbarPos('high' + axis, window) for axis in 'HSV']
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                for item in bands:
                    mask |= cv2.inRange(hsv, np.array(item['lower']), np.array(item['upper']))
                display = np.hstack([display, cv2.bitwise_and(frame, frame, mask=mask)])
            elif mode == 'grid':
                for index, point in enumerate(points):
                    cv2.circle(display, tuple(point), 5, (0, 255, 255), -1)
                    cv2.putText(display, str(index + 1), tuple(point), cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (0, 0, 0), 2)
                if len(points) == 4:
                    cv2.polylines(display, [np.array(points)], True, (0, 255, 255), 2)
            cv2.putText(display, 'S=save Q=cancel R=reset', (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 2)
            cv2.imshow(window, display)
            key = cv2.waitKey(1) & 255
            if key in (ord('q'), 27) or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                return
            if key == ord('r'):
                points.clear()
            if key != ord('s'):
                continue
            if mode == 'preview':
                image_path = path.parent.parent / 'artifacts' / ('calibration_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.jpg')
                image_path.parent.mkdir(exist_ok=True)
                if not cv2.imwrite(str(image_path), frame):
                    raise RuntimeError('Salvarea imaginii a esuat.')
                LOG.info('Imagine salvata: %s', image_path)
                continue
            if mode == 'hsv':
                if any(low > high for low, high in zip(band['lower'], band['upper'])):
                    LOG.warning('Limita inferioara depaseste limita superioara; nu salvez.')
                    continue
                candidate['vision']['validated_on_real_images'] = False
            if mode == 'grid':
                contour = np.array(points, dtype=np.float32)
                if len(points) != 4 or not cv2.isContourConvex(contour) or abs(cv2.contourArea(contour)) < config['vision']['minimum_grid_area_px']:
                    LOG.warning('Sunt necesare 4 colturi ordonate, convexe, cu arie suficienta.')
                    continue
                candidate['grids'][grid_name]['corners_px'] = points
                candidate['vision']['validated_on_real_images'] = False
            save_config(path, candidate)
            config.clear()
            config.update(candidate)
            LOG.info('Calibrare GUI salvata: %s', path)
            return
    finally:
        camera.close()
        cv2.destroyAllWindows()


def save_pose_command(args, arm, config):
    measured = arm.read()[:5]
    arm.validate_pose(measured)
    if len(args) == 1 and args[0] in config['poses']:
        config['poses'][args[0]] = measured
    elif len(args) == 3 and args[0] in config['cells'] and args[2] in ('approach', 'contact'):
        config['cells'][args[0]][cell_key(args[1], config)][args[2]] = measured
    elif len(args) == 4 and args[0] == 'tower' and args[3] in ('approach', 'contact'):
        levels = config['tower']['targets'][cell_key(args[1], config)]
        level = str(int(args[2]))
        if level not in levels:
            raise ValueError('Nivel invalid.')
        levels[level][args[3]] = measured
    else:
        raise ValueError('Sintaxa save invalida; consulta help.')


def status(config):
    print('Pozitii generale:', {name: value is not None for name, value in config['poses'].items()})
    print('Gripper:', config['gripper'])
    for name, cells in config['cells'].items():
        complete = sum(all(value.get(key) is not None for key in ('approach', 'contact')) for value in cells.values())
        print(f'{name}: {complete}/{len(cells)} celule cu approach si contact')
    print('Recuperare automata:', config['safety']['recovery_enabled'])
    print('Praguri validate pe imagini reale:', config['vision']['validated_on_real_images'])


def command(parts, arm, config, path):
    name, args = parts[0], parts[1:]
    if name == 'exit':
        arm.safe_shutdown()
        return False
    if name == 'help':
        print(HELP)
    elif name == 'read':
        print(' '.join(f'S{i}={angle:.2f}' for i, angle in enumerate(arm.read(), 1)))
    elif name == 'j' and len(args) == 2:
        arm.move_servo(int(args[0]), float(args[1]), manual=True)
    elif name == 'limit' and len(args) == 3:
        servo_id, low, high = int(args[0]), float(args[1]), float(args[2])
        maximum = config['arm']['protocol']['servo5' if servo_id == 5 else 'standard']['degrees']
        if servo_id not in range(1, 7) or not 0 <= low < high <= maximum:
            raise ValueError('Limite invalide.')
        if not low <= arm.read()[servo_id - 1] <= high:
            raise ValueError('Pozitia curenta ar fi in afara noilor limite.')
        config['arm']['limits_deg'][servo_id - 1] = [low, high]
        save_config(path, config)
    elif name == 'save':
        save_pose_command(args, arm, config)
        save_config(path, config)
        LOG.info('Pozitie salvata in %s', path)
    elif name == 'grip' and len(args) == 1 and args[0] in ('open', 'closed'):
        config['gripper'][args[0] + '_deg'] = arm.read()[config['gripper']['servo_id'] - 1]
        save_config(path, config)
    elif name in ('open', 'close') and not args:
        (arm.gripper_open if name == 'open' else arm.gripper_close)()
    elif name == 'goto' and len(args) == 1:
        destination, transit = arm.named_pose(args[0]), arm.named_pose('transit')
        arm.move_pose(transit)
        arm.move_pose(destination)
    elif name == 'height' and len(args) == 1:
        height = float(args[0])
        if not math.isfinite(height) or height <= 0:
            raise ValueError('Inaltimea trebuie sa fie pozitiva, in mm.')
        config['tower']['cube_height_mm'] = height
        config['tower']['level_heights_mm'] = [height * i for i in range(len(config['tower']['level_heights_mm']))]
        save_config(path, config)
    elif name in ('preview', 'hsv', 'grid'):
        if (name == 'preview' and args) or (name in ('hsv', 'grid') and not args):
            raise ValueError('Sintaxa GUI invalida; consulta help.')
        gui(config, path, name, args)
    elif name == 'recovery' and args in (['on'], ['off']):
        if args == ['on']:
            arm.named_pose('home')
            arm.named_pose('transit')
            arm._grip_angle('open')
        config['safety']['recovery_enabled'] = args == ['on']
        save_config(path, config)
    elif name == 'test' and len(args) == 2:
        source = config['cells']['source'][cell_key(args[0], config)]
        destination = config['cells']['destination'][cell_key(args[1], config)]
        arm.validate_station(source)
        arm.validate_station(destination)
        if not config['safety']['recovery_enabled']:
            raise ValueError('Calibreaza si verifica traseul home/transit si recovery on inainte de test.')
        LOG.warning('Test MECANIC pick/place; verificarea vizuala automata urmeaza in etapa 3.')
        arm.pick(source)
        arm.place(destination)
    elif name == 'status':
        status(config)
    else:
        raise ValueError('Comanda necunoscuta sau argumente invalide; consulta help.')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--smoke', action='store_true', help='Verificare simulata neinteractiva; necesita --dry-run')
    args = parser.parse_args()
    if args.smoke and not args.dry_run:
        parser.error('--smoke necesita --dry-run')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    path = args.config.resolve()
    config = load_config(path)
    if args.dry_run:
        path = path.with_name(path.stem + '.dry-run.json')
        if path.exists():
            config = load_config(path)
        config['calibration']['simulated'] = True
        LOG.warning('SIMULARE brat. Salvarile merg exclusiv in %s', path)
    arm = None
    try:
        arm = Arm(config, dry_run=args.dry_run)
        if args.smoke:
            start = arm.read()[0]
            step = config['motion']['manual_max_step_deg']
            target = start + step if start + step <= config['arm']['limits_deg'][0][1] else start - step
            arm.move_servo(1, target, manual=True)
            arm.move_servo(1, start, manual=True)
            status(config)
            return 0
        print(HELP)
        print('Config:', path)
        while True:
            try:
                line = input('SIM> ' if args.dry_run else 'DOFBOT> ')
                parts = shlex.split(line)
                if parts and not command(parts, arm, config, path):
                    return 0
            except (ValueError, KeyError, IndexError) as exc:
                LOG.error('%s', exc)
    except EOFError:
        if arm is not None:
            arm.safe_shutdown()
        return 0
    except KeyboardInterrupt:
        LOG.warning('Ctrl+C: opresc operatia si aplic doar recuperarea calibrata.')
        if arm is not None:
            arm.safe_shutdown()
        return 130
    except (OSError, RuntimeError) as exc:
        LOG.error('Operatie oprita: %s. Cuplul nu este eliberat automat.', exc)
        # Feedback/I2C failure: blind automatic motion is unsafe.
        return 1
    finally:
        if arm is not None:
            arm.close()


if __name__ == '__main__':
    raise SystemExit(main())
