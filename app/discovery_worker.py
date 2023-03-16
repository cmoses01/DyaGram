from dyagram.dyagram import dyagram

inventory = r"C:\Users\chrimos\PycharmProjects\DyaGram\app\inventory.yml"

# main code

dyagram = dyagram(inventory, new_state=True)
dyagram.discover()