import win32com.client
from win32com.client import constants

appVisio = win32com.client.Dispatch("Visio.InvisibleApp")
#appVisio = win32com.client.Dispatch("Visio.Application")


doc = appVisio.Documents.Add("Basic Diagram.vst")


pages = appVisio.ActiveDocument.Pages

page = pages.item(1)
stn = appVisio.Documents("Basic Shapes.vss")
mast = stn.Masters("Rectangle")
shp = page.Drop(mast, 4.25, 5.5)

shp.Text = "Hello TAYLER BOO!"

doc.SaveAs(r"C:\Users\chrimos\PycharmProjects\DyaGram\testpythonvisio.vsdx")
doc.Close()
appVisio.Quit()

