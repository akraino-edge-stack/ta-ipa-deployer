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

from setuptools import setup, find_packages

VERSION = '0.1'
PROJECT = 'ironic_bmc_hardware_manager'

setup(
    name=PROJECT,
    version=VERSION,
    description='ironic_bmc_hardware_manager',
    author='Janne Suominen',
    author_email='janne.suominen@nokia.com',
    platforms=['Any'],
    scripts=[],
    provides=[],
    install_requires=['openstack-ironic-python-agent'],
    namespace_packages=[],
    packages=find_packages(),
    entry_points={
        'ironic_python_agent.hardware_managers': [
            'bmc = ironic_bmc_hardware_manager.bmc:BMCHardwareManager'
        ],
    },
    zip_safe=False,
)
