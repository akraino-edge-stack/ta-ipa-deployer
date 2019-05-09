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


import tarfile
import sys
import os
import errno
import stat
import time
import tempfile
import shutil

import json
import logging
import subprocess

from oslo_config import cfg
from oslo_log import log
from ironic_python_agent import utils
from ironic_lib import utils as ironic_utils
from ironic_python_agent import errors
from oslo_concurrency import processutils

CONF = cfg.CONF
LOG = log.getLogger(__name__)
dhclient_physIfaces = []

def dhclient_path():
    if os.path.exists("/usr/sbin/dhclient"):
        return "/usr/sbin/dhclient"
    elif os.path.exists("/sbin/dhclient"):
        return "/sbin/dhclient"
    else:
        raise RuntimeError("Could not find dhclient")

def stop_dhclient_process(interface):
    """Stop a DHCP process before running os-net-config.

    :param interface: The interface on which to stop dhclient.
    """
    pid_file = '/var/run/dhclient-%s.pid' % (interface)
    try:
        dhclient = dhclient_path()
    except RuntimeError as err:
        LOG.info('Exception when stopping dhclient: %s' % err)
        return

    if os.path.exists(pid_file):
        LOG.info('Stopping %s on interface %s' % (dhclient, interface))
        utils.execute(dhclient, '-r', '-pf', pid_file, interface)
        try:
            os.unlink(pid_file)
        except OSError as err:
            LOG.error('Could not remove dhclient pid file \'%s\': %s' %
                         (pid_file, err))

def _poll_interface(_ifacedata):
    ifacedata = json.loads(_ifacedata)
    global dhclient_physIfaces
    
    physIfaces = []
    if "network_config" in ifacedata:
        for netconfdata in ifacedata["network_config"]:
            if "device" in netconfdata:
                if "bond" not in netconfdata["device"]:
                    # Is (physical) interface
                    LOG.debug('Physical device %s' % netconfdata["device"])
                    physIfaces.append(netconfdata["device"])

            elif "members" in netconfdata:
                # logical interface with member (f.ex bond)
                for _member in netconfdata["members"]:
                    if "type" in _member:
                        if _member["type"] == 'interface':
                            if "name" in _member:
                                LOG.debug('Physical device %s' % _member["name"])
                                physIfaces.append(_member["name"])
            elif "name" in netconfdata:
                if "type" in netconfdata and netconfdata["type"] == 'interface':
                    LOG.debug('Physical device %s' % netconfdata["name"])
                    physIfaces.append(netconfdata["name"])

    LOG.info('Checking for physical device(s) "%s"' % ', '.join(physIfaces))
    dhclient_physIfaces = list(physIfaces)
    wait_secs = 5
    max_wait_secs = 60

    while len(physIfaces) > 0 and max_wait_secs >= 0:
        missing_devices = []
        max_wait_secs = max_wait_secs - wait_secs

        for _device in physIfaces:
            devicepath = "/sys/class/net/%s/device" % _device
            LOG.debug('Check path "%s"' % devicepath )
            if os.path.exists(devicepath):
                LOG.debug('Device "%s" in known by kernel' % _device)
                physIfaces.remove(_device)
            else:
                LOG.debug('Device "%s" in not (yet) known by kernel' % _device)
		missing_devices.append(_device)

        if len(physIfaces) > 0:
            LOG.info('Device(s) not (yet?) known by kernel: "%s"' % ', '.join(missing_devices))
            time.sleep(wait_secs)


    if len(physIfaces) > 0:
        msg = 'Timeout, Device(s) missing: "%s"' % ', '.join(physIfaces)
        LOG.error(msg)
        raise errors.VirtualMediaBootError(msg)
    else:
        LOG.info('All physical devices found.')

    for _device in dhclient_physIfaces:
        stop_dhclient_process(_device)

def _configure_static_net(os_net_config):
    """Configures network using os-net-config utility"""
    global dhclient_physIfaces
    LOG.debug("Configuring static network with os-net-config: %s", os_net_config)
    try:
        os.makedirs('/etc/os-net-config/')
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
        pass
    with open('/etc/os-net-config/config.yaml', 'w') as fp:
        fp.write(os_net_config)

    try:
        _poll_interface(os_net_config)
    except Exception as e:
        LOG.info('Exception while checking for physical interfaces: %s' % str(e) )

    try:
        os.system('/usr/sbin/ip a > /tmp/ifaces_before_initial_netconfig')
    except Exception as e:
        LOG.info('Exception while logging runtime ifaces to /tmp/ifaces_before_initial_netconfig: %s' % str(e) )

    LOG.info('Running os-net-config..')
    
    cmd = [ '/usr/bin/os-net-config', '--detailed-exit-codes', '-v', '-c', '/etc/os-net-config/config.yaml']
    wait_secs = 5
    retries = 3
    while retries > 0:
        retries = retries - 1
        netconf_process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        while True:
            output = netconf_process.stdout.readline()
            if output == '' and netconf_process.poll() is not None:
                break
            if output:
                LOG.info(output.strip())

        rc = netconf_process.poll()
        LOG.info('os-net-config exit with status %d' % rc)

        # os-net-config returns:
        # 0 when nothing changed,
        # 1 on error,
        # 2 when config was modified (assuming option "--detailed-exit-codes")
        
        if rc == 0 or rc == 1:
            LOG.info('os-net-config modified nothing or execution error. Not what we want..')
            LOG.info('Attempt removing physical interface ifcfg-files to force os-net-config to reconfigure')
            
            for iface in dhclient_physIfaces:
                ifcfg_file = '/etc/sysconfig/network-scripts/ifcfg-' + str(iface)
                try:
                    LOG.info('Removing "%s"' % ifcfg_file)
                    os.system('/usr/bin/rm -f ' + ifcfg_file)
                except Exception as e:
                    LOG.info('Ignoring exception when removing "%s": %s' % (ifcfg_file, str(e)))
                    pass
            time.sleep(wait_secs)

        elif rc == 2:
            LOG.info('os-net-config done.')
            break
        else:
            LOG.info('os-net-config unknown exit code??')
            time.sleep(wait_secs)
    
    # Config should be in place assuming os-net-config above was successfull
    # As additional step restart network.service
    LOG.info('Restarting network.service')
    try:
        cmd = ['/usr/bin/systemctl', 'restart', 'network']
        subprocess.check_call(cmd)
    except Exception as e:
        LOG.info('Igoring exception when restarting network service: %s' % str(e))
        pass


def get_file_size(filename):
    "Get the file size by seeking at end"
    fd= os.open(filename, os.O_RDONLY)
    try:
        return os.lseek(fd, 0, os.SEEK_END)
    finally:
        os.close(fd)

def wait_for_cd_device():
    """ This function waits for /dev/sr0 device to appear """
    inputiso = '/dev/sr0'
    wait_count = 30
    while not os.path.exists(inputiso) and wait_count:
        LOG.debug('Waiting for %s to appear. Time left = %d secs' %(inputiso,wait_count))
        time.sleep(1)
        wait_count -= 1

    if not wait_count:
        msg = "Unable to find device %s" %(inputiso)
        raise errors.VirtualMediaBootError(msg)

def check_cd_config():
    """ This function checks for any extended 64K block in CD.
    If it is available it will extract the contents for the block.
    Loop mount the image for reading configuration parameters.
    """
    inputiso = '/dev/sr0'
    outputtgz = '/tmp/cdconf.tgz'
    mode = os.stat(inputiso).st_mode
    if stat.S_ISBLK(mode):
        filesize = get_file_size(inputiso)
        skip = filesize / 2048-32
        ironic_utils.dd(inputiso, outputtgz, 'bs=2k', 'skip=%d'%skip)

        # Check if tgz file is valid.
        try:
            utils.execute("/usr/bin/gzip", '-t', outputtgz)
        except processutils.ProcessExecutionError as err:
            if 'not in gzip format' in err.stderr:
                LOG.info('File is not gzip format skipping!!')
                sys.exit()

        LOG.info('Configuration file in gzip format proceeding for extraction')
        tar = tarfile.open(outputtgz)
        tar.extractall('/tmp/floppy')
        tar.close()

        dir_list = os.listdir('/tmp/floppy')
        for item in dir_list:
            if item.find('.img') != -1:
                os.mkdir('/tmp/floppy/mnt')
                utils.execute("mount", '-o', 'loop', '/tmp/floppy/%s' %item, '/tmp/floppy/mnt')
                time.sleep(1)

def _get_vmedia_params():
    """This method returns the parameters passed through virtual media floppy.

    :returns: a partial dict of potential agent configuration parameters
    :raises: VirtualMediaBootError when it cannot find the virtual media device
    """
    parameters_file = "parameters.txt"

    vmedia_device_file_lower_case = "/dev/disk/by-label/ir-vfd-dev"
    vmedia_device_file_upper_case = "/dev/disk/by-label/IR-VFD-DEV"
    if os.path.exists(vmedia_device_file_lower_case):
        vmedia_device_file = vmedia_device_file_lower_case
    elif os.path.exists(vmedia_device_file_upper_case):
        vmedia_device_file = vmedia_device_file_upper_case
    else:

        # TODO(rameshg87): This block of code is there only for compatibility
        # reasons (so that newer agent can work with older Ironic). Remove
        # this after Liberty release.
        vmedia_device = utils._get_vmedia_device()
        if not vmedia_device:
            msg = "Unable to find virtual media device"
            raise errors.VirtualMediaBootError(msg)

        vmedia_device_file = os.path.join("/dev", vmedia_device)

    vmedia_mount_point = tempfile.mkdtemp()
    try:
        try:
            stdout, stderr = utils.execute("mount", vmedia_device_file,
                                     vmedia_mount_point)
        except processutils.ProcessExecutionError as e:
            msg = ("Unable to mount virtual media device %(device)s: "
                   "%(error)s" % {'device': vmedia_device_file, 'error': e})
            raise errors.VirtualMediaBootError(msg)

        parameters_file_path = os.path.join(vmedia_mount_point,
                                            parameters_file)
        params = _read_params_from_file(parameters_file_path, '\n')

        try:
            stdout, stderr = utils.execute("umount", vmedia_mount_point)
        except processutils.ProcessExecutionError as e:
            pass
    finally:
        try:
            shutil.rmtree(vmedia_mount_point)
        except Exception as e:
            pass

    return params

def _read_params_from_file(filepath, seperator=None):
    """Extract key=value pairs from a file.

    :param filepath: path to a file containing key=value pairs separated by
                     whitespace or newlines.
    :returns: a dictionary representing the content of the file
    """
    with open(filepath) as f:
        cmdline = f.read()

    options = cmdline.split(seperator)
    params = {}
    for option in options:
        if '=' not in option:
            continue
        k, v = option.split('=', 1)
        params[k] = v

    return params

def main():
    log.register_options(CONF)
    CONF(args=sys.argv[1:])
    log.setup(CONF, 'virtmedia-netconfig')
    LOG.info("Starting virtmedia-netconfig!!")

    params = _read_params_from_file('/proc/cmdline')
    # If the node booted over virtual media, the parameters are passed
    # in a text file within the virtual media floppy.

    if params.get('boot_method') == 'vmedia':
        LOG.info("This node is booted with vmedia. Checking for available virtual media!!")
        wait_for_cd_device()
        check_cd_config()
        vmedia_params = _get_vmedia_params()
        params.update(vmedia_params)
        LOG.debug("vmedia parameters: %r", vmedia_params)
        os_net_config = params.get('os_net_config')
        LOG.info("virtmedia: os_net_config=%s" %os_net_config)
        if os_net_config:
            _configure_static_net(os_net_config)

        LOG.debug("Erasing old filesystems")
        utils.execute('/usr/bin/erase-oldfs.sh')


if __name__ == "__main__":
    sys.exit(main())
