from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QRadioButton,
    QVBoxLayout,
)

from pyqt_openai.lang.translations import LangClass


class SelectChatImportTypeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__initVal()
        self.__initUi()

    def __initVal(self):
        self.__selected_import_type = None

    def __initUi(self):
        self.setWindowTitle(LangClass.TRANSLATIONS["Import From..."])
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)

        self.__generalRadBtn = QRadioButton(LangClass.TRANSLATIONS["General"])
        self.__chatGptRadBtn = QRadioButton(LangClass.TRANSLATIONS["ChatGPT"])

        self.__generalRadBtn.setChecked(True)

        self.__buttonGroup = QButtonGroup()
        self.__buttonGroup.addButton(self.__generalRadBtn, 1)
        self.__buttonGroup.addButton(self.__chatGptRadBtn, 2)

        lay = QVBoxLayout()
        lay.addWidget(self.__generalRadBtn)
        lay.addWidget(self.__chatGptRadBtn)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        importTypeGrpBox = QGroupBox(LangClass.TRANSLATIONS["Import Type"])
        importTypeGrpBox.setLayout(lay)

        buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        lay = QVBoxLayout()
        lay.addWidget(importTypeGrpBox)
        lay.addWidget(buttonBox)

        self.setLayout(lay)

    def getImportType(self):
        selected_button_id = self.__buttonGroup.checkedId()
        if selected_button_id == 1:
            return "general"
        if selected_button_id == 2:
            return "chatgpt"
        return None
