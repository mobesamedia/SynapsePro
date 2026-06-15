# -*- coding: utf-8 -*-

try:
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QDialogButtonBox
    from PyQt6.QtCore import Qt
except ImportError:
    from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QDialogButtonBox
    from PyQt5.QtCore import Qt

try:
    from .locales import _
except ImportError:
    def _(text):  # type: ignore
        return text

HELP_TEXT = """
<h2>Troubleshooting & Manual Removal</h2>
<p>If you are unable to activate the addon or close Anki, you can manually remove SynapsePro to regain access.</p>

<b>Follow these steps:</b>
<ol>
    <li>Close this window and click the "Quit Anki" button in the activation dialog. If that fails, force-quit Anki (e.g., via Activity Monitor on Mac or Task Manager on Windows).</li>
    <li>Open Anki while holding down the <b>Shift key</b>. This will temporarily disable all addons.</li>
    <li>Go to <b>Tools > Add-ons</b> from the Anki menu.</li>
    <li>Select "SynapsePro" from the list.</li>
    <li>Click the "Delete" button on the right side.</li>
    <li>Restart Anki normally.</li>
</ol>

<p>If you believe your key is valid but not working, or for any other issues, please contact us:</p>
<p><a href='mailto:help.synapse.pro@gmail.com'>help.synapse.pro@gmail.com</a></p>
"""

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("SynapsePro - Help"))
        self.setMinimumWidth(500)

        layout = QVBoxLayout()

        label = QLabel(_(HELP_TEXT))
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)

        layout.addWidget(label)
        layout.addWidget(button_box)

        self.setLayout(layout)

