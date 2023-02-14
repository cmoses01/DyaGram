import re

from netmiko import ConnectHandler
import os

class discovery:


    cdp_info = {}
    def __init__(self, netmiko_args_starting_device, database):
    
        self.session = ConnectHandler(**netmiko_args_starting_device)
        self.database = database
        self.current_version = None
        self.current_hostname = None


        self._get_hostname()
        self._get_version()

        self.device_type = "switch" if self.current_version in ['nx_os', 'ios_xe'] else "router"


    def get_cdp_neighbors(self):
        cdp_neighbors = self.session.send_command("show cdp neighbors det")
        cdp_neighbors = self._regex_cdp_neighbors(cdp_neighbors)
        return cdp_neighbors

    def _regex_cdp_neighbors(self, cdp_neighbors):


        list_of_lists = []
        cdp_info_json = {"neighbors": []}

        regex = self._get_cdp_neighbor_regex_strings()
        print(regex)
        device_ids = re.findall(rf"{regex[self.current_version]['device_id']}", cdp_neighbors)
        list_of_lists.append(device_ids)
        ip_addresses = re.findall(regex[self.current_version]['ip_address'], cdp_neighbors)
        list_of_lists.append(ip_addresses)
        local_interfaces = re.findall(regex[self.current_version]['local_interface'], cdp_neighbors)
        list_of_lists.append(local_interfaces)
        neighbor_interfaces = re.findall(regex[self.current_version]['neighbor_interface'], cdp_neighbors)
        list_of_lists.append(neighbor_interfaces)
        mgmt_ip_addresses = re.findall(regex[self.current_version]['mgmt_ip_address'], cdp_neighbors)
        list_of_lists.append(mgmt_ip_addresses)


        neighbor_info = {
			"hostname": "",
			"local_port": "",
			"remote_port": "",
			"mgmt_ip_address": ""
		}
        for i in device_ids:
            counter = 0
            cdp_info_json['neighbors'].append(neighbor_info)
            cdp_neighbors['neighbors'][counter]['hostname'] = i

        print(cdp_info_json)







    def _get_hostname(self):
        self.hostname = self.session.send_command("sh hostname")

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

                 "nx_os": {"device_id": "Device\s+ID:(.*)\(.*\)",
                           "ip_address": r"Interface address.*\n\s+.*:\s+(\d+\.\d+\.\d+\.\d+)",
                           "local_interface": r"Interface:\s+(.*),",
                           "neighbor_interface": r"Port ID.*:\s+(.*)",
                           "mgmt_ip_address": r"Mgmt address.*:\n\s+.*:\s+(\d+\.\d+\.\d+\.\d+)"}}

        return regex[self.current_version]

