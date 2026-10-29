"""USB/CSI capture, explicit camera controls, flushing, and saved real frames."""
from __future__ import annotations

import logging
from pathlib import Path
import re
import subprocess
import time

LOG = logging.getLogger(__name__)


def detect_camera(settings):
    device = Path(settings['device'])
    if device.exists():
        result = subprocess.run(['v4l2-ctl', '-d', str(device), '--info'],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and 'uvcvideo' in result.stdout:
            return 'usb', str(device)
    try:
        from picamera2 import Picamera2
        if Picamera2.global_camera_info():
            return 'csi', settings['csi_index']
    except ImportError:
        pass
    raise RuntimeError('Nu exista camera USB UVC la device-ul configurat si nu exista camera CSI detectata.')


class Camera:
    def __init__(self, config):
        import cv2
        self.settings = config['camera']
        self.cap = None
        self.picam = None
        self.control_report = {'applied': {}, 'missing': []}
        backend = self.settings['backend']
        if backend == 'auto':
            backend, device = detect_camera(self.settings)
        else:
            device = self.settings['device'] if backend == 'usb' else self.settings['csi_index']
        self.backend = backend
        try:
            if backend == 'usb':
                self._usb_controls(device)
                self.cap = cv2.VideoCapture(str(device), cv2.CAP_V4L2)
                if not self.cap.isOpened():
                    raise RuntimeError(f'Nu pot deschide camera USB {device}.')
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings['width'])
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings['height'])
                self.cap.set(cv2.CAP_PROP_FPS, self.settings['fps'])
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.settings['buffer_size'])
            elif backend == 'csi':
                from picamera2 import Picamera2
                self.picam = Picamera2(device)
                capture = self.picam.create_video_configuration(main={
                    'size': (self.settings['width'], self.settings['height']), 'format': 'RGB888'})
                self.picam.configure(capture)
                # Picamera2 RGB888 is BGR byte order in the captured numpy array.
                self.picam.set_controls(self.settings['csi_controls'])
                self.picam.start()
            else:
                raise ValueError('Backend camera trebuie sa fie auto, usb sau csi.')
            time.sleep(self.settings['warmup_s'])
            self.read()
        except BaseException:
            self.close()
            raise

    def _usb_controls(self, device):
        listed = subprocess.run(['v4l2-ctl', '-d', str(device), '--list-ctrls'],
                                capture_output=True, text=True, timeout=10)
        if listed.returncode:
            raise RuntimeError('Nu pot interoga controalele V4L2: ' + listed.stderr)
        available = set(re.findall(r'^\s*(\w+)\s+0x', listed.stdout, flags=re.MULTILINE))
        desired = dict(self.settings['usb_controls'])
        desired.update(self.settings['usb_fixed_controls'])
        missing = [name for name in desired if name not in available]
        self.control_report['missing'] = missing
        if missing and self.settings['require_fixed_controls']:
            raise RuntimeError(f'Controale manuale indisponibile: {missing}.')
        if missing:
            LOG.warning('Camera nu expune %s; expunerea/balansul fixe NU sunt confirmate.', missing)
        for name, value in desired.items():
            if name not in available:
                continue
            result = subprocess.run(['v4l2-ctl', '-d', str(device), f'--set-ctrl={name}={value}'],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode:
                raise RuntimeError(f'Nu pot seta {name}: {result.stderr}')
            actual = subprocess.run(['v4l2-ctl', '-d', str(device), f'--get-ctrl={name}'],
                                    capture_output=True, text=True, timeout=10)
            if actual.returncode or actual.stdout.strip().split(':')[-1].strip() != str(value):
                raise RuntimeError(f'Camera nu confirma controlul {name}={value}.')
            self.control_report['applied'][name] = value

    def read(self, *, flush=True):
        if self.cap is not None:
            if flush:
                for _ in range(self.settings['flush_frames']):
                    if not self.cap.grab():
                        raise RuntimeError('Nu pot goli bufferul camerei.')
            ok, frame = self.cap.read()
            if not ok:
                raise RuntimeError('Captura USB esuata.')
        elif self.picam is not None:
            for _ in range(self.settings['flush_frames'] if flush else 0):
                self.picam.capture_array()
            frame = self.picam.capture_array()
        else:
            raise RuntimeError('Camera este inchisa.')
        if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
            raise RuntimeError('Cadru invalid; astept imagine BGR cu 3 canale.')
        return frame

    def save(self, path):
        import cv2
        frame = self.read()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(path), frame):
            raise RuntimeError('Nu pot salva imaginea: ' + str(path))
        return frame

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self.picam is not None:
            try:
                self.picam.stop()
            finally:
                self.picam.close()
                self.picam = None
