import os


class sites:
    def __init__(self):
        self.current_sites = self.load_current_sites()

    def load_current_sites(self):
        return os.listdir('sites')

    def make_new_site(self, name):
        if name in self.current_sites:
            print(f'Site "{name}" already exists.')
        else:
            os.mkdir(f'sites/{name}')
            print(f'Site "{name}" created!')