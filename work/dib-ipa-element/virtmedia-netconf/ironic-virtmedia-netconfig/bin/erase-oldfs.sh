#!/bin/bash
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

SYS_BLOCK="/sys/class/block"

function is_partition(){
    device=$1
    if [ -e $SYS_BLOCK/$device/partition ];then
        return 0
    else
        return 1
    fi
}

function is_removable(){
    device=$1
    sysdev=$SYS_BLOCK/$device
    if ( is_partition $device );then
        removable=$(readlink -f $sysdev/..)/removable
    else
        removable=$sysdev/removable
    fi
    if [ -e $removable ] && [ $(cat $removable) -eq 1 ];then
        return 0
    else
        return 1
    fi

}

device_list=$(ls $SYS_BLOCK)
read -r -a hd_devices <<< $device_list


for hd_dev in ${hd_devices[@]}; do
    if [ -b /dev/$hd_dev ] && (( is_removable $hd_dev ) || ( is_partition $hd_dev )); then
        echo "Removable or partition $hd_dev. Skipping..."
        continue
    fi
    wipefs --all /dev/$hd_dev
    sgdisk -Z -o /dev/$hd_dev
    dd if=/dev/zero of=/dev/$hd_dev bs=1M count=200
done
