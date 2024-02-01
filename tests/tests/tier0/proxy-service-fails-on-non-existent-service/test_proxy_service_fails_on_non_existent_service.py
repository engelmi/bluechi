# SPDX-License-Identifier: LGPL-2.1-or-later

import os
from typing import Dict

from bluechi_test.config import BluechiControllerConfig, BlueChiAgentConfig
from bluechi_test.machine import BlueChiControllerMachine, BlueChiAgentMachine
from bluechi_test.test import BluechiTest
from bluechi_test.util import assemble_bluechi_proxy_service_name


node_foo_name = "node-foo"
node_bar_name = "node-bar"

requesting_service = "requesting.service"
simple_service = "simple.service"


def verify_proxy_start_failed(foo: BlueChiAgentMachine):
    assert foo.wait_for_unit_state_to_be(requesting_service, "active")
    bluechi_proxy_service = assemble_bluechi_proxy_service_name(node_bar_name, simple_service)
    assert foo.wait_for_unit_state_to_be(bluechi_proxy_service, "failed")


def exec(ctrl: BlueChiControllerMachine, nodes: Dict[str, BlueChiAgentMachine]):
    foo = nodes[node_foo_name]

    source_dir = os.path.join(".", "systemd")
    target_dir = os.path.join("/", "etc", "systemd", "system")

    foo.copy_systemd_service(requesting_service, source_dir, target_dir)
    assert foo.wait_for_unit_state_to_be(requesting_service, "inactive")

    ctrl.bluechictl.start_unit(node_foo_name, requesting_service)
    verify_proxy_start_failed(foo)


def test_proxy_service_fails_on_non_existent_service(
        bluechi_test: BluechiTest,
        bluechi_ctrl_default_config: BluechiControllerConfig,
        bluechi_node_default_config: BlueChiAgentConfig):

    node_foo_cfg = bluechi_node_default_config.deep_copy()
    node_foo_cfg.node_name = node_foo_name

    node_bar_cfg = bluechi_node_default_config.deep_copy()
    node_bar_cfg.node_name = node_bar_name

    bluechi_ctrl_default_config.allowed_node_names = [node_foo_name, node_bar_name]

    bluechi_test.set_bluechi_ctrl_machine_config(bluechi_ctrl_default_config)
    bluechi_test.add_bluechi_agent_machine_configs(node_foo_cfg)
    bluechi_test.add_bluechi_agent_machine_configs(node_bar_cfg)

    bluechi_test.run(exec)
