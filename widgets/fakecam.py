from pathlib import Path
from libqtile.images import Img
from typing import Optional, List, Tuple, Any
from libqtile import widget


Defaults = List[Tuple[str, Any, str]]

CURRENT_DIR = Path(__file__).absolute().parent
ASSET_DIR = CURRENT_DIR / "assets"


class FakecamWidget(widget.Image):

    defaults: Defaults = []

    def __init__(self, length: Optional[int] = None, **kwargs: Any) -> None:
        super().__init__(length, **kwargs)
        self.add_defaults(FakecamWidget.defaults)
        self.on_img = str(ASSET_DIR / "hal_on.png")
        self.off_img = str(ASSET_DIR / "hal_off.png")
