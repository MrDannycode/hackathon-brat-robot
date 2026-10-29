"""Behavior and safety checks with simulated arms; never opens real hardware."""
import copy
import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import calibrate
from common.arm import Arm
from common.settings import DEFAULT_CONFIG, load_config, save_config


def setUpModule():
    logging.disable(logging.CRITICAL)


def tearDownModule():
    logging.disable(logging.NOTSET)


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(DEFAULT_CONFIG)
        self.arm = Arm(self.config, dry_run=True)

    def tearDown(self):
        self.arm.close()

    def calibrated(self):
        self.config['poses']['home'] = [90] * 5
        self.config['poses']['transit'] = [92] * 5
        self.config['gripper']['open_deg'] = 45
        self.config['gripper']['closed_deg'] = 135
        self.config['cells']['source']['1,1'] = {'approach': [94] * 5, 'contact': [96] * 5}
        self.config['cells']['destination']['1,1'] = {'approach': [88] * 5, 'contact': [86] * 5}

    def test_missing_station_rejected_before_motion(self):
        before = self.arm.read()
        with self.assertRaises(ValueError):
            self.arm.pick(self.config['cells']['source']['1,1'])
        self.assertEqual(self.arm.read(), before)

    def test_missing_home_does_not_command_transit_first(self):
        self.config['poses']['transit'] = [92] * 5
        with patch.object(self.arm, 'move_pose') as move:
            with self.assertRaises(ValueError):
                self.arm.home()
            move.assert_not_called()

    def test_manual_large_step_rejected(self):
        with self.assertRaises(ValueError):
            self.arm.move_servo(1, 110, manual=True)
        self.assertEqual(self.arm.read()[0], 90)

    def test_simulated_pick_place_finishes_above_grid_with_open_gripper(self):
        self.calibrated()
        self.arm.pick(self.config['cells']['source']['1,1'])
        self.assertEqual(self.arm.read()[5], 135)
        self.arm.place(self.config['cells']['destination']['1,1'])
        self.assertEqual(self.arm.read(), [92] * 5 + [45])

    def test_bad_destination_prevents_pick(self):
        self.calibrated()
        self.config['safety']['recovery_enabled'] = True
        self.config['cells']['destination']['1,1']['contact'] = None
        with patch.object(self.arm, 'pick') as pick:
            with self.assertRaises(ValueError):
                calibrate.command(['test', '1,1', '1,1'], self.arm, self.config, Path('unused'))
            pick.assert_not_called()

    def test_uncommanded_joint_drift_stops_move(self):
        self.arm.bus = Mock()
        with patch.object(self.arm, 'read', side_effect=[[90] * 6, [92, 95, 90, 90, 90, 90]]), \
             patch('common.arm.time.sleep'), patch('common.arm.write_angle') as write:
            with self.assertRaises(RuntimeError):
                self.arm._move({1: 92})
            self.assertEqual({entry.args[2] for entry in write.call_args_list}, {1})

    def test_uncalibrated_recovery_does_not_move(self):
        with patch.object(self.arm, 'move_pose') as move:
            self.assertFalse(self.arm.safe_shutdown())
            move.assert_not_called()

    def test_real_hardware_refuses_simulated_configuration(self):
        self.config['calibration']['simulated'] = True
        with self.assertRaises(ValueError):
            Arm(self.config, dry_run=False)

    def test_dry_run_calibration_never_overwrites_real_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            save_config(path, self.config)
            original = path.read_bytes()
            with patch('sys.argv', ['calibrate.py', '--config', str(path), '--dry-run']), \
                 patch('calibrate.logging.basicConfig'), patch('builtins.print'), \
                 patch('builtins.input', side_effect=['save home', 'exit']):
                self.assertEqual(calibrate.main(), 0)
            self.assertEqual(path.read_bytes(), original)
            saved = load_config(path.with_name('config.dry-run.json'))
            self.assertTrue(saved['calibration']['simulated'])
            self.assertEqual(saved['poses']['home'], [90] * 5)

    def test_atomic_save_preserves_previous_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            save_config(path, {'version': 1})
            save_config(path, {'version': 2})
            self.assertEqual(load_config(path), {'version': 2})
            self.assertEqual(load_config(path.with_suffix('.json.bak')), {'version': 1})
            with self.assertRaises(ValueError):
                save_config(path, {'angle': float('nan')})
            self.assertEqual(load_config(path), {'version': 2})


if __name__ == '__main__':
    unittest.main()
