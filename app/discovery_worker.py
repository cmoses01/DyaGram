from modules.dyagram import dyagram

init_file = r"C:\Users\chrimos\PycharmProjects\DyaGram\app\inventory.yml"

# main code

dyagram = dyagram(init_file)
dyagram.discover()



print(dyagram.topology)




