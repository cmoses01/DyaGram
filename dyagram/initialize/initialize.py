import os

class dyagramInitialize:

    def __init__(self, site):
        self.site = site

    def make_dyagram_folder_structure(self):
        os.mkdir(self.site)

def main(site=None):
    if not site:
        raise Exception("Site not defined")
    dyinit = dyagramInitialize(site)
    dyinit.make_dyagram_folder_structure()
    print(f"Created site: {site}")

