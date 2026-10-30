"""Feedback correction safety regressions; hardware is always mocked."""
import logging
import unittest
from unittest.mock import Mock, patch

from common.arm import Arm
from common.settings import load_config


def pose(s3, s1=90):
    return [s1, 90, s3, 90, 90, 90]


class S3CorrectionTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        self.arm = Arm(self.config, dry_run=True)
        self.arm.bus = Mock()

    def tearDown(self):
        self.arm.close()

    def run_move(self, samples, target=31.67):
        with patch.object(self.arm, 'read', side_effect=samples), \
                patch('common.arm.time.sleep'), patch('common.arm.write_angle') as write:
            try:
                self.arm._move({3: target})
            finally:
                self.commands = write.call_args_list

    def corrections(self):
        return [call for call in self.commands if call.args[4] >= 3000]

    def test_reaches_original_target_with_one_bounded_correction(self):
        self.run_move([pose(26.67), pose(30.27), pose(30.27), pose(31.58)])
        corrections = self.corrections()
        self.assertEqual(len(corrections), 1)
        self.assertEqual(corrections[0].args[2], 3)
        self.assertAlmostEqual(corrections[0].args[3], 33.07)
        self.assertEqual(self.config['motion']['feedback_tolerance_deg'], 1.0)

    def test_uncommanded_drift_prevents_correction(self):
        with self.assertRaises(RuntimeError):
            self.run_move([pose(26.67), pose(30.27, s1=94)])
        self.assertEqual(self.corrections(), [])

    def test_unstable_feedback_prevents_correction(self):
        with self.assertRaises(RuntimeError):
            self.run_move([pose(26.67), pose(30.27), pose(31.0)])
        self.assertEqual(self.corrections(), [])

    def test_large_error_prevents_correction(self):
        with self.assertRaises(RuntimeError):
            self.run_move([pose(26.67), pose(28.0)])
        self.assertEqual(self.corrections(), [])

    def test_overshoot_prevents_correction(self):
        with self.assertRaises(RuntimeError):
            self.run_move([pose(26.67), pose(33.0)])
        self.assertEqual(self.corrections(), [])

    def test_untested_target_range_prevents_correction(self):
        with self.assertRaises(RuntimeError):
            self.run_move([pose(36), pose(39.6)], target=41)
        self.assertEqual(self.corrections(), [])

    def test_failed_correction_stops_without_second_retry(self):
        with self.assertRaises(RuntimeError):
            self.run_move([pose(26.67), pose(30.27), pose(30.27), pose(30.27)])
        self.assertEqual(len(self.corrections()), 1)

    def test_angle_limits_apply_to_corrected_command(self):
        self.config['arm']['limits_deg'][2] = [0, 32]
        with self.assertRaises(ValueError):
            self.run_move([pose(26.67), pose(30.27), pose(30.27)])
        self.assertEqual(self.corrections(), [])

    def test_disabling_correction_preserves_stop_on_error(self):
        self.config['motion']['s3_correction']['enabled'] = False
        with self.assertRaises(RuntimeError):
            self.run_move([pose(26.67), pose(30.27)])
        self.assertEqual(self.corrections(), [])


if __name__ == '__main__':
    logging.basicConfig(level=logging.CRITICAL)
    unittest.main()
