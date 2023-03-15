from dyagram.modules.dyagram import dyagram

inventory = r"C:\Users\chrimos\PycharmProjects\DyaGram\app\inventory.yml"

# main code

dyagram = dyagram(inventory)
dyagram.discover()