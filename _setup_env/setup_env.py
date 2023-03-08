#enable lldp, cdp, RESTCONF
from netmiko import ConnectHandler

netmiko_args = {
    "device_type": "cisco_ios",
    "host": "",
    "username": "cisco",
    "password": "cisco"
}

routers = ['10.10.20.176']

nxos_switches = ['10.10.20.177', "10.10.20.178"]

for r in routers:
    netmiko_args['host'] = r
    dev = ConnectHandler(**netmiko_args)
    dev.send_config_set("lldp run")
    dev.send_config_set("cdp run")
    dev.send_config_set("restconf")
    dev.send_config_set(['interface range gi4-5', "cdp enable"])
    dev.send_config_set(['interface range gi4-5', "lldp enable"])

    dev.disconnect()

for s in nxos_switches:
    netmiko_args['host'] = s
    dev = ConnectHandler(**netmiko_args)
    dev.send_config_set("feature lldp")
    dev.send_config_set("feature restconf")
    dev.send_config_set("feature nxapi")

