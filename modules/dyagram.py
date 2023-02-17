import re
import time
import os
from netmiko import ConnectHandler

class dyagram:

    # cdp_info = {} will need global list in future when multithreaded/multiprocessed
    # Right now class only supports SSH (netmiko), will need to enable REST later

    def __init__(self, netmiko_args_starting_device, database):

        self.netmiko_args = netmiko_args_starting_device
        self.session = self._create_netmiko_session()
        self.database = database
        self.current_version = None
        self.current_hostname = None
        self.current_device_type = None
        self.current_serial_number = None

        self.topology = {"devices": []}  # topology via cdp and lldp extracted data
        self._devices_queried = []
        self._devices_to_query = []

        self._load_device_info()

    def _load_device_info(self):

        self._get_hostname()
        self._get_version()
        self._get_serial_number()
        self.current_device_type = "switch" if self.current_version in ['nx_os', 'ios_xe'] else "router"

    def _reset_device_info(self):

        self.session.disconnect()
        self.session = None
        self.current_version = None
        self.current_hostname = None
        self.current_serial_number = None

    def discover(self):
        '''

        Generates topology via cdp/lldp neighbors into a json object assigned to topology attribute

        :return:
        '''

        # START WITH STARTING DEVICE
        cdp_nei_json_starting_device = self.get_cdp_neighbors()
        self.topology["devices"].append(cdp_nei_json_starting_device)
        for neighbor in cdp_nei_json_starting_device['neighbors']:
            if neighbor not in self._devices_to_query and neighbor not in self._devices_queried:
                self._devices_to_query.append(neighbor)
        self.session.disconnect()

        for device in self._devices_to_query:

            try:
                self.session.disconnect()
            except:
                pass
            self._reset_device_info()
            self.netmiko_args['host'] = device['mgmt_ip_address']
            self.session = self._create_netmiko_session()
            self._load_device_info()

            cdp_nei_json = self.get_cdp_neighbors()
            self.topology["devices"].append(cdp_nei_json)
            for neighbor in cdp_nei_json_starting_device['neighbors']:
                if neighbor not in self._devices_to_query and neighbor not in self._devices_queried:
                    self._devices_to_query.append(neighbor)
            #self._devices_to_query.remove(device) # this was causing loop issue
            self._devices_queried.append(device)

    def _create_netmiko_session(self):
        return ConnectHandler(**self.netmiko_args)

    def _get_serial_number(self):
        show_ver = self.session.send_command("show ver")
        self.current_serial_number = re.search("board id\s+(.*)", show_ver.lower()).group(1)

    def get_cdp_neighbors(self):

        '''
        returns JSON formatted cdp neighbor data
        :return:
        '''

        cdp_neighbors_output = self.session.send_command("show cdp neighbors det")
        return self._regex_cdp_neighbors(cdp_neighbors_output)

    def _regex_cdp_neighbors(self, cdp_neighbors):

        cdp_info_json = {"hostname": self.current_hostname, "serial_number": self.current_serial_number, "neighbors": []}
        regex = self._get_cdp_neighbor_regex_strings()
        device_ids = []

        for r in regex['device_id']:
            print(r)
            ids = re.findall(r, cdp_neighbors)
            print(f"IDS: {ids}")
            for i in ids:
                print(i)
                try:
                    regexed_again_neighbor = re.match("Device\s+ID:(.*)\(.*\)", i)
                    device_ids.append(regexed_again_neighbor.group(1))
                except:
                    try:
                        regexed_again_neighbor = re.match("Device\s+ID:([^\.]*)", i)
                        device_ids.append(regexed_again_neighbor.group(1))
                    except:
                        continue

        print(f"DEVICE IDS: {device_ids}")


        device_ids = [x.strip(' ') for x in device_ids]

        ip_addresses = re.findall(regex['ip_address'], cdp_neighbors)
        ip_addresses = [x.strip(' ') for x in ip_addresses]

        local_interfaces = re.findall(regex['local_interface'], cdp_neighbors)
        local_interfaces = [x.strip(' ') for x in local_interfaces]

        neighbor_interfaces = re.findall(regex['neighbor_interface'], cdp_neighbors)
        neighbor_interfaces = [x.strip(' ') for x in neighbor_interfaces]

        mgmt_ip_addresses = re.findall(regex['mgmt_ip_address'], cdp_neighbors)
        if len(mgmt_ip_addresses) > 0:
            mgmt_ip_addresses = [x.strip(' ') for x in mgmt_ip_addresses]

        neighbor_info_template = {
			"hostname": "",
			"local_port": "",
			"neighbor_port": "",
            "ip_address": "",
			"mgmt_ip_address": ""
		}

        counter = 0
        for i in device_ids:
            neighbor_info = neighbor_info_template.copy()
            cdp_info_json['neighbors'].append(neighbor_info)
            cdp_info_json['neighbors'][counter]['hostname'] = i
            counter += 1

        counter = 0
        print(ip_addresses)
        print(cdp_info_json['neighbors'])
        for i in ip_addresses:
            cdp_info_json['neighbors'][counter]["ip_address"] = i
            counter += 1

        counter = 0
        for i in local_interfaces:
            cdp_info_json['neighbors'][counter]["local_port"] = i
            counter += 1

        counter = 0
        for i in neighbor_interfaces:
            cdp_info_json['neighbors'][counter]["neighbor_port"] = i
            counter += 1

        counter = 0
        for i in mgmt_ip_addresses:
            cdp_info_json['neighbors'][counter]["mgmt_ip_address"] = i
            counter += 1

        return cdp_info_json

    def _get_hostname(self):

        sh_run_output = self.session.send_command("sh run | inc hostname")
        self.current_hostname = re.search("hostname\s+(.*)", sh_run_output).group(1)

    def _get_version(self):
        sh_version_output = self.session.send_command("show version")
        if "IOS-XE" in sh_version_output:
            self.current_version = "ios_xe"
        elif "NX-OS" in sh_version_output:
            self.current_version = "nx_os"
        else:
            self.current_version = None

    def _get_cdp_neighbor_regex_strings(self):

        regex = {"ios_xe": #{"device_id": [r"Device\s+ID:(.*)\(.*\)"],
                            {"device_id": [r"Device\s+ID:.*"],
                           "ip_address": r"Entry address.*\n\s+.*:\s+(\d+\.\d+\.\d+\.\d+)",
                           "local_interface": r"Interface:\s+(.*),",
                           "neighbor_interface": r"Port ID.*:\s+(.*)",
                           "mgmt_ip_address": r"Management address.*:\s+.*:\s+(\d+\.\d+\.\d+\.\d+)"},

                 "nx_os": #{"device_id": [r"Device\s+ID:(.*)\(.*\)", r"Device\s+ID:([^\.]*)"],
                           {"device_id": [r"Device\s+ID:.*"],
                           "ip_address": r"Interface address.*\n\s+.*:\s+(\d+\.\d+\.\d+\.\d+)",
                           "local_interface": r"Interface:\s+(.*),",
                           "neighbor_interface": r"Port ID.*:\s+(.*)",
                           "mgmt_ip_address": r"Mgmt address.*:\n\s+.*:\s+(\d+\.\d+\.\d+\.\d+)"}}

        return regex[self.current_version]
