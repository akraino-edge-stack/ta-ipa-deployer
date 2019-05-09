# Copyright 2019 Nokia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os

from ironic_python_agent import hardware
from ironic_python_agent import utils

from oslo_log import log
from oslo_concurrency import processutils


LOG = log.getLogger()


class BMCHardwareManager(hardware.GenericHardwareManager):
    HARDWARE_MANAGER_NAME = 'BMCHardwareManager'
    HARDWARE_MANAGER_VERSION = '1'

    def evaluate_hardware_support(self):
        """Declare level of hardware support provided."""

        LOG.info('Running in BMC environment')
        return hardware.HardwareSupport.SERVICE_PROVIDER

    def list_network_interfaces(self):
        network_interfaces_list = []

        bmc_mac = self.get_ipmi_info().get('MAC Address', False)
        if bmc_mac:
            LOG.info("Adding MAC address net interfaces %s", bmc_mac)
            bmc_address = self.get_bmc_address()
            network_interfaces_list.append(hardware.NetworkInterface(
                name="BMC_INTERFACE",
                mac_addr=bmc_mac,
                ipv4_address=bmc_address,
                has_carrier=True,
                vendor="BMC",
                product="Akraino"))

        else:
            network_interfaces_list = super(BMCHardwareManager, self).list_network_interfaces()
        return network_interfaces_list

    def get_ipmi_info(self):
        # These modules are rarely loaded automatically
        utils.try_execute('modprobe', 'ipmi_msghandler')
        utils.try_execute('modprobe', 'ipmi_devintf')
        utils.try_execute('modprobe', 'ipmi_si')

        try:
            out, _e = utils.execute(
                "ipmitool lan print", shell=True, attempts=2)
        except (processutils.ProcessExecutionError, OSError) as e:
            # Not error, because it's normal in virtual environment
            LOG.warning("Cannot get BMC info: %s", e)
            return {}

        info = {}
        for line in out.split('\n'):
            spl = line.find(':')
            if spl == -1:
                continue
            else:
                key = line[0:spl].strip()
                if key == '':
                    continue
                info[line[0:spl].strip()] = line[spl+1:].strip()
        return info

