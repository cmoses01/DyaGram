from diagrams import Diagram, Cluster
from diagrams.aws.network import ELB
import os
import json
from dyagram.cli.sites import sites

os.environ["PATH"] += os.pathsep + r'C:\Program Files\Graphviz\bin'
# FIXME: MUST HAVE GRAPHVIZ INSTALLED TO RUN


class DiagramExport:

    def __init__(self):

        self.current_site = sites.get_current_site()
        self.state = self.load_state()


    def load_state(self):
        file = open(rf"{self.current_site}/state.json", 'r')
        state = json.load(file)
        file.close()
        return state

    def export(self):
        with Diagram(self.current_site, show=False, filename=f'{self.current_site}/{self.current_site}_diagram.png'):
            with Cluster(" "):  #  makes a pretty background lol

                graph_info = []  # object, hostname, neighbor_obj

                for n, val in enumerate(self.state['devices']):
                    locals()[f"var{n}"] = ELB(val['hostname'])
                    graph_info.append({"object": locals()[f"var{n}"], "inventory_ip": val['inventory_ip'],
                                       "chassis_ids": val['layer2']["chassis_ids"], "neighbor_objects": []})

                for device in self.state['devices']:
                    for neighbor in device['layer2']['neighbors']:
                        for dev in self.state['devices']:
                            if neighbor['chassis_id'] in dev['layer2']['chassis_ids']:
                                for i in graph_info:
                                    if i['inventory_ip'] == device['inventory_ip']:
                                        for x in graph_info:
                                            if neighbor['chassis_id'] in x['chassis_ids']:
                                                i['neighbor_objects'].append(x['object'])

                for device in graph_info:
                    for neighbor in device['neighbor_objects']:
                        device['object'] - neighbor
