from modules.dyagram import dyagram

DB_LOCATION = r"C:\Users\chrimos\PycharmProjects\DyaGram\app\db.json"


init_file = r"C:\Users\chrimos\PycharmProjects\DyaGram\app\inventory.yml"

# main code

dyagram = dyagram(init_file,DB_LOCATION)
dyagram.discover()



print(dyagram.topology)




