import re

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QFrame, QPushButton, QHBoxLayout, QWidget

from pyqt_openai.res.language_dict import LangClass
from pyqt_openai.sqlite import SqliteDatabase


class PromptGroupInputDialog(QDialog):
    def __init__(self, db: SqliteDatabase, parent=None):
        super().__init__(parent)
        self.__initVal(db)
        self.__initUi()

    def __initVal(self, db):
        self.__db = db

    def __initUi(self):
        self.setWindowTitle('New Prompt')
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)

        self.__newName = QLineEdit()
        self.__newName.textChanged.connect(self.__setAccept)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)

        self.__okBtn = QPushButton(LangClass.TRANSLATIONS['OK'])
        self.__okBtn.clicked.connect(self.accept)

        cancelBtn = QPushButton(LangClass.TRANSLATIONS['Cancel'])
        cancelBtn.clicked.connect(self.close)

        lay = QHBoxLayout()
        lay.addWidget(self.__okBtn)
        lay.addWidget(cancelBtn)
        lay.setAlignment(Qt.AlignRight)
        lay.setContentsMargins(0, 0, 0, 0)

        okCancelWidget = QWidget()
        okCancelWidget.setLayout(lay)

        lay = QVBoxLayout()
        lay.addWidget(self.__newName)
        lay.addWidget(sep)
        lay.addWidget(okCancelWidget)

        self.setLayout(lay)

    def getPromptGroupName(self):
        return self.__newName.text()

    def __setAccept(self, text):
        m = re.search('^[a-zA-Z_0-9]+$', text)
        names = [obj[1] for obj in self.__db.selectPropPromptGroup()+self.__db.selectTemplatePromptGroup()]
        f = (True if m else False) and text not in names
        self.__okBtn.setEnabled(f)
