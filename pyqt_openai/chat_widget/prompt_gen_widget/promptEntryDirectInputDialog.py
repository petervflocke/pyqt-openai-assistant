from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyqt_openai.lang.translations import LangClass
from pyqt_openai.util.common import getSeparator, is_prompt_entry_name_valid


class PromptEntryDirectInputDialog(QDialog):
    def __init__(self, group_id, parent=None):
        super().__init__(parent)
        self.__initVal(group_id)
        self.__initUi()

    def __initVal(self, group_id):
        self.__group_id = group_id

    def __initUi(self):
        self.setWindowTitle(LangClass.TRANSLATIONS["New Prompt"])
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)

        self.__name = QLineEdit()
        self.__name.setPlaceholderText(LangClass.TRANSLATIONS["Name"])

        self.__content = QPlainTextEdit()
        self.__content.setPlaceholderText(LangClass.TRANSLATIONS["Content"])

        sep = getSeparator("horizontal")

        self.__okBtn = QPushButton(LangClass.TRANSLATIONS["OK"])
        self.__okBtn.clicked.connect(self.__accept)

        cancelBtn = QPushButton(LangClass.TRANSLATIONS["Cancel"])
        cancelBtn.clicked.connect(self.close)

        lay = QHBoxLayout()
        lay.addWidget(self.__okBtn)
        lay.addWidget(cancelBtn)
        lay.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.setContentsMargins(0, 0, 0, 0)

        okCancelWidget = QWidget()
        okCancelWidget.setLayout(lay)

        lay = QVBoxLayout()
        lay.addWidget(self.__name)
        lay.addWidget(self.__content)
        lay.addWidget(sep)
        lay.addWidget(okCancelWidget)

        self.setLayout(lay)

    def getAct(self):
        return self.__name.text()

    def getPrompt(self):
        return self.__content.toPlainText()

    def __accept(self):
        exists_f = is_prompt_entry_name_valid(self.__group_id, self.__name.text())
        if exists_f:
            self.__name.setFocus()
            QMessageBox.warning(  # type: ignore[call-arg]
                self,
                LangClass.TRANSLATIONS["Warning"],
                LangClass.TRANSLATIONS["Entry name already exists."],
            )
            return
        self.accept()
