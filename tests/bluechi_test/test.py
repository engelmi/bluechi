# SPDX-License-Identifier: LGPL-2.1-or-later

import datetime
import logging
import os
import re
import time
import traceback

from podman import PodmanClient
from typing import List, Dict, Callable, Tuple

from bluechi_test.command import Command
from bluechi_test.config import BluechiControllerConfig, BlueChiAgentConfig
from bluechi_test.machine import BlueChiAgentMachine, BlueChiControllerMachine
from bluechi_test.client import ContainerClient

LOGGER = logging.getLogger(__name__)


class BluechiTest():

    def __init__(
            self,
            podman_client: PodmanClient,
            bluechi_image_id: str,
            bluechi_ctrl_host_port: str,
            bluechi_ctrl_svc_port: str,
            tmt_test_serial_number: str,
            tmt_test_data_dir: str,
            run_with_valgrind: bool,
            run_with_coverage: bool,
            additional_ports: dict) -> None:

        self.podman_client = podman_client
        self.bluechi_image_id = bluechi_image_id
        self.bluechi_ctrl_host_port = bluechi_ctrl_host_port
        self.bluechi_ctrl_svc_port = bluechi_ctrl_svc_port
        self.tmt_test_serial_number = tmt_test_serial_number
        self.tmt_test_data_dir = tmt_test_data_dir
        self.run_with_valgrind = run_with_valgrind
        self.run_with_coverage = run_with_coverage
        self.additional_ports = additional_ports

        self.bluechi_ctrl_machine_config: Tuple[BluechiControllerConfig, BlueChiAgentConfig] = None
        self.bluechi_agent_machine_configs: List[BlueChiAgentConfig] = []

        self._test_init_time = datetime.datetime.now()

    def set_bluechi_ctrl_machine_config(self, ctrl_cfg: BluechiControllerConfig, agent_cfg: BlueChiAgentConfig = None):
        self.bluechi_ctrl_machine_config = [ctrl_cfg, agent_cfg]

    def add_bluechi_agent_machine_configs(self, cfg: BlueChiAgentConfig):
        self.bluechi_agent_machine_configs.append(cfg)

    def setup(self) -> Tuple[bool, Tuple[BlueChiControllerMachine, Dict[str, BlueChiAgentMachine]]]:
        if self.bluechi_ctrl_machine_config is None or self.bluechi_ctrl_machine_config[0] is None:
            raise Exception("Bluechi Controller configuration not set")

        success = True
        ctrl_machine: BlueChiControllerMachine = None
        agent_machines: Dict[str, BlueChiAgentMachine] = dict()

        try:
            LOGGER.debug(f"Starting bluechi-controller with config:\
                \n{self.bluechi_ctrl_machine_config[0].serialize()}")

            name = f"{self.bluechi_ctrl_machine_config[0].name}-{self.tmt_test_serial_number}"
            ports = {self.bluechi_ctrl_svc_port: self.bluechi_ctrl_host_port}
            if self.additional_ports:
                ports.update(self.additional_ports)

            ctrl_machine = BlueChiControllerMachine(name,
                                                    ContainerClient(self.podman_client, self.bluechi_image_id, name, ports),
                                                    self.bluechi_ctrl_machine_config[0],
                                                    self.bluechi_ctrl_machine_config[1])
            if self.run_with_valgrind:
                ctrl_machine.enable_valgrind()
            ctrl_machine.systemctl.start_unit("bluechi-controller.service")
            ctrl_machine.wait_for_unit_state_to_be("bluechi-controller.service", "active")
            if self.bluechi_ctrl_machine_config[1] is not None:
                ctrl_machine.systemctl.start_unit("bluechi-agent.service")
                ctrl_machine.wait_for_unit_state_to_be("bluechi-agent.service", "active")

            for cfg in self.bluechi_agent_machine_configs:
                LOGGER.debug(f"Starting bluechi-agent '{cfg.node_name}' with config:\n{cfg.serialize()}")

                name = f"{cfg.node_name}-{self.tmt_test_serial_number}"
                agent_machine = BlueChiAgentMachine(name,
                                                    ContainerClient(self.podman_client, self.bluechi_image_id, name, {}), cfg)

                agent_machines[cfg.node_name] = agent_machine

                if self.run_with_valgrind:
                    agent_machine.enable_valgrind()

                agent_machine.systemctl.start_unit("bluechi-agent.service")
                agent_machine.wait_for_unit_state_to_be("bluechi-agent.service", "active")

        except Exception as ex:
            success = False
            LOGGER.error(f"Failed to setup bluechi machines: {ex}")
            traceback.print_exc()

        if self.run_with_valgrind:
            # Give some more time for bluechi to start and connect while running with valgrind
            time.sleep(2)

        return (success, (ctrl_machine, agent_machines))

    def gather_logs(self, ctrl: BlueChiControllerMachine, nodes: Dict[str, BlueChiAgentMachine]):
        LOGGER.debug("Collecting logs from all machines...")

        if ctrl is not None:
            ctrl.gather_journal_logs(self.tmt_test_data_dir)
            if self.run_with_valgrind:
                ctrl.gather_valgrind_logs(self.tmt_test_data_dir)

        for _, node in nodes.items():
            node.gather_journal_logs(self.tmt_test_data_dir)
            if self.run_with_valgrind:
                node.gather_valgrind_logs(self.tmt_test_data_dir)

        self.gather_test_executor_logs()

    def gather_coverage(self, ctrl: BlueChiControllerMachine, nodes: Dict[str, BlueChiAgentMachine]):
        LOGGER.info("Collecting code coverage started")

        data_coverage_dir = f"{self.tmt_test_data_dir}/bluechi-coverage/"

        os.mkdir(f"{self.tmt_test_data_dir}/bluechi-coverage")

        if ctrl is not None:
            ctrl.gather_coverage(data_coverage_dir)

        for _, node in nodes.items():
            node.gather_coverage(data_coverage_dir)

        LOGGER.info("Collecting code coverage finished")

    def gather_test_executor_logs(self) -> None:
        LOGGER.debug("Collecting logs from test executor...")
        log_file = f"{self.tmt_test_data_dir}/journal-test_executor.log"
        try:
            logs_since = self._test_init_time.strftime("%Y-%m-%d %H:%M:%S")
            Command(f'journalctl --no-pager --since "{logs_since}" > {log_file}').run()
        except Exception as ex:
            LOGGER.error(f"Failed to gather test executor journal: {ex}")

    def shutdown_bluechi(self, ctrl: BlueChiControllerMachine, nodes: Dict[str, BlueChiAgentMachine]):
        LOGGER.debug("Stopping all BlueChi components in all machines...")

        for _, node in nodes.items():
            node.systemctl.stop_unit("bluechi-agent.service")

        if ctrl is not None:
            ctrl.systemctl.stop_unit("bluechi-agent.service")
            ctrl.systemctl.stop_unit("bluechi-controller.service")

    def teardown(self, ctrl: BlueChiControllerMachine, nodes: Dict[str, BlueChiAgentMachine]):
        LOGGER.debug("Cleaning up all machines...")

        if ctrl is not None:
            ctrl.cleanup()

        for _, node in nodes.items():
            node.cleanup()

    def check_valgrind_logs(self) -> None:
        LOGGER.debug("Checking valgrind logs...")
        errors_found = False
        for filename in os.listdir(self.tmt_test_data_dir):
            if re.match(r'.+-valgrind-.+\.log', filename):
                with open(os.path.join(self.tmt_test_data_dir, filename), 'r') as file:
                    summary_found = False
                    for line in file.readlines():
                        if 'ERROR SUMMARY' in line:
                            summary_found = True
                            errors = re.findall(r'ERROR SUMMARY: (\d+) errors', line)
                            if errors[0] != "0":
                                LOGGER.error(f"Valgrind errors found in {filename}")
                                errors_found = True
                    if not summary_found:
                        raise Exception(f"Valgrind log {filename} does not contain summary, log was not finalized")
        if errors_found:
            raise Exception(f"Memory errors found in test. Review valgrind logs in {self.tmt_test_data_dir}")

    def run(self, exec: Callable[[BlueChiControllerMachine, Dict[str, BlueChiAgentMachine]], None]):
        LOGGER.info("Test execution started")
        successful, machines = self.setup()
        ctrl_machine, agent_machines = machines

        if not successful:
            self.teardown(ctrl_machine, agent_machines)
            traceback.print_exc()
            raise Exception("Failed to setup bluechi test")

        test_result = None
        try:
            exec(ctrl_machine, agent_machines)
        except Exception as ex:
            test_result = ex
            LOGGER.error(f"Failed to execute test: {ex}")
            traceback.print_exc()

        try:
            self.shutdown_bluechi(ctrl_machine, agent_machines)
        except Exception as ex:
            LOGGER.error(f"Failed to shutdown BlueChi components: {ex}")
            traceback.print_exc()

        try:
            self.gather_logs(ctrl_machine, agent_machines)
            if self.run_with_valgrind:
                self.check_valgrind_logs()
            if self.run_with_coverage:
                self.gather_coverage(ctrl_machine, agent_machines)
        except Exception as ex:
            LOGGER.error(f"Failed to collect logs: {ex}")
            traceback.print_exc()

        self.teardown(ctrl_machine, agent_machines)

        LOGGER.info("Test execution finished")
        if test_result is not None:
            raise test_result
