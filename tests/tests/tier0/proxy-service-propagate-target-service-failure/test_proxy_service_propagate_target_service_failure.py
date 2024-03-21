# SPDX-License-Identifier: LGPL-2.1-or-later

import logging

from typing import Dict
from bluechi_test.test import BluechiTest
from bluechi_test.machine import BluechiControllerMachine, BluechiAgentMachine
from bluechi_test.config import BluechiControllerConfig, BluechiAgentConfig
from bluechi_test.service import Option, Section, SimpleRemainingService

LOGGER = logging.getLogger(__name__)

NODE_FOO = "node-foo"
NODE_BAR = "node-bar"


def exec(_: BluechiControllerMachine, nodes: Dict[str, BluechiAgentMachine]):

    node_foo = nodes[NODE_FOO]
    node_bar = nodes[NODE_BAR]

    service = SimpleRemainingService("target.service")
    service.set_option(Section.Service, Option.ExecStart, "/bin/false")

    node_bar.install_systemd_service(service)

    service = SimpleRemainingService("requesting.service")
    service.set_option(Section.Unit, Option.BindsTo, "bluechi-proxy@node-bar_target.service")
    service.set_option(Section.Unit, Option.After, "bluechi-proxy@node-bar_target.service")
    service.set_option(Section.Service, Option.ExecStart, "/bin/true")
    service.set_option(Section.Service, Option.RemainAfterExit, "yes")

    node_foo.install_systemd_service(service)

    assert node_foo.systemctl.start_unit("requesting.service")
    assert node_foo.wait_for_unit_state_to_be("requesting.service", "inactive")
    assert node_bar.wait_for_unit_state_to_be("target.service", "failed")


def test_proxy_service_propagate_target_service_failure(
        bluechi_test: BluechiTest,
        bluechi_node_default_config: BluechiAgentConfig, bluechi_ctrl_default_config: BluechiControllerConfig):
    node_foo_cfg = bluechi_node_default_config.deep_copy()
    node_foo_cfg.node_name = NODE_FOO

    node_bar_cfg = bluechi_node_default_config.deep_copy()
    node_bar_cfg.node_name = NODE_BAR

    bluechi_test.add_bluechi_agent_config(node_foo_cfg)
    bluechi_test.add_bluechi_agent_config(node_bar_cfg)

    bluechi_ctrl_default_config.allowed_node_names = [NODE_FOO, NODE_BAR]
    bluechi_test.set_bluechi_controller_config(bluechi_ctrl_default_config)

    bluechi_test.run(exec)
