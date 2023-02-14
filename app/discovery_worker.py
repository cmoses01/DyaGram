from modules.discovery import discovery


dev_user = "cisco"
dev_pw = "cisco"
exit_routers = {
	"routers": [{
		"mgmt_ip": "10.10.20.176",
		"exit_interfaces": ["gig2"]
	}]
}


starting_device = {"device_type": "cisco_ios_telnet",
          "host": "10.10.20.176",
          "username": dev_user,
          "password": dev_pw}


discovery = discovery(starting_device, r"C:\Users\chrimos\PycharmProjects\DyaGram\app\db.json")


cdp_neighbors = discovery.get_cdp_neighbors()
print(cdp_neighbors)




