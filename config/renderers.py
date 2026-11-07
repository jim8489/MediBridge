
from rest_framework.renderers import BaseRenderer


class PDFRenderer(BaseRenderer):
    """
    Allows DRF content negotiation to accept PDF downloads.

    FileResponse streams the actual PDF, so this renderer
    does not need to generate the PDF itself.
    """

    media_type = "application/pdf"
    format = "pdf"
    charset = None
    render_style = "binary"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b""

        return data
