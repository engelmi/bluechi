# SPDX-License-Identifier: LGPL-2.1-or-later

import os
from typing import Dict

from bluechi_test.config import BluechiControllerConfig, BlueChiAgentConfig
from bluechi_test.machine import BlueChiControllerMachine, BlueChiAgentMachine
from bluechi_test.test import BluechiTest


node_foo_name = "node-foo"
simple_service = "simple.service"


def exec(ctrl: BlueChiControllerMachine, nodes: Dict[str, BlueChiAgentMachine]):
    foo = nodes[node_foo_name]

    source_dir = "systemd"
    target_dir = os.path.join("/", "etc", "systemd", "system")
    foo.copy_systemd_service(simple_service, source_dir, target_dir)
    assert foo.wait_for_unit_state_to_be(simple_service, "inactive")

    result, output = ctrl.run_python(os.path.join("python", "start_unit_job_metrics.py"))
    if result != 0:
        raise Exception(output)


def test_metrics_start_unit(
        bluechi_test: BluechiTest,
        bluechi_ctrl_default_config: BluechiControllerConfig,
        bluechi_node_default_config: BlueChiAgentConfig):

    node_foo_cfg = bluechi_node_default_config.deep_copy()
    node_foo_cfg.node_name = node_foo_name

    bluechi_ctrl_default_config.allowed_node_names = [node_foo_name]

    bluechi_test.set_bluechi_ctrl_machine_config(bluechi_ctrl_default_config)
    bluechi_test.add_bluechi_agent_machine_configs(node_foo_cfg)

    bluechi_test.run(exec)
