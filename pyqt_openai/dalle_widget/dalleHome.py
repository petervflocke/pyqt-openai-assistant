from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from pyqt_openai import CONTEXT_DELIMITER, LARGE_LABEL_PARAM, MEDIUM_LABEL_PARAM


class DallEHome(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__initUi()

    def __initUi(self):
        title = QLabel("Welcome to DALL-E Page !", self)
        title.setFont(QFont(*LARGE_LABEL_PARAM))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        description = QLabel("Generate images with DALL-E." + CONTEXT_DELIMITER)

        description.setFont(QFont(*MEDIUM_LABEL_PARAM))
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay = QVBoxLayout()
        lay.addWidget(title)
        lay.addWidget(description)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(lay)

        mainWidget = QWidget()
        mainWidget.setLayout(lay)
        self.setWidget(mainWidget)
        self.setWidgetResizable(True)
