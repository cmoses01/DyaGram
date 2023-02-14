import re

from netmiko import ConnectHandler
import os

class discovery:

    # cdp_info = {} will need global list in future when multithreaded/multiprocessed

    def __init__(self, netmiko_args_starting_device, database):
    
        self.session = ConnectHandler(**netmiko_args_starting_device)
        self.database = database
        self.current_version = None
        self.current_hostname = None
        self.current_serial_number = None
        self.topology = {"devices": []}  # topology via cdp and lldp extracted data

        self._get_hostname()
        self._get_version()
        self._get_serial_number()

        self.device_type = "switch" if self.current_version in ['nx_os', 'ios_xe'] else "router"

    def discover_topology(self):
        '''

        Generates topology via cdp/lldp neighbors into a json object assigned to topology attribute

        :return:
        '''

        cdp_nei_json = self.get_cdp_neighbors()
        self.topology["devices"].append(cdp_nei_json)

    def _get_serial_number(self):
        show_ver = self.session.send_command("show ver | inc board ID")
        self.current_serial_number = re.search("board ID\s+(.*)", show_ver).group(1)


    def get_cdp_neighbors(self):

        '''
        returns JSON formatted cdp neighbor data
        :return:
        '''
        cdp_neighbors = self.session.send_command("show cdp neighbors det")
        return self._regex_cdp_neighbors(cdp_neighbors)



    def _regex_cdp_neighbors(self, cdp_neighbors):

        cdp_info_json = {"hostname": self.current_hostname, "serial_number": self.current_serial_number, "neighbors": []}

        regex = self._get_cdp_neighbor_regex_strings()

        device_ids = re.findall(rf"{regex['device_id']}", cdp_neighbors)
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

        neighbor_info = {
			"hostname": "",
			"local_port": "",
			"neighbor_port": "",
            "ip_address": "",
			"mgmt_ip_address": ""
		}

        for i in device_ids:
            counter = 0
            cdp_info_json['neighbors'].append(neighbor_info)
            cdp_info_json['neighbors'][counter]['hostname'] = i

        for i in ip_addresses:
            counter = 0
            cdp_info_json['neighbors'][counter]["ip_address"] = i

        for i in local_interfaces:
            counter = 0
            cdp_info_json['neighbors'][counter]["local_port"] = i

        for i in neighbor_interfaces:
            counter = 0
            cdp_info_json['neighbors'][counter]["neighbor_port"] = i

        for i in mgmt_ip_addresses:
            counter = 0
            cdp_info_json['neighbors'][counter]["mgmt_ip_address"] = i

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

        regex = {"ios_xe": {"device_id": "Device\s+ID:(.*)\(.*\)",
                           "ip_address": r"Entry address.*\n\s+.*:\s+(\d+\.\d+\.\d+\.\d+)",
                           "local_interface": r"Interface:\s+(.*),",
                           "neighbor_interface": r"Port ID.*:\s+(.*)",
                           "mgmt_ip_address": r"Management address.*:\s+.*:\s+(\d+\.\d+\.\d+\.\d+)"},

                 "nx_os": {"device_id": "Device\s+ID:(.*)\(.*\)|Device\s+ID:([^\.]*)",
                           "ip_address": r"Interface address.*\n\s+.*:\s+(\d+\.\d+\.\d+\.\d+)",
                           "local_interface": r"Interface:\s+(.*),",
                           "neighbor_interface": r"Port ID.*:\s+(.*)",
                           "mgmt_ip_address": r"Mgmt address.*:\n\s+.*:\s+(\d+\.\d+\.\d+\.\d+)"}}

        return regex[self.current_version]

