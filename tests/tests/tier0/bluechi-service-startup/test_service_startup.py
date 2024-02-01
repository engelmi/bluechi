# SPDX-License-Identifier: LGPL-2.1-or-later

from typing import Dict

from bluechi_test.test import BluechiTest
from bluechi_test.machine import BlueChiControllerMachine, BlueChiAgentMachine
from bluechi_test.config import BluechiControllerConfig


def startup_verify(ctrl: BlueChiControllerMachine, _: Dict[str, BlueChiAgentMachine]):
    ctrl.wait_for_unit_state_to_be('bluechi-controller', 'active')


def test_controller_startup(bluechi_test: BluechiTest, bluechi_ctrl_default_config: BluechiControllerConfig):
    bluechi_test.set_bluechi_ctrl_machine_config(bluechi_ctrl_default_config)

    bluechi_test.run(startup_verify)
