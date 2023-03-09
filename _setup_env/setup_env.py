#enable lldp, cdp, RESTCONF
from netmiko import ConnectHandler

netmiko_args = {
    "device_type": "cisco_ios",
    "host": "",
    "username": "cisco",
    "password": "cisco"
}

ios_xr_routers = ['10.10.20.173']

nxos_switches = ['10.10.20.177', "10.10.20.178"]

# for r in ios_xr_routers:
#     netmiko_args['device_type'] = "cisco_xr_telnet"
#     netmiko_args['host'] = r
#     dev = ConnectHandler(**netmiko_args)
#     dev.send_config_set("lldp")
#     dev.send_command("crypto generate dsa")
#     dev.send_config_set("ssh server vrf Mgmt-intf")
#    # dev.send_config_set("cdp run")
#   #  dev.send_config_set("restconf")
#     dev.disconnect()



for s in nxos_switches:
    netmiko_args['device_type'] = "cisco_ios"
    netmiko_args['host'] = s
    dev = ConnectHandler(**netmiko_args)
    dev.send_config_set("feature lldp")
    dev.send_config_set("feature restconf")
    dev.send_config_set("feature nxapi")

# 5254.000a.4303