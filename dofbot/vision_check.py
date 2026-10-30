"""Offline vision checks on saved images. Does not connect to arm or camera."""
import argparse
import json
from pathlib import Path

import cv2

from common.settings import DEFAULT_CONFIG, load_config
from common.vision import candidates, inspect, overlay, reference_mapping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--grid', choices=['source', 'destination'], default='source')
    parser.add_argument('--geometry', type=Path)
    parser.add_argument('--reference', help='Four confirmed centers: red:2,1;yellow:2,3;green:3,1;blue:3,3')
    parser.add_argument('--output', type=Path, default=Path('artifacts/vision'))
    args = parser.parse_args()
    if args.reference and args.geometry:
        parser.error('Alege --reference sau --geometry.')
    config = load_config(args.config)
    frame = cv2.imread(str(args.image))
    if frame is None:
        parser.error('Imagine inexistenta sau imposibil de citit.')
    geometry = json.loads(args.geometry.read_text()) if args.geometry else None
    if args.reference:
        references = {}
        for item in args.reference.split(';'):
            color, cell = item.split(':')
            references[color] = tuple(map(int, cell.split(',')))
        geometry = reference_mapping(candidates(frame, config), references,
                                     config['grids'][args.grid], frame.shape)
    result = inspect(frame, config, args.grid, geometry)
    result['image'] = str(args.image)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if geometry is not None:
        args.output.with_suffix('.geometry.json').write_text(json.dumps(geometry, indent=2))
    args.output.with_suffix('.json').write_text(json.dumps(result, indent=2))
    if not cv2.imwrite(str(args.output.with_suffix('.jpg')),
                       overlay(frame, result, config['grids'][args.grid])):
        raise RuntimeError('Nu am putut salva overlay.')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
