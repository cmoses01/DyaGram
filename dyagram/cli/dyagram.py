import json
import queue
import re
import os
import time
import traceback
from pathlib import Path

from netmiko import ConnectHandler
from netmiko import NetmikoAuthenticationException
from netmiko.exceptions import SSHException
from netmiko.ssh_autodetect import SSHDetect
import requests
import yaml
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from urllib3.exceptions import InsecureRequestWarning
import logging
from tqdm import tqdm
import warnings
from colorama import Fore
from deepdiff import DeepDiff

warnings.simplefilter("ignore")



requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

logging.basicConfig(format=' %(message)s')




class dyagram:

    def __init__(self, inventory_file=None, verbose=False):

        self.pbar = None
        self.pbar_update_int = None
        self.inventory_file = inventory_file
        self.verbose = verbose
        self.log = None
        self.setup_logging()

        self.inventory_object = self.get_inv_yaml_obj()
        self._devices_to_query = Queue()
        self._devices_queried = []
        self.topology = {"devices": []}  # topology via cdp and lldp extracted data
        self.username = None
        self.password = None
        self.changes_in_state = None
        self.site = self.get_current_site()
        self.state_exists = self.does_state_exist()
        self.lldp_neighbor_template = {
            "hostname": "",
            "local_port": "",
            "neighbor_port": "",
            "chassis_id": ""
        }

        self._load_creds()
        self._load_inventory()
        self.netmiko_args_template = {"device_type": "",
                                      "host": "",
                                      "username": self.username,
                                      "password": self.password,
                                      "secret": self.password,

                                      "banner_timeout": 200}



    def setup_logging(self):
        log = logging.getLogger("")
        self.log = log
        if self.verbose:
            self.log.setLevel(logging.INFO)
        else:
            self.log.setLevel(logging.CRITICAL)



    def get_current_site(self):
        try:

            file = open(r".info/info.json", 'r')
            info = json.load(file)
            file.close()
            return info['current_site']
        except:
            print("Unable to load last site.")

    @staticmethod
    def get_traceback():
        x = traceback.format_exc()
        result = " ".join(line.strip() for line in x.splitlines())
        return result

    def _load_creds(self):
        #first try OS ENV
        self.log.info("Loading Credentials")
        self.username = os.environ['DYAGRAM_USERNAME']
        self.password = os.environ['DYAGRAM_PASSWORD']
        self.log.info("Loaded Credentials")


    def __discover_lldp_neighbors(self, device):

        """
        this enables us to keep multithreading and not block for waiting for an exception for restconf before trying
        ssh.

        See inside discover() for threading
        :param device:
        :return:
        """

        try:
            self.log.info(f"DEVICE: {device} - RESTCONF : Discovering LLDP Neighbors - START")
            resp = self._discover_lldp_neighbors_by_restconf(device)
            if not resp:
                raise
            self.pbar.update(self.pbar_update_int)
            self.log.info(f"DEVICE: {device} - RESTCONF : Discovering LLDP Neighbors - SUCCESSFUL")
        except SSHException:
            print("CAUGHT SSH EXCEPT 02")
        except:
            try:
            # try ssh
                self.log.info(f"DEVICE: {device} - RESTCONF : Discovering LLDP Neighbors - FAILURE")
                self.log.info(f"DEVICE: {device} - SSH : Discovering LLDP Neighbors - START")
                self._discover_lldp_neighbors_by_ssh(device)
                self.pbar.update(self.pbar_update_int)
                self.log.info(f"DEVICE: {device} - SSH : Discovering LLDP Neighbors - SUCCESSFUL")
            except:
                tb = self.get_traceback()
                self.log.info(f"DEVICE: {device} EXCEPTION01 THROWN IN __discover_lldp_neighbors : {tb}")

    def discover(self):

        """

        Generates topology via cdp/lldp neighbors into a json object assigned to topology attribute

        :return:
        """
        try:
            print(f'Discovering site "{self.site}"')
            self.pbar = tqdm(total=100,
                             bar_format=Fore.LIGHTBLUE_EX + "{l_bar}{bar:20}|") if not self.verbose else tqdm(total=100,
                                                                                                         bar_format="{l_bar}{bar}|",
                                                                                                         disable=True)

            executor = ThreadPoolExecutor(max_workers=30)

            queue_empty = False
            while not queue_empty:
                try:
                    device = self._devices_to_query.get_nowait()
                    self.log.info(f"Pulled device {device} from Queue")
                    self.topology['devices'].append({'hostname': "", 'inventory_ip': device, 'layer2': {}, 'routes': [], 'dynamic_routing_neighbors': {}})

                    future_lldp = executor.submit(self.__discover_lldp_neighbors, device)
                    self.log.info(f"DEVICE: {device} - Submitted for discover_lldp_neighbors")
                    future_routes = executor.submit(self.discover_routes, device)
                    self.log.info(f"DEVICE: {device} - Submitted for discover_routes")
                    future_routing_neighbors = executor.submit(self.discover_dynamic_routing_neighbors, device)
                    self.log.info(f"DEVICE: {device} - Submitted for discover_dynamic_routing_neighbors")

                    self._devices_queried.append(device)

                except queue.Empty:
                    self.log.info(f"QUEUE EMPTY")
                    queue_empty = True
                except:
                    tb = self.get_traceback()
                    self.log.info(f"EXCEPTION THROWN IN PULLING FROM QUEUE: {tb}")

            executor.shutdown(wait=True)

            #sort topology by hostname to compare to previous

            self.topology['devices'] = sorted(self.topology['devices'], key=lambda d: d['hostname'])

            if not self.state_exists:
                self.export_state()
            else:
                self.compare_states()

            self.pbar.close()
            if self.changes_in_state:
                print("\nChanges in state!\n")
                file = open(rf"{self.site}/state.json", 'r')
                state = json.load(file)
                try:
                    diffs = self.get_state_diff(state, self.topology) # state is the state file on record and topology is current state
                except Exception:
                    tb = self.get_traceback()
                    self.log.info(f"EXCEPTION THROWN GETTING DIFFS: {tb}")
                # print to screen the diffs
                print("DIFFS\n")
                for ip in diffs:
                    print(f"{ip}\n")
                    for i in diffs[ip]['added']:
                        print(Fore.LIGHTGREEN_EX + f"  + {i}" + Fore.RESET)
                    for i in diffs[ip]['removed']:
                        print(Fore.RED + f"  - {i}"+ Fore.RESET)
                    for i in diffs[ip]['changed']:
                        print(Fore.YELLOW + f"  ~ {i}"+ Fore.RESET)
                    print("\n\n")
            elif not self.changes_in_state and self.state_exists:
                print("\nNo changes in state")
            else:
                print("\n")  # gives another space after progress bar in CLI
        except SSHException:
            print("CAUGHT SSH EXCEPT 01")
        except:
            try:
                tb = self.get_traceback()
                self.log.info(f"DEVICE: {device} MAIN EXCEPTION : {tb}")
            except:
                tb = self.get_traceback()
                self.log.info(f"DEVICE: UNKNOWN - MAIN EXCEPTION : {tb}")


    def does_state_exist(self):
        path = Path(f"{self.site}/state.json")
        return path.is_file()

    def export_state(self):

        file = open(rf"{self.site}/state.json", 'w')
        json.dump(self.topology, file)
        file.close()


    def compare_states(self):

        file = open(rf"{self.site}/state.json", 'r')
        state = json.load(file)
        current_state = self.topology

        if state == current_state:
            self.changes_in_state = False
        else:
            self.changes_in_state = True
        file.close()


    def discover_routes(self, device):

        try:
            self.log.info(f"DEVICE: {device} - RESTCONF : Discovering routes - START")
            routes = self.discover_routes_restconf(device)
            if not routes:
                raise
            self.pbar.update(self.pbar_update_int)
            self.log.info(f"DEVICE: {device} - RESTCONF : Discovering routes - SUCCESSFUL")
        except SSHException:
            print("CAUGHT SSH EXCEPT 04")
        except:
            try:
                self.log.info(f"DEVICE: {device} - RESTCONF : Discovering routes - FAILURE")
                self.log.info(f"DEVICE: {device} - SSH : Discovering routes - START")
                self.discover_routes_ssh(device)
                self.pbar.update(self.pbar_update_int)
                self.log.info(f"DEVICE: {device} - SSH : Discovering routes - SUCCESSFUL")
            except:
                tb = self.get_traceback()
                self.log.info(f"DEVICE: {device} EXCEPTION01 THROWN IN discover_routes : {tb}")

        return True

    def discover_routes_restconf(self, device):
        return None

    def discover_routes_ssh(self, device):

        # CONN_SET = False
        try:
            self.log.info(f"DEVICE: {device} - SSH : GETTING DEVICE TYPE : discover_routes_ssh")
            os = self.get_device_type(device)
            self.log.info(f"DEVICE: {device} - SSH : GOT DEVICE TYPE : discover_routes_ssh")

            netmiko_args = {"device_type": os,
                            "host": device,
                            "username": self.username,
                            "password": self.password,
                            "secret": self.password,
                            "banner_timeout": 200
                            }
            # autodetect_tries = 0
            # while autodetect_tries < 10:
            #     try:
            #         guesser = SSHDetect(**autodetect_netmiko_args)
            #         best_match = guesser.autodetect()
            #         netmiko_args['device_type'] = best_match
            #
            #         dev = ConnectHandler(**netmiko_args)
            #         dev.enable()
            #
            #
            #
            #     except NetmikoAuthenticationException:
            #         # print(f"AUTHENTICATION ERROR FOR DEVICE: {device}")
            #         return False
            #     except:
            #         autodetect_tries += 1
            #         time.sleep(5)
            #         tb = self.get_traceback()
            #         self.log.info(f"DEVICE: {device} EXCEPTION02 THROWN IN discover_routes_ssh: {tb}")

                # raise Exception("Unable to determine OS or OS Not Supported.")
            #     try:
            #         if not netmiko_args['device_type']:
            #             # Later put in unable to find OS
            #             netmiko_args['device_type'] = "cisco_ios"
            #         dev = ConnectHandler(**netmiko_args)
            #         dev.enable()
            #         CONN_SET = True
            #     except Exception:
            #         tb = self.get_traceback()
            #         self.log.info(f"DEVICE: {device} EXCEPTION THROWN IN discover_routes_ssh: {tb}")
            #
            #         # print(tb)
            #
            #
            # os = self._get_os_version(dev)
            # netmiko_args['device_type'] = os

            # if not CONN_SET:
            #     dev = ConnectHandler(**netmiko_args)
            self.log.info(f"DEVICE: {device} - SSH : CREATING NETMIKO OBJ : discover_routes_ssh")
            dev = ConnectHandler(**netmiko_args)
            self.log.info(f"DEVICE: {device} - SSH : CREATED NETMIKO OBJ : discover_routes_ssh")
            dev.enable()

            routes_w_vrf = dev.send_command("show ip route vrf all", use_textfsm=True)
            routes_wo_vrf = dev.send_command("show ip route", use_textfsm=True)
            for route in routes_w_vrf:
                if 'uptime' in route.keys():
                    route.pop('uptime')
            for route in routes_wo_vrf:
                if 'uptime' in route.keys():
                    route.pop('uptime')
            combined_routes = routes_wo_vrf + routes_w_vrf
            routes = [i for n, i in enumerate(combined_routes) if i not in combined_routes[n + 1:]]

            dev.disconnect()
            for i in self.topology['devices']:
                if i['inventory_ip'] == device:
                    i['routes'] = routes
                    break
        except:
            tb = self.get_traceback()
            self.log.info(f"DEVICE: {device} EXCEPTION THROWN IN discover_routes_ssh: {tb}")

    @staticmethod
    def get_state_diff(previous_state, current_state):

        device_diffs = {}

        elem_changed = {
            "routes": []}  # this keeps up with "changes" when converting to removed/add for routes,
                           # this is due to deeper dictionary items

        diff_resp = DeepDiff(previous_state, current_state, ignore_order=True)

        if not diff_resp:
            return None

        diff_type = None
        for k in diff_resp.keys():
            if "added" in k:
                diff_type = "added"
                s = current_state
            elif "removed" in k:
                diff_type = "removed"
                s = previous_state
            elif "changed" in k:
                s = current_state
                diff_type = "changed"

            for diff in diff_resp[k]:

                resp = re.search("root\['devices'\]\[(\d+)\]\[([^\]]*)\]", diff)
                device_elem = int(resp.group(1))
                category = resp.group(2).replace("'", "").replace('"', '')
                if s['devices'][device_elem]['inventory_ip'] not in device_diffs.keys():
                    device_diffs[s['devices'][device_elem]['inventory_ip']] = {"added": [], "removed": [],
                                                                               "changed": []}


                if category == "dynamic_routing_neighbors":
                    if 'eigrp' in diff:
                        routing_protocol = "EIGRP"
                    elif 'ospf' in diff:
                        routing_protocol = "OSPF"
                    elif 'bgp' in diff:
                        routing_protocol = "BGP"

                    if diff_type != "changed":
                        device_diffs[s['devices'][device_elem]['inventory_ip']][diff_type].append(
                            f"{routing_protocol} Neighbor {diff_resp[k][diff]}")
                    else:
                        device_diffs[s['devices'][device_elem]['inventory_ip']]["removed"].append(
                            f"{routing_protocol} Neighbor {diff_resp[k][diff]['old_value']}")
                        device_diffs[s['devices'][device_elem]['inventory_ip']]["added"].append(
                            f"{routing_protocol} Neighbor {diff_resp[k][diff]['new_value']}")

                elif category == "layer2":
                    if diff_type != "changed":
                        device_diffs[s['devices'][device_elem]['inventory_ip']][diff_type].append(
                            f"LLDP Neighbor {diff_resp[k][diff]['hostname']} (Chassis ID: {diff_resp[k][diff]['chassis_id']})")

                    else:
                        resp = re.search("\['neighbors'\]\[(\d+)\]\['(.*)'\]", diff)
                        neigh_elem = int(resp.group(1))
                        neigh_property = resp.group(2)
                        device_diffs[s['devices'][device_elem]['inventory_ip']][diff_type].append(
                            f"LLDP Neighbor {s['devices'][device_elem][category]['neighbors'][neigh_elem]['hostname']}: {neigh_property}: "
                            f"NEW VALUE: {diff_resp[k][diff]['new_value']}, OLD VALUE: {diff_resp[k][diff]['old_value']}")
                elif category == "routes":

                    if diff_type != "changed":

                        try:
                            device_diffs[s['devices'][device_elem]['inventory_ip']][diff_type].append(

                                f"Route {diff_resp[k][diff]['network']}/{diff_resp[k][diff]['mask']} {diff_resp[k][diff]['next_hop']}")
                        except KeyError:
                            # different return for next hop for XR
                            device_diffs[s['devices'][device_elem]['inventory_ip']][diff_type].append(

                                f"Route {diff_resp[k][diff]['network']}/{diff_resp[k][diff]['mask']} {diff_resp[k][diff]['nexthop_ip']}")
                    else:

                        resp = re.search("\['routes'\]\[(\d+)\]\['(.*)'\]", diff)

                        route_elem = int(resp.group(1))

                        if route_elem not in elem_changed['routes']:
                            elem_changed['routes'].append(route_elem)

                            try:

                                device_diffs[s['devices'][device_elem]['inventory_ip']]["removed"].append(
                                    f"Route {s['devices'][device_elem][category][route_elem]['network']}/"
        
                                    f"{previous_state['devices'][device_elem][category][route_elem]['mask']} "
        
                                    f"{previous_state['devices'][device_elem][category][route_elem]['next_hop']}")

                                device_diffs[s['devices'][device_elem]['inventory_ip']]["added"].append(

                                    f"Route {s['devices'][device_elem][category][route_elem]['network']}/"
        
                                    f"{current_state['devices'][device_elem][category][route_elem]['mask']} "
        
                                    f"{current_state['devices'][device_elem][category][route_elem]['next_hop']}")
                            except KeyError:
                                # different return for next hop for XR
                                device_diffs[s['devices'][device_elem]['inventory_ip']]["removed"].append(
                                    f"Route {s['devices'][device_elem][category][route_elem]['network']}/"

                                    f"{previous_state['devices'][device_elem][category][route_elem]['mask']} "

                                    f"{previous_state['devices'][device_elem][category][route_elem]['nexthop_ip']}")

                                device_diffs[s['devices'][device_elem]['inventory_ip']]["added"].append(

                                    f"Route {s['devices'][device_elem][category][route_elem]['network']}/"

                                    f"{current_state['devices'][device_elem][category][route_elem]['mask']} "

                                    f"{current_state['devices'][device_elem][category][route_elem]['nexthop_ip']}")


        return device_diffs

    def get_device_type(self, device):

        try:

            autodetect_netmiko_args = {"device_type": "autodetect",
                                       "host": device,
                                       "username": self.username,
                                       "password": self.password,
                                       "banner_timeout": 30}
            autodetect_tries = 0
            while autodetect_tries < 10:
                try:
                    guesser = SSHDetect(**autodetect_netmiko_args)
                    best_match = guesser.autodetect()


                    return best_match


                except NetmikoAuthenticationException:
                    # print(f"AUTHENTICATION ERROR FOR DEVICE: {device}")
                    return None

                except:
                    if autodetect_tries > 10:
                        tb = self.get_traceback()
                        self.log.info(f"DEVICE: {device} EXCEPTION THROWN IN GET_DEVICE_TYPE: {tb}")
                        raise Exception("Unable to access device")
                    autodetect_tries += 1
                    time.sleep(5)
        except:
            tb = self.get_traceback()
            self.log.info(f"DEVICE: {device} EXCEPTION THROWN IN get_device_type: {tb}")



    def discover_dynamic_routing_neighbors(self, device):

        try:

            self.pbar.update(self.pbar_update_int)

            self.discover_eigrp_neighbors(device)

            # self.discover_ospf_neighbors(device)
            #
            # self.discover_bgp_neighbors(device)

            self.pbar.update(self.pbar_update_int)
        except SSHException:
            print("CAUGHT SSH EXCEPT 03")
        except:
            tb = self.get_traceback()
            self.log.info(f"DEVICE: {device} EXCEPTION THROWN IN discover_dynamic_routing_neighbors: {tb}")

    def discover_ospf_neighbors(self, device):
        pass

    def discover_ospf_neighbors_ssh(self, device):
        return None

    def discover_ospf_neighbors_restconf(self):
        return None

    def discover_eigrp_neighbors(self, device):

        try:
            self.log.info(f"DEVICE: {device} - RESTCONF : Discovering EIGRP Neighbors - START")
            #time.sleep(5)  # FIXME: IF I DON'T PUT THIS HERE THERE IS AN EXCEPTION THROWN THAT I CAN'T CATCH
            discovered = self.discover_eigrp_neighbors_restconf()

            if not discovered:
                self.log.info(f"DEVICE: {device} - RESTCONF : Discovering EIGRP Neighbors - FAIL")
                try:
                    self.log.info(f"DEVICE: {device} - SSH : Discovering EIGRP Neighbors - START")
                    self.discover_eigrp_neighbors_ssh(device)
                    self.log.info(f"DEVICE: {device} - SSH : Discovering EIGRP Neighbors - SUCCESS")
                except:
                    tb = self.get_traceback()
                    self.log.info(f"DEVICE: {device} EXCEPTION THROWN IN DISCOVERING EIGRP NEIGHBORS: {tb}")
            else:
                self.log.info(f"DEVICE: {device} - RESTCONF : Discovering EIGRP Neighbors - SUCCESS")
        except:
            tb = self.get_traceback()
            self.log.info(f"DEVICE: {device} - SSH : ERROR discover_eigrp_neighbors - {tb}")


    def discover_eigrp_neighbors_restconf(self):
        return None

    def discover_eigrp_neighbors_ssh(self, device):

        try:
            self.log.info("GETTING DEVICE TYPE IN EIGRP NEIGHBORS SSH")
            os = self.get_device_type(device)
            self.log.info("GOT DEVICE TYPE  FROM get_device_type func IN EIGRP NEIGHBORS SSH_top")
            if os:
                self.log.info("GOT DEVICE TYPE  FROM get_device_type func IN EIGRP NEIGHBORS SSH")
                nm_args = self.netmiko_args_template.copy()
                nm_args['host'] = device
                nm_args['device_type'] = os


            else:
                os = "cisco_ios"
                nm_args = self.netmiko_args_template.copy()
                nm_args['host'] = device
                nm_args['device_type'] = os
                #raise Exception("Unable to determine OS.")
                self.log.info("GOT DEVICE TYPE IN EIGRP NEIGHBORS SSH")

            self.log.info("CREATING NETMIKO OBJ : discover_eigrp_neighbors_ssh")
            dev = ConnectHandler(**nm_args)
            self.log.info("CREATED NETMIKO OBJ : discover_eigrp_neighbors_ssh")

            dev.enable()


            if os in ['cisco_ios', 'cisco_nxos']:
                eigrp_output = dev.send_command("show ip eigrp neighbors vrf all") #textfsm not currently supported for this command
            elif os in ['cisco_xr']:
                eigrp_output = dev.send_command(
                    "show eigrp neighbors")  # textfsm not currently supported for this command
                if isinstance(eigrp_output, str):
                    neighbor_ips = re.findall('\d+\.\d+\.\d+\.\d+', eigrp_output)
                    self.log.info(f"{device}: EIGRP NEIGHBOR IPs - {neighbor_ips}")
                for i in self.topology['devices']:
                    if i['inventory_ip'] == device:
                        i['dynamic_routing_neighbors']['eigrp'] = neighbor_ips
                        break
            else:
                dev.disconnect()
                raise Exception(f"OS {os} Not supported")
            dev.disconnect()
        except:
            self.log.info("HIT EXCEPT discover_eigrp_neighbors_ssh")
            tb = self.get_traceback()
            self.log.info(f"DEVICE: {device} - SSH : discover_eigrp_neighbors_ssh - {tb}")



    def discover_bgp_neighbors(self, device):
        pass

    def discover_ospf_neighbors_via_ssh(self, session):

        pass

    def discover_ospf_neighbors_via_restconf(self):
        pass

    def get_inv_yaml_obj(self):

        if not self.inventory_file:
            self.inventory_file = "inventory.yml"

        path = Path(self.inventory_file)
        if not path.is_file():
            print(f"Unable to find inventory file {self.inventory_file}")
            return None

        with open(self.inventory_file, 'r') as file:
            try:
                # Converts yaml document to python object
                inventory_object = yaml.safe_load(file)
                return inventory_object

            except yaml.YAMLError as e:
                print(f"YAML ERROR: {e}")

    def _load_inventory(self):
        self.pbar_update_int = 100 / len(self.inventory_object[self.site]) / 4 # CAN"T BE ODD SO GO UP ONE IF SO, 3 is the number of jobs each device hits CURRENTLY
        for ip in self.inventory_object[self.site]:
            self._devices_to_query.put(ip)


    def _discover_lldp_neighbors_by_restconf(self, device):
        try:
            lldp_neighbors = self._get_lldp_neighbors_restconf(device)

            for i in self.topology['devices']:
                if i['inventory_ip'] == device:
                    i['hostname'] = lldp_neighbors['hostname']
                    lldp_neighbors.pop('hostname')
                    i['layer2'] = lldp_neighbors
                    break

            self._devices_queried.append(device)
        except:
            return False

        return True

    def _discover_lldp_neighbors_by_ssh(self, device):

        try:
            self.log.info(f"DEVICE: {device} - SSH : GETTING DEVICE TYPE : _discover_lldp_neighbors_by_ssh")
            os = self.get_device_type(device)
            self.log.info(f"DEVICE: {device} - SSH : GOT DEVICE TYPE : _discover_lldp_neighbors_by_ssh")
            netmiko_args = {"device_type": os,
                            "host": device,
                            "username": self.username,
                            "password": self.password,
                            "secret": self.password,
                            }


                # try:
                #     if not netmiko_args['device_type']:
                #         # Later put in unable to find OS
                #         netmiko_args['device_type'] = "cisco_ios"
                #     dev = ConnectHandler(**netmiko_args)
                #     dev.enable()
                # except Exception:
                #     tb = self.get_traceback()
                #     self.log.info(f"DEVICE: {device} - SSH : ERROR DISCOVER LLDP NEIGHBORS - {tb}")


                # CONN_SET = True
                # os = self._get_os_version(dev)
                # netmiko_args['device_type'] = os

            self.log.info(f"DEVICE: {device} - SSH : CREATING NETMIKO OBJ : _discover_lldp_neighbors_by_ssh")
            dev = ConnectHandler(**netmiko_args)
            self.log.info(f"DEVICE: {device} - SSH : CREATED NETMIKO OBJ : _discover_lldp_neighbors_by_ssh")
            self.log.info(f"DEVICE: {device} - SSH : SETTING ENABLE")

            dev.enable()
            self.log.info(f"DEVICE: {device} - SSH : ENABLE SET")

            try:
                lldp_nei_json = self._get_lldp_neighbors_ssh_textfsm(dev)

                if type(lldp_nei_json) == str:
                    raise ValueError("LLDP NEIGHBORS ARE STRs. Try without textfsm")
            except ValueError as e:
                try:
                    lldp_nei_json = self._get_lldp_neighbors_ssh_regex(dev)
                except:
                    tb = self.get_traceback()
                    self.log.info(f"DEVICE: {device} EXCEPTION22 IN _discover_lldp_neighbors_by_ssh: {tb}")
            except:
                tb = self.get_traceback()
                self.log.info(f"DEVICE: {device} - SSH : ERROR DISCOVER LLDP NEIGHBORS - {tb}")

            for i in self.topology["devices"]:
                if i['inventory_ip'] == device:
                    i['hostname'] = lldp_nei_json['hostname']
                    lldp_nei_json.pop("hostname")
                    i['layer2'] = lldp_nei_json
                    break

            dev.disconnect()
            self._devices_queried.append(device)
        except:
            tb = self.get_traceback()
            self.log.info(f"EXCEPTION01 THROWN IN _discover_lldp_neighbors_by_ssh : {tb}")


    def _create_netmiko_session(self, netmiko_kargs):

        return ConnectHandler(**netmiko_kargs)


    def _get_chassis_ids(self, netmiko_session=None, os=None, restconf_session=None):


        if not netmiko_session and restconf_session:

            try:
                resp = restconf_session.get(f"{restconf_session.base_url}/openconfig-interfaces:interfaces")
            except:
                tb = self.get_traceback()
                self.log.info(f"DEVICE: {restconf_session.base_url} EXCEPTION01 THROWN IN _get_chassis_ids : {tb}")
                #print(tb) LOG THIS

            if resp.status_code == 200:
                return  [i['ethernet']['state']['hw-mac-address']
             for i in resp.json()['interfaces']['interface']
             if 'ethernet' in i.keys() if 'state' in i['ethernet'].keys()
             if 'hw-mac-address' in i['ethernet']['state'].keys()]

            return None


        elif netmiko_session.device_type in ["cisco_nxos", "cisco_xe", "cisco_ios"]:
            output = netmiko_session.send_command("sh interface | inc bia ")
            re_resp = re.findall(
                '(?<=bia\s)[a-f\d][a-f\d][a-f\d][a-f\d]\.[a-f\d][a-f\d][a-f\d][a-f\d]\.[a-f\d][a-f\d][a-f\d][a-f\d]',
                output)

            # PC'S CARRY OVER ETHERNET MAC, SO THIS WOULD CHANGE IF PORT FAILED OVER TO OTHER MEMBERS AND THIS FIXES
            #THAT BY REMOVING DUPLICATES

            chassis_ids = []
            [chassis_ids.append(i) for i in re_resp if i not in chassis_ids]
            return chassis_ids

        elif netmiko_session.device_type == "cisco_xr":
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
        session = requests.session()
        session.auth = (os.environ['DYAGRAM_USERNAME'], os.environ['DYAGRAM_PASSWORD'])
        session.headers = headers
        session.verify = False
        session.base_url = f"https://{device}/restconf/data"

        #first try OpenConfig YANG
        self.log.info(f"DEVICE: {device} - RESTCONF-OPENCONFIG : Querying lldp for device - START")
        oc_yang_resp = session.get(f"{session.base_url}/openconfig-lldp:lldp/interfaces/")
        if oc_yang_resp.status_code != 200:
            self.log.info(f"DEVICE: {device} - RESTCONF-OPENCONFIG : Querying lldp for device - FAILURE")
            oc_yang_resp.raise_for_status()
        self.log.info(f"DEVICE: {device} - RESTCONF-OPENCONFIG : Querying lldp for device - SUCCESSFUL")



        lldp_info_json = {"hostname": self._get_hostname(restconf_session=session),
                          "chassis_ids": self._get_chassis_ids(restconf_session=session),
                          "neighbors": []}

        try:
            for intf in oc_yang_resp.json()['interfaces']['interface']:
                if 'neighbors' in intf.keys():

                    neighbor_info = self.lldp_neighbor_template.copy()
                    neighbor_info['hostname'] = intf['neighbors']['neighbor'][0]['state']['system-name']
                    neighbor_info['local_port'] = intf['name']
                    neighbor_info['neighbor_port'] = intf['neighbors']['neighbor'][0]['state']['port-id']
                    neighbor_info['chassis_id'] = intf['neighbors']['neighbor'][0]['state']['chassis-id']
                    lldp_info_json['neighbors'].append(neighbor_info)

        except:
            tb = self.get_traceback()
            self.log.info(f"DEVICE: {device} EXCEPTION01 THROWN IN _get_lldp_neighbors_restconf : {tb}")

            #print(tb)

        if oc_yang_resp.status_code == 200:
            return lldp_info_json
        raise Exception("UNABLE TO USE RESTCONF")


    def _get_lldp_neighbors_ssh_textfsm(self, netmiko_session):
        #os = self._get_os_version(netmiko_session)
        os = netmiko_session.device_type

        lldp_neighbors_output = netmiko_session.send_command("show lldp neighbors det", use_textfsm=True)
        if type(lldp_neighbors_output) == str:
            return lldp_neighbors_output

        lldp_info_json = {"hostname": self._get_hostname(netmiko_session),
                         "chassis_ids": self._get_chassis_ids(netmiko_session, os),
                         "neighbors": []}



        for neighbor in lldp_neighbors_output:
            neighbor_info = self.lldp_neighbor_template.copy()
            neighbor_info['hostname'] = neighbor['neighbor']
            neighbor_info['local_port'] = neighbor['local_interface']
            neighbor_info['neighbor_port'] = neighbor['neighbor_interface']
            neighbor_info['chassis_id'] = neighbor['chassis_id']
            lldp_info_json['neighbors'].append(neighbor_info)

        return lldp_info_json

    def _get_lldp_neighbors_ssh_regex(self, netmiko_session):

        # os = self._get_os_version(netmiko_session)
        os = netmiko_session.device_type

        lldp_neighbors_output = netmiko_session.send_command("show lldp neighbors det")
        cdp_info_json = {"hostname": self._get_hostname(netmiko_session),
                         "chassis_ids": self._get_chassis_ids(netmiko_session),
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

    def _get_hostname(self, netmiko_session=None, restconf_session=None):

        try:
            if not netmiko_session and restconf_session:
                try:
                    device = re.search('\d+\.\d+\.\d+\.\d+', restconf_session.base_url).group(1)
                except:
                    device = restconf_session.base_url

                try:
                    self.log.info(f"DEVICE: {device} - RESTCONF_OPENCONFIG : Querying for hostname - START")
                    resp = restconf_session.get(f"{device}/openconfig-system:system/config/name")
                    if resp.status_code == 200:
                        self.log.info(f"DEVICE: {device} - RESTCONF_OPENCONFIG : Querying hostname - SUCCESSFUL")
                        return resp.json()['hostname']
                    if resp.status_code != 200:
                        self.log.info(
                            f"DEVICE: {device} - RESTCONF_OPENCONFIG : Querying hostname - FAILURE")
                        # try nexus TEMPORARY
                        self.log.info(
                            f"DEVICE: {device} - RESTCONF_NXOS_OS_DEVICE_YANG : Querying hostname - START")
                        resp = restconf_session.get(f"{device}/Cisco-NX-OS-device:System/name")

                        if resp.status_code == 200:
                            self.log.info(
                                f"DEVICE: {device} - RESTCONF_NXOS_OS_DEVICE_YANG : Querying hostname - SUCCESSFUL")
                            return resp.json()['name']
                        self.log.info(
                            f"DEVICE: {device} - RESTCONF_NXOS_OS_DEVICE_YANG : Querying hostname - FAILURE")

                except:

                    tb = self.get_traceback()
                    self.log.info(
                        f"DEVICE: {device} - RESTCONF_OPENCONFIG_AND_NXOS_OS_DEVICE_YANG_CATCHALL : Querying hostname - FAILURE - TB: {tb}")

            else:
                self.log.info(f"DEVICE: {netmiko_session.host} - SSH : Querying for hostname - START")
                sh_run_output = netmiko_session.send_command("sh run | inc hostname")
                hostname = re.search("hostname\s+(.*)", sh_run_output).group(1)
                self.log.info(f"DEVICE: {netmiko_session.host} - SSH : Querying for hostname - SUCCESSFUL")

                return hostname
            return None
        except:
            tb = self.get_traceback()
            self.log.info(f"DEVICE: {device} EXCEPTION THROWN IN _get_hostname : {tb}")


    def _get_os_version(self, netmiko_session):

        sh_version_output = netmiko_session.send_command("show version")
        if "IOS-XE" in sh_version_output:
            return "cisco_xe"
        elif "NX-OS" in sh_version_output:
            return "cisco_nxos"
        elif "IOS XR" in sh_version_output:
            return "cisco_xr"

        return None


    def _get_lldp_neighbor_regex_strings(self, os):

        regex = {"cisco_xe":
                     {"system_name": r"(?<=System Name:\s).*",
                      "local_interface": r"(?<=Local Intf:\s).*",
                      "neighbor_interface": r"(?<=Port id:\s).*",
                      "chassis_id": r"(?<=^Chassis id:\s).*"},

                 "cisco_nxos":
                     {"system_name": r"(?<=System Name:\s).*",
                      "local_interface": r"(?<=Local Port id:\s).*",
                      "neighbor_interface": r"(?<=^Port id:\s).*",
                      "chassis_id": r"(?<=^Chassis id:\s).*"

                      },
                 "cisco_xr":
                     {"system_name": r"(?<=System Name:\s).*",
                      "local_interface": r"(?<=Local Interface:\s).*",
                      "neighbor_interface": r"(?<=^Port id:\s).*",
                      "chassis_id": r"(?<=^Chassis id:\s).*"
                      }
                 }

        return regex[os]



def main():

    import argparse
    try:
        parser = argparse.ArgumentParser()

        parser.add_argument('dyagram_args', nargs='*')
        parser.add_argument("-v", action='store_true', dest='verbose')

        args = parser.parse_args()

        if args.dyagram_args[0].lower() == "init":
            from dyagram.cli import initialize
            dyinit = initialize.dyagramInitialize()
            dyinit.dy_init()

        if args.dyagram_args[0].lower() == "discover":
            dy = dyagram(verbose=args.verbose)
            dy.discover()


        if args.dyagram_args[0].lower() == "site":
            from dyagram.cli import sites
            s = sites()
            if len(args.dyagram_args) == 1:
                s.list_sites_in_cli()
            elif len(args.dyagram_args) > 1:
                if args.dyagram_args[1].lower() == "new":
                    try:
                        s.make_new_site(args.dyagram_args[2])
                    except:
                        print("Missing argument : <site>")
                if args.dyagram_args[1].lower() == "switch":
                    try:
                        s.switch_site(args.dyagram_args[2].lower())
                    except:
                        print(f"Site {args.dyagram_args[2]} doesn't exist")
    except:
        tb = dyagram.get_traceback()
        print(f"DEVICE: MAIN EXCEPTION : {tb}")


if __name__ == "__main__":
    main()

