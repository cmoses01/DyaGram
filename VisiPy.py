import win32com.client


class visipy:
    def __init__(self , template=None):
        self.visio_obj = win32com.client.Dispatch("Visio.InvisibleApp")
        self.template = "Basic Diagram.vss" if self.template == None else template


        self._validate_template()


    def _validate_template(self):
        pass #add later


    class visio_diagram():
        def __init__(self):
            self.doc = self.visio_obj.Documents.Add(self.template)


