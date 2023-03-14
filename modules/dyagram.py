import json
import queue
import re
import time
import os
from netmiko import ConnectHandler
from netmiko.ssh_autodetect import SSHDetect
import requests
import yaml
from concurrent.futures import ThreadPoolExecutor
from queue import Queue


#during multithread

class dyagram:

    # cdp_info = {} will need global list in future when multithreaded/multiprocessed
    # Right now class only supports SSH (netmiko), will need to enable REST later

    def __init__(self, inventory_file, initial=None):

        self.initial = initial
        self.inventory_file = inventory_file
        self.inventory_object = self.get_inv_yaml_obj()
        self._devices_to_query = Queue()
        self._devices_queried = []
        self.topology = {"devices": []}  # topology via cdp and lldp extracted data
        self.username = None
        self.password = None
        self._neighbor_template = {
            "hostname": "",
            "local_port": "",
            "neighbor_port": "",
            "chassis_id": ""
        }

        self._load_creds()
        self._pull_devices_out_of_inventory()


    def _load_creds(self):
        #first try OS ENV
        self.username = os.environ['DYAGRAM_USERNAME']
        self.password = os.environ['DYAGRAM_PASSWORD']


    def discover(self):
        '''

        Generates topology via cdp/lldp neighbors into a json object assigned to topology attribute

        :return:
        '''

        print("DYAGRAM DISCOVERING NETWORK...")

        executor = ThreadPoolExecutor(max_workers=10)

        queue_empty = False
        while not queue_empty:
            try:
               device =  self._devices_to_query.get_nowait()

               try:
                   executor.submit(self._discover_neighbors_by_restconf, device)


               executor.submit(self._discover_neighbors_by_ssh,device)
               self._devices_queried.append(device)
            except queue.Empty:
                queue_empty = True
            except Exception as e:
                print(e)

        executor.shutdown(wait=True)

        #sort topology by hostname to compare to previous

        self.topology['devices'] = sorted(self.topology['devices'], key=lambda d: d['hostname'])


        if self.initial:
            self.export_state()
            print("\n\nDYAMGRAM COMPLETED DISCOVERY!")
        else:
            self.compare_states()


    def export_state(self):

        file = open(r"C:\Users\chrimos\PycharmProjects\DyaGram\app\state.json", 'w')
        json.dump(self.topology, file)
        file.close()

    def compare_states(self):
        file = open(r"C:\Users\chrimos\PycharmProjects\DyaGram\app\state.json", 'r')
        state = json.load(file)
        current_state = self.topology

        if state == current_state:
            print("\n\n\nNO CHANGES IN STATE!")
            print("DYAGRAM COMPLETE")
        else:
            print("\n\n\n\nCHANGES IN STATE!!")
            print(f"\n\nSTATE FILE:\n{state}")
            print(f"\n\nCURRENT STATE:\n{current_state}")
        file.close()

    def get_inv_yaml_obj(self):

        with open(self.inventory_file, 'r') as file:
            try:
                # Converts yaml document to python object
                inventory_object = yaml.safe_load(file)
                return inventory_object

            except yaml.YAMLError as e:
                print(e)



    def _pull_devices_out_of_inventory(self):

        for site in self.inventory_object.keys():
            for ip in self.inventory_object[site]:
                self._devices_to_query.put(ip)


    def _discover_neighbors_by_restconf(self, device):

        lldp_neighbors = self._get_lldp_neighbors_restconf(device)

        self.topology["devices"].append(lldp_neighbors)

        self._devices_queried.append(device)

    # def _get_lldp_neighbors_by_restconf(self, device):
    #
    #     restconf_uri = 'restconf/data'
    #     url = f"https://{device}/{restconf_uri}/"
    #
    #     try:
    #         #openconfig










    def _discover_neighbors_by_ssh(self, device):

        unable_to_find_os = False
        CONN_SET = False

        autodetect_netmiko_args = {"device_type": "autodetect",
         "host": device,
         "username": self.username,
         "password": self.password}

        netmiko_args = {"device_type": "",
                        "host": device,
                        "username": self.username,
                        "password": self.password}
        try:
            guesser = SSHDetect(**autodetect_netmiko_args)
            best_match = guesser.autodetect()
            netmiko_args['device_type'] = best_match
            print(f"BEST MATCH: {best_match}")
        except:

            dev = ConnectHandler(**netmiko_args)
            CONN_SET = True
            os = self._get_os_version(dev)
            netmiko_args['device_type'] = os
            print(f"OS FOUND BY MANUAL LOOKUP: {os}")

        if not CONN_SET:
            dev = ConnectHandler(**netmiko_args)


        try:
            lldp_nei_json = self._get_lldp_neighbors_ssh_textfsm(dev)

            if type(lldp_nei_json) == str:
                raise ValueError("LLDP NEIGHBORS ARE STRs. Try without textfsm")
        except ValueError as e:
            print(e)
            print(f"TRYING VIA SSH: {device}")
            lldp_nei_json = self._get_lldp_neighbors_ssh_regex(dev)
        except Exception as e:
            print(e)
        print("AFTER")

        self.topology["devices"].append(lldp_nei_json)


        dev.disconnect()
        self._devices_queried.append(device)

    def _create_netmiko_session(self):

        return ConnectHandler(**self.netmiko_args)


    def _get_chassis_ids(self, netmiko_session=None, os=None, restconf_ip=None, restconf_headers=None):


        if not netmiko_session and restconf_ip:
            resp = requests.get(f"https://{restconf_ip}//restconf/data/openconfig-interfaces:interfaces",
                                headers=restconf_headers, verify=False)
            if resp.status_code == 200:
                return [i['ethernet']['state']['hw-mac-address']
             for i in resp.json()['interfaces']['interface']
             if 'ethernet' in i.keys() if 'state' in i['ethernet'].keys()
             if 'hw-mac-address' in i['ethernet']['state'].keys()]
            return None


        elif os in ["nx_os", "ios_xe"]:
            output = netmiko_session.send_command("sh interface | inc bia ")
            re_resp = re.findall(
                '(?<=bia\s)[a-f\d][a-f\d][a-f\d][a-f\d]\.[a-f\d][a-f\d][a-f\d][a-f\d]\.[a-f\d][a-f\d][a-f\d][a-f\d]',
                output)

            # PC'S CARRY OVER ETHERNET MAC, SO THIS WOULD CHANGE IF PORT FAILED OVER TO OTHER MEMBERS AND THIS FIXES
            #THAT BY REMOVING DUPLICATES

            chassis_ids = []
            [chassis_ids.append(i) for i in re_resp if i not in chassis_ids]
            return chassis_ids

        elif os == "ios_xr":
            output = netmiko_session.send_command("show lldp")
            return [re.search("(?<=Chassis ID:\s).*", output).group(0)]


    def _get_serial_number(self, netmiko_session):
        show_ver = netmiko_session.send_command("show ver")
        return re.search("board id\s+(.*)", show_ver.lower()).group(1)


    def get_restconf_netconf_capabilities(self):
        return requests.get(f"{self.restconf_url}/netconf-state/capabilities", headers=self.restconf_headers, verify=False)


    def _get_lldp_neighbors_restconf(self, device):

        headers = {"Accept": "application/yang.data+json"}
        """
        Attempts to get lldp neighbor info via various YANG Data models starting with OpenConfig then moving to device
        specific (native)

        returns lldp neighbor info in
        :return:
        """

        #first try OpenConfig YANG

        oc_yang_resp = requests.get(f"https://{device}/openconfig-lldp:lldp/interfaces/interface/",
                                    headers=headers, verify=False)
        # if oc_yang_resp.status_code == 200:
        #     requests.get(f"{self.restconf_url}/openconfig-lldp:lldp/interfaces/interface/",
        #                  headers=headers, verify=False)

        lldp_info_json = {"hostname": self._get_hostname(restconf_ip=device),
                          "chassis_ids": self._get_chassis_ids(restconf_ip=device, restconf_headers=headers),
                          "neighbors": []}

        for intf in oc_yang_resp['interfaces']['interface']:
            if 'neighbors' in intf.keys():
                neighbor_info = self._neighbor_template.copy()
                neighbor_info['hostname'] = intf['neighbors']['neighbor'][0]['state']['system-name']
                neighbor_info['local_port'] = intf['name']
                neighbor_info['neighbor_port'] = intf['neighbors']['neighbor'][0]['state']['port-id']
                neighbor_info['chassis_id'] = intf['neighbors']['neighbor'][0]['state']['chassis-id']
                lldp_info_json['neighbors'].append(neighbor_info)

        #try Cisco-NX-OS-device YANG
        cisco_nx_os_device_yang_resp = requests.get(f"{self.restconf_url}/Cisco-NX-OS-device:System/lldp-items/inst-items/",
                                                    headers={"Accept": "application/yang.data+json", "Content-Type": "application/yang.data+json"}
                                                    , verify=False)

        if cisco_nx_os_device_yang_resp.status_code == 200:
            return cisco_nx_os_device_yang_resp.json()


    def _get_lldp_neighbors_ssh_textfsm(self, netmiko_session):
        os = self._get_os_version(netmiko_session)
        lldp_neighbors_output = netmiko_session.send_command("show lldp neighbors det", use_textfsm=True)
        if type(lldp_neighbors_output) == str:
            return lldp_neighbors_output

        lldp_info_json = {"hostname": self._get_hostname(netmiko_session),
                         "chassis_ids": self._get_chassis_ids(netmiko_session, os),
                         "neighbors": []}



        for neighbor in lldp_neighbors_output:
            neighbor_info = self._neighbor_template.copy()
            neighbor_info['hostname'] = neighbor['neighbor']
            neighbor_info['local_port'] = neighbor['local_interface']
            neighbor_info['neighbor_port'] = neighbor['neighbor_interface']
            neighbor_info['chassis_id'] = neighbor['chassis_id']
            lldp_info_json['neighbors'].append(neighbor_info)

        return lldp_info_json

    def _get_lldp_neighbors_ssh_regex(self, netmiko_session):

        os = self._get_os_version(netmiko_session)
        netmiko_session.host = os

        lldp_neighbors_output = netmiko_session.send_command("show lldp neighbors det")
        cdp_info_json = {"hostname": self._get_hostname(netmiko_session),
                         "chassis_ids": self._get_chassis_ids(netmiko_session, os),
                         "neighbors": []}

        regex_strs = self._get_lldp_neighbor_regex_strings(os)


        system_names = re.findall(regex_strs['system_name'], lldp_neighbors_output, re.MULTILINE)



        system_names = [x.strip(' ') for x in system_names]

        # ip_addresses = re.findall(regex_strs['ip_address'], lldp_neighbors_output)
        # ip_addresses = [x.strip(' ') for x in ip_addresses]

        local_interfaces = re.findall(regex_strs['local_interface'], lldp_neighbors_output)
        local_interfaces = [x.strip(' ') for x in local_interfaces]

        neighbor_interfaces = re.findall(regex_strs['neighbor_interface'], lldp_neighbors_output, re.MULTILINE)
        neighbor_interfaces = [x.strip(' ') for x in neighbor_interfaces]

        chassis_ids = re.findall(regex_strs['chassis_id'], lldp_neighbors_output, re.MULTILINE)
        chassis_ids = [x.strip(' ') for x in chassis_ids]

        # mgmt_ip_addresses = re.findall(regex_strs['mgmt_ip_address'], lldp_neighbors_output)
        # if len(mgmt_ip_addresses) > 0:
        #     mgmt_ip_addresses = [x.strip(' ') for x in mgmt_ip_addresses]

        neighbor_info_template = {
			"hostname": "",
			"local_port": "",
			"neighbor_port": "",
            "chassis_id": ""
		}

        counter = 0
        for i in system_names:
            neighbor_info = neighbor_info_template.copy()
            cdp_info_json['neighbors'].append(neighbor_info)
            cdp_info_json['neighbors'][counter]['hostname'] = i
            counter += 1

        # counter = 0

        # print(cdp_info_json['neighbors'])
        # for i in ip_addresses:
        #     cdp_info_json['neighbors'][counter]["ip_address"] = i
        #     counter += 1

        counter = 0
        for i in local_interfaces:
            cdp_info_json['neighbors'][counter]["local_port"] = i
            counter += 1

        counter = 0

        for i in neighbor_interfaces:
            cdp_info_json['neighbors'][counter]["neighbor_port"] = i
            counter += 1

        counter = 0
        for i in chassis_ids:
            cdp_info_json['neighbors'][counter]['chassis_id'] = i
            counter += 1

        # counter = 0
        # for i in mgmt_ip_addresses:
        #     cdp_info_json['neighbors'][counter]["mgmt_ip_address"] = i
        #     counter += 1

        return cdp_info_json

    def _get_hostname(self, netmiko_session=None, restconf_ip=None, restconf_headers=None):


        if not netmiko_session and restconf_ip:
            try:
                resp = requests.get(f"https://{restconf_ip}/restconf/data/openconfig-system:system/config/name",
                         headers=restconf_headers, verify=False)
                if resp.status_code == 200:
                    return resp.json()['hostname']
                if resp.status_code != 200:
                    # try nexus TEMPORARY
                    resp = requests.get(f"https://{restconf_ip}/restconf/data/Cisco-NX-OS-device:System/name",
                                        headers=restconf_headers, verify=False)
                    if resp.status_code == 200:
                        return resp.json()['name']

            except Exception as e:
                print(e)

        else:
            sh_run_output = netmiko_session.send_command("sh run | inc hostname")
            hostname = re.search("hostname\s+(.*)", sh_run_output).group(1)
            return hostname
        return None

    def _get_os_version(self, netmiko_session):

        sh_version_output = netmiko_session.send_command("show version")
        if "IOS-XE" in sh_version_output:
            return "ios_xe"
        elif "NX-OS" in sh_version_output:
            return "nx_os"
        elif "IOS XR" in sh_version_output:
            return "ios_xr"

        return None


    def _get_lldp_neighbor_regex_strings(self, os):

        regex = {"ios_xe":
                     {"system_name": r"(?<=System Name:\s).*",
                      "local_interface": r"(?<=Local Intf:\s).*",
                      "neighbor_interface": r"(?<=Port id:\s).*",
                      "chassis_id": r"(?<=^Chassis id:\s).*"},

                 "nx_os":
                     {"system_name": r"(?<=System Name:\s).*",
                      "local_interface": r"(?<=Local Port id:\s).*",
                      "neighbor_interface": r"(?<=^Port id:\s).*",
                      "chassis_id": r"(?<=^Chassis id:\s).*"

                      },
                 "ios_xr":
                     {"system_name": r"(?<=System Name:\s).*",
                      "local_interface": r"(?<=Local Interface:\s).*",
                      "neighbor_interface": r"(?<=^Port id:\s).*",
                      "chassis_id": r"(?<=^Chassis id:\s).*"
                      }
                 }

        return regex[os]
