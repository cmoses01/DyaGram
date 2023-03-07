import re
import time
import os
from netmiko import ConnectHandler
import requests
import yaml


class dyagram:

    # cdp_info = {} will need global list in future when multithreaded/multiprocessed
    # Right now class only supports SSH (netmiko), will need to enable REST later

    def __init__(self, init_file_location, database):

        self.current_device_is_starting_device = True

        self.init_file_location = init_file_location
        self.database = database
        self.starting_device = None
        self.current_version = None
        self.current_hostname = None
        self.current_device_type = None
        self.current_serial_number = None

        self.topology = {"devices": []}  # topology via cdp and lldp extracted data

        self.username = None
        self.password = None
        self.ip = None

        self.restconf_url = f'https://{self.ip}/restconf/data'
        self.restconf_headers = {
            'Accept': 'application/yang-data+json',
            'Content-Type': 'application/yang-data+json'
        }
        self.device_brand = None
        self.device_os = None
        self._devices_queried = []
        self._devices_to_query = []
        self._current_device = None

        self._load_creds()
        self._load_init_file()

        self.netmiko_args_starting_device = {"device_type": "cisco_ios",
                                             "host": self.starting_device,
                                             "username": self.username,
                                             "password": self.password}
        self.netmiko_args = {"device_type": "cisco_ios",
                             "host": self.ip,
                             "username": self.username,
                             "password": self.password}
        #self.netmiko_args = None
        self.session = self._create_netmiko_session()
        self._load_device_info()

    def _load_creds(self):
        #first try OS ENV
        self.username = os.environ['DYAGRAM_USERNAME']
        self.password = os.environ['DYAGRAM_PASSWORD']


    def _load_init_file(self):
        with open(self.init_file_location, 'r') as file:
            init = yaml.safe_load(file)
            self.starting_device = init['starting_device']['ip']

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
        #self._discover_neighbors_by_restconf()
        self._discover_neighbors_by_ssh()

        self.current_device_is_starting_device = False

        #next will start to crawl through neighbors
        for device in self._devices_to_query:
            self._current_device = device
            #self._discover_neighbors_by_restconf()
            self._discover_neighbors_by_ssh()



    def _discover_neighbors_by_restconf(self):
        pass


    def _discover_neighbors_by_ssh(self):

        if not self.current_device_is_starting_device:

            try:
                self.session.disconnect()
            except:
                pass

            self._reset_device_info()

            if self._current_device['mgmt_ip_address']:
                print(f"CURRENT MGMT IP ADDRESS: {self._current_device['mgmt_ip_address']}")
                self.netmiko_args['host'] = self._current_device['mgmt_ip_address']
            elif self._current_device['ip_address']:
                print(f"CURRENT NON-MGMT IP ADDRESS: {self._current_device['ip_address']}")
                self.netmiko_args['host'] = self._current_device['ip_address']
            else:
                raise Exception(f"IP Address not found:\n {self._current_device}")
            self.session = self._create_netmiko_session()
            self._load_device_info()

        else:
            self.netmiko_args['host'] = self.netmiko_args_starting_device['host']

        cdp_nei_json = self._get_cdp_neighbors_regex()
        self.topology["devices"].append(cdp_nei_json)

        for neighbor in cdp_nei_json['neighbors']:
            if neighbor not in self._devices_to_query and neighbor not in self._devices_queried:
                self._devices_to_query.append(neighbor)
        self.session.disconnect()
        self._devices_queried.append(self._current_device)



    # def _discover_by_cdp(self):
    #
    #     # try:
    #     #     #discover by RESTCONF
    #     #     pass
    #     # except:
    #     #     pass
    #     #
    #     #
    #     # try:
    #     #     cdp_nei_json_starting_device = self._get_cdp_neighbors_regex()
    #     # except:
    #     #     #try open config
    #     #     pass
    #     #
    #     #
    #     #
    #     # self.topology["devices"].append(cdp_nei_json_starting_device)
    #     # for neighbor in cdp_nei_json_starting_device['neighbors']:
    #     #     if neighbor not in self._devices_to_query and neighbor not in self._devices_queried:
    #     #         self._devices_to_query.append(neighbor)
    #     # self.session.disconnect()
    #
    #     # for device in self._devices_to_query:
    #     #
    #     #     try:
    #     #         self.session.disconnect()
    #     #     except:
    #     #         pass
    #     #     self._reset_device_info()
    #     #     self.netmiko_args['host'] = device['mgmt_ip_address']
    #     #     self.session = self._create_netmiko_session()
    #     #     self._load_device_info()
    #
    #         cdp_nei_json = self._get_cdp_neighbors_regex()
    #         self.topology["devices"].append(cdp_nei_json)
    #         for neighbor in cdp_nei_json_starting_device['neighbors']:
    #             if neighbor not in self._devices_to_query and neighbor not in self._devices_queried:
    #                 self._devices_to_query.append(neighbor)
    #         # self._devices_to_query.remove(device) # this was causing loop issue
    #

    def _create_netmiko_session(self):
        if self.current_device_is_starting_device:
            return ConnectHandler(**self.netmiko_args_starting_device)

        return ConnectHandler(**self.netmiko_args)

    def _get_serial_number(self):
        show_ver = self.session.send_command("show ver")
        self.current_serial_number = re.search("board id\s+(.*)", show_ver.lower()).group(1)

    # def get_neighbors(self):
    #
    #     '''
    #     returns JSON formatted cdp/lldp neighbor data
    #     :return:
    #     '''
    #
    #
    #     return self._get_cdp_neighbors_regex()

    def get_restconf_netconf_capabilities(self):
        return requests.get(f"{self.restconf_url}/netconf-state/capabilities", headers=self.restconf_headers, verify=False)

    def _get_lldp_neighbors_restconf(self):

        """
        Attempts to get lldp neighbor info via various YANG Data models starting with OpenConfig then moving to device
        specific (native)

        returns lldp neighbor info in
        :return:
        """

        #first try OpenConfig YANG
        oc_yang_resp = requests.get(f"{self.restconf_url}/openconfig-lldp:lldp/interfaces/interface/",
                                    headers=self.restconf_headers, verify=False)
        if oc_yang_resp.status_code == 200:
            return oc_yang_resp.json()

        #try Cisco-NX-OS-device YANG
        cisco_nx_os_device_yang_resp = requests.get(f"{self.restconf_url}/Cisco-NX-OS-device:System/lldp-items/inst-items/",
                                                    headers={"Accept": "application/yang.data+json", "Content-Type": "application/yang.data+json"}
                                                    , verify=False)

        if cisco_nx_os_device_yang_resp.status_code == 200:
            return cisco_nx_os_device_yang_resp.json()



    def _get_cdp_neighbors_regex(self):
        print(self.session.username)
        print(self.session.password)
        print(self.session.host)
        print(self.session.device_type)

        cdp_neighbors_output = self.session.send_command("show cdp neighbors det")
        cdp_info_json = {"hostname": self.current_hostname, "serial_number": self.current_serial_number, "neighbors": []}
        regex_strs = self._get_cdp_neighbor_regex_strings()
        device_ids = []

        for r in regex_strs['device_id']:
            print(r)
            ids = re.findall(r, cdp_neighbors_output)
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

        ip_addresses = re.findall(regex_strs['ip_address'], cdp_neighbors_output)
        ip_addresses = [x.strip(' ') for x in ip_addresses]

        local_interfaces = re.findall(regex_strs['local_interface'], cdp_neighbors_output)
        local_interfaces = [x.strip(' ') for x in local_interfaces]

        neighbor_interfaces = re.findall(regex_strs['neighbor_interface'], cdp_neighbors_output)
        neighbor_interfaces = [x.strip(' ') for x in neighbor_interfaces]

        mgmt_ip_addresses = re.findall(regex_strs['mgmt_ip_address'], cdp_neighbors_output)
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
