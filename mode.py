# -*- coding: utf-8 -*-
import os
from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo

try:
    from .locales import _
except ImportError:
    def _(text):  # type: ignore
        return text

class ThemeChangeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Restart Required"))
        self.setMinimumWidth(360)

        layout = QVBoxLayout()

        # --- Bild Logik (OBEN) ---
        addon_path = os.path.dirname(__file__)
        image_path = os.path.join(addon_path, "media", "mode.png")

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                if pixmap.width() > 350:
                    scaled_pixmap = pixmap.scaledToWidth(
                        350,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    image_label.setPixmap(scaled_pixmap)
                else:
                    image_label.setPixmap(pixmap)

        layout.addWidget(image_label)

        layout.addSpacing(10)

        # --- Text Logik (UNTEN) ---
        label = QLabel(_(
            "<b>Theme Change Detected</b><br><br>"
            "You have switched between Light and Dark mode.<br>"
            "To ensure all SynapsePro UI elements and styles are applied correctly, "
            "please restart Anki."
        ))
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter) 
        
        layout.addWidget(label)
        
        layout.addSpacing(10)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        buttons.setCenterButtons(True) 
        layout.addWidget(buttons)
        
        self.setLayout(layout)

def show_restart_warning():
    """Zeigt den Dialog an."""
    if mw:
        d = ThemeChangeDialog(mw)
        d.exec()