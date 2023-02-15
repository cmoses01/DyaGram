from modules.dyagram import dyagram


dev_user = "cisco"
dev_pw = "cisco"
exit_routers = {
	"routers": [{
		"mgmt_ip": "10.10.20.176",
		"exit_interfaces": ["gig2"]
	}]
}
DB_LOCATION = r"C:\Users\chrimos\PycharmProjects\DyaGram\app\db.json"

starting_device = {"device_type": "cisco_ios_telnet",
          "host": "10.10.20.176",
          "username": dev_user,
          "password": dev_pw}


if __name__ == "__main__":
	dyagram = dyagram(starting_device, DB_LOCATION)
	dyagram.discover_topology()
	print(dyagram.topology)



