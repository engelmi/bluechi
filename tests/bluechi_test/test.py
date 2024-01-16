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
from bluechi_test.config import BluechiControllerConfig, BluechiNodeConfig
from bluechi_test.container import BluechiNodeContainer, BluechiControllerContainer

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

        self.bluechi_controller_config: BluechiControllerConfig = None
        self.bluechi_node_configs: List[BluechiNodeConfig] = []

        self._test_init_time = datetime.datetime.now()

    def set_bluechi_controller_config(self, cfg: BluechiControllerConfig):
        self.bluechi_controller_config = cfg

    def add_bluechi_node_config(self, cfg: BluechiNodeConfig):
        self.bluechi_node_configs.append(cfg)

    def setup(self) -> Tuple[bool, Tuple[BluechiControllerContainer, Dict[str, BluechiNodeContainer]]]:
        if self.bluechi_controller_config is None:
            raise Exception("Bluechi Controller configuration not set")

        success = True
        ctrl_container: BluechiControllerContainer = None
        node_container: Dict[str, BluechiNodeContainer] = dict()
        try:
            LOGGER.debug(f"Starting container for bluechi-controller with config:\
                \n{self.bluechi_controller_config.serialize()}")

            ports = {self.bluechi_ctrl_svc_port: self.bluechi_ctrl_host_port}
            if self.additional_ports:
                ports.update(self.additional_ports)
            c = self.podman_client.containers.run(
                name=f"{self.bluechi_controller_config.name}-{self.tmt_test_serial_number}",
                image=self.bluechi_image_id,
                detach=True,
                ports=ports,
            )
            c.wait(condition="running")

            ctrl_container = BluechiControllerContainer(c, self.bluechi_controller_config)
            if self.run_with_valgrind:
                ctrl_container.enable_valgrind()
            if self.run_with_coverage:
                ctrl_container.exec_run('lcov -c -i -d /var/tmp/bluechi-coverage -o /var/tmp/base.info')

            ctrl_container.exec_run('systemctl start bluechi-controller')
            ctrl_container.wait_for_unit_state_to_be("bluechi-controller.service", "active")

            for cfg in self.bluechi_node_configs:
                LOGGER.debug(f"Starting container bluechi-node '{cfg.node_name}' with config:\n{cfg.serialize()}")

                c = self.podman_client.containers.run(
                    name=f"{cfg.node_name}-{self.tmt_test_serial_number}",
                    image=self.bluechi_image_id,
                    detach=True,
                )
                c.wait(condition="running")

                node = BluechiNodeContainer(c, cfg)
                node_container[cfg.node_name] = node

                if self.run_with_valgrind:
                    node.enable_valgrind()
                if self.run_with_coverage:
                    node.exec_run('lcov -c -i -d /var/tmp/bluechi-coverage -o /var/tmp/base.info')

                node.exec_run('systemctl start bluechi-agent')
                node.wait_for_unit_state_to_be("bluechi-agent.service", "active")

        except Exception as ex:
            success = False
            LOGGER.error(f"Failed to setup bluechi container: {ex}")
            traceback.print_exc()

        if self.run_with_valgrind:
            # Give some more time for bluechi to start and connect while running with valgrind
            time.sleep(2)

        return (success, (ctrl_container, node_container))

    def gather_logs(self, ctrl: BluechiControllerContainer, nodes: Dict[str, BluechiNodeContainer]):
        LOGGER.debug("Collecting logs from all containers...")

        if ctrl is not None:
            ctrl.gather_journal_logs(self.tmt_test_data_dir)
            if self.run_with_valgrind:
                ctrl.gather_valgrind_logs(self.tmt_test_data_dir)

        for _, node in nodes.items():
            node.gather_journal_logs(self.tmt_test_data_dir)
            if self.run_with_valgrind:
                node.gather_valgrind_logs(self.tmt_test_data_dir)

        self.gather_test_executor_logs()

    def gather_coverage(self, ctrl: BluechiControllerContainer, nodes: Dict[str, BluechiNodeContainer]):
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

    def shutdown_bluechi(self, ctrl: BluechiControllerContainer, nodes: Dict[str, BluechiNodeContainer]):
        LOGGER.debug("Stopping all BlueChi components in all container...")

        for _, node in nodes.items():
            node.exec_run("systemctl stop bluechi-agent")

        if ctrl is not None:
            ctrl.exec_run("systemctl stop bluechi-agent")
            ctrl.exec_run("systemctl stop bluechi-controller")

    def teardown(self, ctrl: BluechiControllerContainer, nodes: Dict[str, BluechiNodeContainer]):
        LOGGER.debug("Stopping and removing all container...")

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

    def run(self, exec: Callable[[BluechiControllerContainer, Dict[str, BluechiNodeContainer]], None]):
        LOGGER.info("Test execution started")
        successful, container = self.setup()
        ctrl_container, node_container = container

        if not successful:
            self.teardown(ctrl_container, node_container)
            traceback.print_exc()
            raise Exception("Failed to setup bluechi test")

        test_result = None
        try:
            exec(ctrl_container, node_container)
        except Exception as ex:
            test_result = ex
            LOGGER.error(f"Failed to execute test: {ex}")
            traceback.print_exc()

        try:
            self.shutdown_bluechi(ctrl_container, node_container)
        except Exception as ex:
            LOGGER.error(f"Failed to shutdown BlueChi components: {ex}")
            traceback.print_exc()

        try:
            self.gather_logs(ctrl_container, node_container)
            if self.run_with_valgrind:
                self.check_valgrind_logs()
            if self.run_with_coverage:
                self.gather_coverage(ctrl_container, node_container)
        except Exception as ex:
            LOGGER.error(f"Failed to collect logs: {ex}")
            traceback.print_exc()

        self.teardown(ctrl_container, node_container)

        LOGGER.info("Test execution finished")
        if test_result is not None:
            raise test_result
