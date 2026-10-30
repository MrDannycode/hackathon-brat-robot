"""HSV face candidates and calibrated mapping; never commands hardware.

The table-plane homography must NOT be used for elevated cube faces. A separate
face-plane mapping needs references at cube height and an independent check.
"""
from __future__ import annotations

import math

import cv2
import numpy as np


def candidates(frame, config):
    if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError('Este necesara o imagine BGR.')
    settings = config['vision']['detector']
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    kernel = np.ones((settings['morphology_kernel_px'],) * 2, np.uint8)
    image_area = frame.shape[0] * frame.shape[1]
    found = []
    for color, bands in config['vision']['hsv'].items():
        mask = np.zeros(frame.shape[:2], np.uint8)
        for band in bands:
            mask |= cv2.inRange(hsv, np.array(band['lower']), np.array(band['upper']))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = cv2.contourArea(contour)
            if not settings['min_area_fraction'] <= area / image_area <= settings['max_area_fraction']:
                continue
            x, y, width, height = cv2.boundingRect(contour)
            if area / (width * height) < settings['min_fill_fraction']:
                continue
            moment = cv2.moments(contour)
            center = [moment['m10'] / moment['m00'], moment['m01'] / moment['m00']]
            margin = settings['image_border_margin_px']
            clipped = (x <= margin or y <= margin or
                       x + width >= frame.shape[1] - margin or
                       y + height >= frame.shape[0] - margin)
            found.append(dict(color=color, center_px=center, bbox_px=[x, y, width, height],
                              area_px=area, clipped=clipped))
    return sorted(found, key=lambda obj: (obj['color'], obj['center_px']))


def reference_mapping(objects, references, grid, frame_shape):
    """Fit a PROVISIONAL face-center map from four confirmed, centered cubes."""
    if len(references) != 4 or len(set(references.values())) != 4:
        raise ValueError('Sunt necesare 4 culori in 4 celule distincte.')
    source, destination = [], []
    for color, (row, col) in references.items():
        matches = [obj for obj in objects if obj['color'] == color]
        if len(matches) != 1 or matches[0]['clipped']:
            raise ValueError(f'{color}: necesita exact un candidat complet vizibil.')
        if not 1 <= row <= grid['rows'] or not 1 <= col <= grid['cols']:
            raise ValueError('Referinta in afara grilei.')
        source.append(matches[0]['center_px'])
        destination.append([col - 0.5, row - 0.5])
    # Reject degenerate/collinear point sets before solving.
    for points in (source, destination):
        array = np.array(points, dtype=np.float32)
        for a in range(4):
            triangle = np.delete(array, a, axis=0)
            if abs(cv2.contourArea(triangle)) < 1e-4:
                raise ValueError('Referinte coliniare; alege un dreptunghi.')
    matrix = cv2.getPerspectiveTransform(np.float32(source), np.float32(destination))
    if not np.isfinite(matrix).all() or abs(np.linalg.det(matrix)) < 1e-10:
        raise ValueError('Transformare degenerata.')
    return dict(matrix=matrix.tolist(), frame_size=[frame_shape[1], frame_shape[0]],
                corners_px=grid['corners_px'], independently_validated=False,
                references={color: list(cell) for color, cell in references.items()})


def inspect(frame, config, grid_name='source', geometry=None):
    grid = config['grids'][grid_name]
    objects = candidates(frame, config)
    cells = {f'{r},{c}': None for r in range(1, grid['rows'] + 1)
             for c in range(1, grid['cols'] + 1)}
    issues = []
    if geometry is None:
        issues.append('Face-plane mapping missing; cell occupancy is UNKNOWN.')
        return dict(objects=objects, proposed_cells=cells, issues=issues, ready_for_motion=False)
    if geometry['frame_size'] != [frame.shape[1], frame.shape[0]]:
        raise ValueError('Rezolutia difera fata de calibrare.')
    if geometry['corners_px'] != grid['corners_px']:
        raise ValueError('Colturile grilei au fost schimbate; recalibreaza planul fetelor.')
    if not geometry.get('independently_validated'):
        issues.append('Provisional geometry; requires a NEW independently labelled arrangement.')
    matrix = np.asarray(geometry['matrix'], dtype=np.float64)
    cells = dict.fromkeys(cells, 'empty')
    margin = config['vision']['detector']['cell_boundary_margin']
    for obj in objects:
        point = cv2.perspectiveTransform(np.float32([[obj['center_px']]]), matrix)[0, 0]
        x, y = map(float, point)
        obj['grid_xy'] = [x, y]
        if not math.isfinite(x + y) or not (0 <= x < grid['cols'] and 0 <= y < grid['rows']):
            issues.append(f"{obj['color']}: outside grid or invalid mapping")
            continue
        row, col = math.floor(y) + 1, math.floor(x) + 1
        key = f'{row},{col}'
        obj['proposed_cell'] = key
        if obj['clipped'] or min(x % 1, 1 - x % 1, y % 1, 1 - y % 1) < margin:
            issues.append(f"{obj['color']}: clipped face or close to cell boundary")
            cells[key] = 'unknown'
        elif cells[key] != 'empty':
            issues.append(f'{key}: multiple candidates')
            cells[key] = 'unknown'
        else:
            cells[key] = obj['color']
    # This first version cannot distinguish an unknown-colour cube from an empty
    # cell; never authorize robotic motion from these provisional observations.
    issues.append('Empty = no supported colour detected; unknown objects are not excluded.')
    return dict(objects=objects, proposed_cells=cells, issues=issues, ready_for_motion=False)


def overlay(frame, result, grid):
    display = frame.copy()
    if grid['corners_px'] is not None:
        cv2.polylines(display, [np.int32(grid['corners_px'])], True, (255, 0, 255), 2)
    for obj in result['objects']:
        x, y, width, height = obj['bbox_px']
        cv2.rectangle(display, (x, y), (x + width, y + height), (0, 255, 0), 2)
        text = obj['color'] + ' ' + obj.get('proposed_cell', '?')
        if obj['clipped']:
            text += ' CLIPPED'
        cv2.putText(display, text, (x, max(18, y - 5)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 0, 0), 3)
        cv2.putText(display, text, (x, max(18, y - 5)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (255, 255, 255), 1)
    return display
