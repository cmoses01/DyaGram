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

starting_device = {"device_type": "cisco_ios",
          "host": "10.10.20.176",
          "username": dev_user,
          "password": dev_pw}

init_file = r"C:\Users\chrimos\PycharmProjects\DyaGram\app\inventory.yml"

# main code

dyagram = dyagram(init_file,DB_LOCATION)
dyagram.discover()



print(dyagram.topology)




