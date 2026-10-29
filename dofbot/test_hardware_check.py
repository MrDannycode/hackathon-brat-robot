"""Safety checks that never open an I2C bus."""
import copy
import json
import unittest
from unittest.mock import patch

import hardware_check as hw


class FakeBus:
    def __init__(self):
        self.writes = []

    def write_i2c_block_data(self, address, register, payload):
        self.writes.append((address, register, payload))

    def write_byte_data(self, address, register, value):
        self.writes.append((address, register, value))


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(hw.DEFAULT_CONFIG.read_text())

    def test_protocol_endpoints_and_inversion(self):
        self.assertEqual(hw.encode_angle(self.config, 1, 0), 900)
        self.assertEqual(hw.encode_angle(self.config, 2, 0), 3100)
        self.assertEqual(hw.encode_angle(self.config, 5, 270), 3700)

    def test_empty_feedback_is_retried_then_validated(self):
        bus = FakeBus()
        # Raw 2000 -> SMBus low-byte-first representation.
        bus.read_word_data = unittest.mock.Mock(side_effect=[0, 0xd007])
        with patch.object(hw.time, 'sleep'):
            self.assertAlmostEqual(hw.read_angle(bus, self.config, 1), 90)
        self.assertEqual(bus.read_word_data.call_count, 2)
        self.assertEqual([entry[1] for entry in bus.writes], [0x31, 0x31])

    def test_persistent_empty_feedback_still_fails_without_motion(self):
        bus = FakeBus()
        bus.read_word_data = unittest.mock.Mock(return_value=0)
        with patch.object(hw.time, 'sleep'):
            with self.assertRaises(RuntimeError):
                hw.read_angle(bus, self.config, 1)
        self.assertEqual(bus.read_word_data.call_count, self.config['arm']['protocol']['read_attempts'])
        self.assertTrue(all(entry[1] == 0x31 for entry in bus.writes))

    def test_invalid_commands_never_write(self):
        bus = FakeBus()
        for servo, angle in ((0, 90), (7, 90), (1.0, 90), (True, 90), (1, -1), (1, 181), (5, 271), (1, float('nan'))):
            with self.assertRaises(ValueError):
                hw.write_angle(bus, self.config, servo, angle, 2000)
        self.assertEqual(bus.writes, [])

    def test_hold_sets_all_current_targets_before_enabling_torque(self):
        bus = FakeBus()
        with patch.object(hw, 'read_angle', return_value=90), patch.object(hw.time, 'sleep'):
            hw.initialize_hold(bus, self.config)
        self.assertEqual([entry[1] for entry in bus.writes], [0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x1a])
        self.assertEqual(bus.writes[-1], (0x15, 0x1a, 1))

    def test_hold_bad_feedback_never_writes_a_target_or_torque(self):
        bus = FakeBus()
        with patch.object(hw, 'read_angle', side_effect=[90, 90, RuntimeError('feedback invalid')]):
            with self.assertRaises(RuntimeError):
                hw.initialize_hold(bus, self.config)
        self.assertEqual(bus.writes, [])

    def test_hold_drift_prevents_activation(self):
        bus = FakeBus()
        with patch.object(hw, 'read_angle', side_effect=[90] * 6 + [95]):
            with self.assertRaises(RuntimeError):
                hw.initialize_hold(bus, self.config)
        self.assertEqual(bus.writes, [])

    def test_hold_write_failure_does_not_enable_torque(self):
        bus = FakeBus()
        with patch.object(hw, 'read_angle', return_value=90), patch.object(bus, 'write_i2c_block_data', side_effect=OSError('I2C failed')):
            with self.assertRaises(OSError):
                hw.initialize_hold(bus, self.config)
        self.assertEqual(bus.writes, [])

    def test_small_motion_cannot_pass_with_unchanged_feedback(self):
        bus = FakeBus()
        with patch.object(hw, 'read_angle', return_value=90), patch.object(hw.time, 'sleep'):
            with self.assertRaises(RuntimeError):
                hw.test_servo(bus, self.config)
        self.assertEqual(len(bus.writes), 2)
        self.assertTrue(all(write[1] == 0x11 for write in bus.writes))
        self.assertEqual(bus.writes[-1][2], hw.write_angle(None, self.config, 1, 90, 2000))

    def test_ctrl_c_restores_only_tested_servo(self):
        bus = FakeBus()
        with patch.object(hw, 'read_angle', return_value=90), patch.object(hw.time, 'sleep', side_effect=[KeyboardInterrupt, None]):
            with self.assertRaises(KeyboardInterrupt):
                hw.test_servo(bus, self.config)
        self.assertEqual([write[1] for write in bus.writes], [0x11, 0x11])

    def test_unsafe_test_rejected_before_motion(self):
        config = copy.deepcopy(self.config)
        config['servo_test']['delta_deg'] = 10
        bus = FakeBus()
        with self.assertRaises(ValueError):
            hw.test_servo(bus, config)
        self.assertEqual(bus.writes, [])


if __name__ == '__main__':
    unittest.main()
