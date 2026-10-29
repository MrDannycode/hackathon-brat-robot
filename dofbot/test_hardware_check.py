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


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(hw.DEFAULT_CONFIG.read_text())

    def test_protocol_endpoints_and_inversion(self):
        self.assertEqual(hw.encode_angle(self.config, 1, 0), 900)
        self.assertEqual(hw.encode_angle(self.config, 2, 0), 3100)
        self.assertEqual(hw.encode_angle(self.config, 5, 270), 3700)

    def test_invalid_commands_never_write(self):
        bus = FakeBus()
        for servo, angle in ((0, 90), (7, 90), (1, -1), (1, 181), (5, 271), (1, float('nan'))):
            with self.assertRaises(ValueError):
                hw.write_angle(bus, self.config, servo, angle, 2000)
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
