import os
import time
from pathlib import Path
import yaml
from colorama import Fore
from tqdm import tqdm

class dyagramInitialize:

    def __init__(self, site=None):
        self.pbar = None
        self.pbar_update_int = None
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

    def get_sites_from_inventory(self):

        sites = []
        with open('inventory.yml', 'r') as file:
            try:
                # Converts yaml document to python object
                inventory_object = yaml.safe_load(file)


            except yaml.YAMLError as e:
                print(e)
        for site in inventory_object:
            sites.append(site)
        self.pbar_update_int = 100 / len(inventory_object)
        return sites


    def make_dyagram_folder_structure(self):

        path = Path('inventory.yml')
        if path.is_file():
            sites = self.get_sites_from_inventory()
            for site in sites:
                os.mkdir(site)
                self.pbar.update(self.pbar_update_int)
            self.site = sites[0]
        else:
            self.site = input("Site Name: ")
            os.mkdir(self.site)
            print(f"Created site: {self.site}")

        os.mkdir('.info')
        with open('.info/info.json', 'w') as f:
            import json
            x = {"current_site": self.site}
            json.dump(x,f)

    def dy_init(self):
        # function called when command dyagram init is called
        print('DyaGram initializing')
        self.pbar = tqdm(total=100,
                         bar_format=Fore.LIGHTBLUE_EX + "{l_bar}{bar:20}|")
        try:
            self.make_dyagram_folder_structure()
        except Exception as e:
            print(e)

        self.pbar.close()



