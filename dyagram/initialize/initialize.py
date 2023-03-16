import os

class dyagramInitialize:

    def __init__(self, site):
        self.clean = None
        self.has_init_been_ran()
        if not self.clean:
            raise Exception('DyaGram is already initialized')
        self.site = site


    def has_init_been_ran(self):
        dir = os.listdir()
        if '.info' in dir:
            self.clean = False
            return True
        self.clean = True
        return False

    def make_dyagram_folder_structure(self):
        os.mkdir(self.site)
        os.mkdir('.info')
        with open('.info/info.json', 'w') as f:
            import json
            x = {"current_site": self.site}
            json.dump(x,f)


def main(site=None):
    if not site:
        raise Exception("Site not defined")
    try:
        dyinit = dyagramInitialize(site)
        dyinit.make_dyagram_folder_structure()
        print(f"Created site: {site}")
    except Exception as e:
        print(e)

    print("\n\nDyaGram initialized!\n")


