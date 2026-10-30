"""Safety and sequencing for the local transfer; no hardware access."""
import unittest
from unittest.mock import Mock

from common.arm import Arm
from common.settings import load_config
from transfer_direct import transfer


class DirectTransferTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        self.config['poses']['home'] = [90] * 5
        self.config['poses']['transit'] = [90] * 5
        self.config['gripper'].update(open_deg=98, closed_deg=110)
        self.source = {'approach': [80, 47, 46, 55, 87], 'contact': [80, 33, 46, 55, 87]}
        self.target = {'approach': [80, 47, 42, 35, 87], 'contact': [80, 44, 42, 35, 87]}
        self.arm = Arm(self.config, dry_run=True)
        self.arm.current = self.source['approach'][:] + [98]
        self.arm._move = Mock(wraps=self.arm._move)

    def tearDown(self):
        self.arm.close()

    def test_direct_transfer_uses_local_poses_and_finishes_open_at_target(self):
        transfer(self.arm, self.config, self.source, self.target)
        self.assertEqual(self.arm.read(), self.target['approach'] + [98])
        targets = [call.args[0] for call in self.arm._move.call_args_list]
        self.assertIn({6: 110}, targets)
        self.assertLess(targets.index({6: 110}), targets.index({6: 98}))
        self.assertNotIn(dict(enumerate([90] * 5, 1)), targets)

    def test_arbitrary_start_is_rejected_before_motion(self):
        self.arm.current = [90] * 6
        self.arm.current[5] = 98
        with self.assertRaises(ValueError):
            transfer(self.arm, self.config, self.source, self.target)
        self.arm._move.assert_not_called()

    def test_closed_start_is_rejected_before_motion(self):
        self.arm.current[5] = 110
        with self.assertRaises(ValueError):
            transfer(self.arm, self.config, self.source, self.target)
        self.arm._move.assert_not_called()

    def test_missing_destination_is_rejected_before_pick(self):
        self.target['contact'] = None
        with self.assertRaises(ValueError):
            transfer(self.arm, self.config, self.source, self.target)
        self.arm._move.assert_not_called()

    def test_destination_contact_start_retracts_locally_first(self):
        self.arm.current = self.target['contact'][:] + [98]
        transfer(self.arm, self.config, self.source, self.target)
        first = self.arm._move.call_args_list[0].args[0]
        self.assertEqual(first, dict(enumerate(self.target['approach'], 1)))

    def test_coincident_contacts_rejected(self):
        self.target['contact'] = self.source['contact'][:]
        with self.assertRaises(ValueError):
            transfer(self.arm, self.config, self.source, self.target)
        self.arm._move.assert_not_called()


if __name__ == '__main__':
    unittest.main()
