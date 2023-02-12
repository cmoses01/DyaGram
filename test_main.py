import win32com.client
import logging

logging.basicConfig(filename=r"C:\logs\dyagram_logs\main.log",
                    format='%(asctime)s %(message)s',
                    filemode='a')
logger = logging.getLogger()
logger.level = 10

from win32com.client import constants


def main():
    logger.debug("Creating Visio Diagram...")
    appVisio = win32com.client.Dispatch("Visio.InvisibleApp")
    # appVisio = win32com.client.Dispatch("Visio.Application")

    logger.debug("Loading template..")
    doc = appVisio.Documents.Add(
        r"C:\Users\chrimos\PycharmProjects\DyaGram\visio_data\visio_templates\main_template.vstx")
    logger.debug("Template loaded")

    logger.debug("Loading pages..")
    pages = appVisio.ActiveDocument.Pages
    logger.debug("Pages loaded")
    page = pages.item(1)

    logger.debug("Loading Stencils..")
    stn = appVisio.Documents(r"dyagram_favorites.vssx")
    logger.debug("Stencils loaded")

    router = stn.Masters("Router")
    switch = stn.Masters("Workgroup Switch")
    dynamic_connector = stn.Masters("Dynamic Connector")

    logger.debug("Dropping shapes..")
    shp_router = page.Drop(router, 5.5, 7)
    shp_switch = page.Drop(switch, 0, 0)

    shapes = page.Shapes
    logger.debug("Shapes dropped")

    logger.debug("Connecting shapes..")
    shp_router.AutoConnect(shp_switch, 2, dynamic_connector)
    connector1 = shapes.ItemU(len(shapes))
    connector1.Text = "Connector1"
    connector1.Cells("LineColor").FormulaForce = 3
    connector1.Cells("ConLineRouteExt").FormulaForce = 2
    logger.debug("Shapes connected")

    # shp.Text = "Hello TAYLER BOO!"
    logger.debug("Saving document...")
    doc.SaveAs(r"C:\Users\chrimos\downloads\nashville_office.vsdx")
    logger.debug("Document Saved")

    logger.debug("Closing Document..")
    doc.Close()
    logger.debug("Document closed")

    logger.debug("Quitting Visio..")
    appVisio.Quit()
    logger.debug("Visio closed")


if __name__ == "__main__":
    main()