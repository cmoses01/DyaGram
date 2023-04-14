import os
import json
from colorama import Fore

class sites:

    def __init__(self):
        self.sites = self.get_sites()


    def get_sites(self):
        return [folder.name for folder in os.scandir() if folder.is_dir() and folder.name not in ['.info']]

    def make_new_site(self, name):
        if name in self.sites:
            print(f'Site "{name}" already exists.')
        else:
            os.mkdir(f'{name}')
            print(f'Site "{name}" created!')

    @staticmethod
    def get_current_site():
        try:
            file = open(r".info/info.json", 'r')
            info = json.load(file)
            return info['current_site']
        except:
            print("Unable to load last site.")

    def list_sites_in_cli(self):
        """
        cli command: dyagram site
        :return:
        """

        current_site = self.get_current_site()
        sites = self.get_sites()

        for site in sites:

            if site == current_site:
                print(Fore.LIGHTGREEN_EX + f"* {site}" + Fore.RESET)

            else:
                print(f"  {site}")

    def switch_site(self, site):
        sites = self.get_sites()
        if site in sites:
            with open('.info/info.json', 'w') as f:
                import json

                x = {"current_site": site}
                json.dump(x,f)
        else:
            raise








