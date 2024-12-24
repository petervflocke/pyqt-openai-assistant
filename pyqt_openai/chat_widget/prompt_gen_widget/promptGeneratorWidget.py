from __future__ import annotations

import pyperclip

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from pyqt_openai.chat_widget.prompt_gen_widget.promptPage import PromptPage
from pyqt_openai.lang.translations import LangClass


class PromptGeneratorWidget(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__initUi()

    def __initUi(self):
        promptLbl = QLabel(LangClass.TRANSLATIONS["Prompt"])

        formPage = PromptPage(prompt_type="form")
        formPage.updated.connect(self.__textChanged)

        sentencePage = PromptPage(prompt_type="sentence")
        sentencePage.updated.connect(self.__textChanged)

        self.__prompt = QTextBrowser()
        self.__prompt.setPlaceholderText(LangClass.TRANSLATIONS["Generated Prompt"])
        self.__prompt.setAcceptRichText(False)

        promptTabWidget = QTabWidget()
        promptTabWidget.addTab(formPage, LangClass.TRANSLATIONS["Form"])
        promptTabWidget.addTab(sentencePage, LangClass.TRANSLATIONS["Sentence"])

        previewLbl = QLabel(LangClass.TRANSLATIONS["Preview"])

        copyBtn = QPushButton(LangClass.TRANSLATIONS["Copy"])
        copyBtn.clicked.connect(self.__copy)

        lay = QVBoxLayout()
        lay.addWidget(promptLbl)
        lay.addWidget(promptTabWidget)

        topWidget = QWidget()
        topWidget.setLayout(lay)

        lay = QVBoxLayout()
        lay.addWidget(previewLbl)
        lay.addWidget(self.__prompt)
        lay.addWidget(copyBtn)

        bottomWidget = QWidget()
        bottomWidget.setLayout(lay)

        mainSplitter = QSplitter()
        mainSplitter.addWidget(topWidget)
        mainSplitter.addWidget(bottomWidget)
        mainSplitter.setOrientation(Qt.Orientation.Vertical)
        mainSplitter.setChildrenCollapsible(False)
        mainSplitter.setHandleWidth(2)
        mainSplitter.setStyleSheet(
            """
            QSplitter::handle:vertical
            {
                background: #CCC;
                height: 1px;
            }
            """,
        )

        self.setWidget(mainSplitter)
        self.setWidgetResizable(True)

        self.setStyleSheet("QScrollArea { border: 0 }")

    def __textChanged(self, prompt_text):
        self.__prompt.clear()
        self.__prompt.setText(prompt_text)

    def __copy(self):
        pyperclip.copy(self.__prompt.toPlainText())
