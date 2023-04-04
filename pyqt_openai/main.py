import inspect
import json, webbrowser

import openai, requests, os, platform, subprocess

from chatWidget import Prompt, ChatBrowser

from notifier import NotifierWidget

from qtpy.QtCore import Qt, QCoreApplication, QThread, QSettings, QEvent, Signal
from qtpy.QtGui import QGuiApplication, QFont, QIcon, QColor, QCursor
from qtpy.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QWidget, QSplitter, QComboBox, QSpinBox, \
    QFormLayout, QDoubleSpinBox, QPushButton, QFileDialog, QToolBar, QWidgetAction, QHBoxLayout, QAction, QMenu, \
    QSystemTrayIcon, QMessageBox, QSizePolicy, QGroupBox, QLineEdit, QLabel, QCheckBox, QListWidgetItem

from pyqt_openai.apiData import getModelEndpoint, getLatestModel
from pyqt_openai.clickableTooltip import ClickableTooltip
from pyqt_openai.leftSideBar import LeftSideBar
from pyqt_openai.apiData import ModelData
from pyqt_openai.modelTable import ModelTable
from pyqt_openai.svgButton import SvgButton
from pyqt_openai.svgLabel import SvgLabel

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)  # HighDPI support
# qt version should be above 5.14
# todo check the qt version with qtpy
if os.environ['QT_API'] == 'pyqt5' or os.environ['QT_API'] != 'pyside6':
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

QApplication.setFont(QFont('Arial', 12))


class OpenAIThread(QThread):
    """
    == replyGenerated Signal ==
    First: response
    Second: user or AI
    Third: streaming a chat completion or not
    Forth: Image generation with DALL-E or not
    """
    replyGenerated = Signal(str, bool, bool, bool)

    def __init__(self, model, openai_arg, idx, remember_f, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__model = model
        self.__endpoint = getModelEndpoint(model)
        self.__openai_arg = openai_arg
        self.__remember_f = remember_f
        self.__idx = idx

    def run(self):
        try:
            if self.__idx == 0:
                if self.__endpoint == '/v1/chat/completions':
                    response = openai.ChatCompletion.create(
                           **self.__openai_arg
                    )
                    # if it is streaming, type will be generator
                    if inspect.isgenerator(response):
                        for chunk in response:
                            delta = chunk['choices'][0]['delta']
                            response_text = delta.get('content', '')
                            if response_text:
                                self.replyGenerated.emit(response_text, False, True, False)
                            else:
                                finish_reason = chunk['choices'][0].get('finish_reason', '')
                                if finish_reason:
                                    print(finish_reason)
                    else:
                        response_text = response['choices'][0]['message']['content']
                        self.replyGenerated.emit(response_text, False, False, False)
                elif self.__endpoint == '/v1/completions':
                    openai_object = openai.Completion.create(
                        **self.__openai_arg
                    )

                    response_text = openai_object['choices'][0]['text'].strip()

                    # this doesn't store any data, so we manually do that every time
                    if self.__remember_f:
                        conv = {
                            'prompt': self.__openai_arg['prompt'],
                            'response': response_text,
                        }

                        with open('conv.json', 'a') as f:
                            f.write(json.dumps(conv) + '\n')

                    self.replyGenerated.emit(response_text, False, False)
            elif self.__idx == 1:
                response = openai.Image.create(
                    **self.__openai_arg
                )

                image_url = response['data'][0]['url']

                self.replyGenerated.emit(image_url, False, False, True)
        except openai.error.InvalidRequestError as e:
            self.replyGenerated.emit('<p style="color:red">Your request was rejected as a result of our safety system.<br/>'
                                     'Your prompt may contain text that is not allowed by our safety system.</p>', False, False, False)
        except openai.error.RateLimitError as e:
            self.replyGenerated.emit(f'<p style="color:red">{e}<br/>Check the usage: https://platform.openai.com/account/usage<br/>Update to paid account: https://platform.openai.com/account/billing/overview', False, False, False)


class OpenAIChatBot(QMainWindow):
    def __init__(self):
        super().__init__()
        self.__initVal()
        self.__initUi()

    def __initVal(self):
        self.__engine = "gpt-3.5-turbo"
        self.__temperature = 0.0
        self.__max_tokens = 256
        self.__top_p = 1.0
        self.__frequency_penalty = 0.0
        self.__presence_penalty = 0.0
        self.__remember_past_conv = False
        self.__stream = True
        self.__finishReason = False
        self.__modelData = ModelData()

        self.__settings_struct = QSettings('pyqt_openai.ini', QSettings.IniFormat)

        # this api key should be yours
        if self.__settings_struct.contains('API_KEY'):
            # for script
            openai.api_key = self.__settings_struct.value('API_KEY')
            # for subprocess (mostly)
            os.environ['OPENAI_API_KEY'] = self.__settings_struct.value('API_KEY')
        else:
            self.__settings_struct.setValue('API_KEY', '')

        # init json file
        if os.path.exists('conv_history.json'):
            pass
        else:
            with open('conv_history.json', 'w') as f:
                init_data = {
                    'each_conv_lst': []
                }
                f.write(json.dumps(init_data))

        # "remember past conv" feature
        if self.__settings_struct.contains('REMEMBER_PAST_CONVERSATION'):
            self.__remember_past_conv = True if self.__settings_struct.value('REMEMBER_PAST_CONVERSATION') == '1' else False
        else:
            self.__settings_struct.setValue('REMEMBER_PAST_CONVERSATION', '0')

        if os.path.exists('conv.json'):
            pass
        else:
            with open('conv.json', 'w') as f:
                json.dump({}, f)

    def __initUi(self):
        self.setWindowTitle('PyQt OpenAI Chatbot')
        self.setWindowIcon(QIcon('ico/openai.svg'))

        self.__leftSideBarWidget = LeftSideBar()
        self.__leftSideBarWidget.initHistory()
        self.__leftSideBarWidget.added.connect(self.__addConv)
        self.__leftSideBarWidget.changed.connect(self.__changeConv)
        self.__leftSideBarWidget.deleted.connect(self.__deleteConv)

        self.__prompt = Prompt()

        self.__aiTypeCmbBox = QComboBox()
        self.__aiTypeCmbBox.addItems(['Text/Code Completion', 'Image Generation'])

        self.__lineEdit = self.__prompt.getTextEdit()
        self.__lineEdit.setPlaceholderText('Write some text...')
        self.__lineEdit.returnPressed.connect(self.__chat)

        self.__browser = ChatBrowser()
        self.__browser.convUpdated.connect(self.__updateConv)

        lay = QHBoxLayout()
        lay.addWidget(self.__aiTypeCmbBox)
        lay.addWidget(self.__prompt)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)

        self.__aiTypeCmbBox.setMaximumHeight(self.__prompt.sizeHint().height())

        self.__queryWidget = QWidget()
        self.__queryWidget.setLayout(lay)
        self.__queryWidget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        lay = QVBoxLayout()
        lay.addWidget(self.__browser)
        lay.addWidget(self.__queryWidget)
        lay.setSpacing(0)
        chatWidget = QWidget()
        chatWidget.setLayout(lay)

        # background app
        menu = QMenu()

        action = QAction("Quit", self)
        action.setIcon(QIcon('ico/close.svg'))

        action.triggered.connect(app.quit)

        menu.addAction(action)

        tray_icon = QSystemTrayIcon(app)
        tray_icon.setIcon(QIcon('ico/openai.svg'))
        tray_icon.activated.connect(self.__activated)

        tray_icon.setContextMenu(menu)

        tray_icon.show()

        self.__modelComboBox = QComboBox()
        self.__modelComboBox.addItems(getLatestModel())
        self.__modelComboBox.setCurrentText(self.__engine)
        self.__modelComboBox.currentTextChanged.connect(self.__modelChanged)

        temperatureSpinBox = QDoubleSpinBox()
        temperatureSpinBox.setRange(0, 1)
        temperatureSpinBox.setAccelerated(True)
        temperatureSpinBox.setSingleStep(0.01)
        temperatureSpinBox.setValue(self.__temperature)
        temperatureSpinBox.valueChanged.connect(self.__temperatureChanged)

        maxTokensSpinBox = QSpinBox()
        maxTokensSpinBox.setRange(0, 4000)
        maxTokensSpinBox.setAccelerated(True)
        maxTokensSpinBox.setValue(self.__max_tokens)
        maxTokensSpinBox.valueChanged.connect(self.__maxTokensChanged)

        toppSpinBox = QDoubleSpinBox()
        toppSpinBox.setRange(0, 1)
        toppSpinBox.setAccelerated(True)
        toppSpinBox.setSingleStep(0.01)
        toppSpinBox.setValue(self.__top_p)
        toppSpinBox.valueChanged.connect(self.__toppChanged)

        frequencyPenaltySpinBox = QDoubleSpinBox()
        frequencyPenaltySpinBox.setRange(0, 2)
        frequencyPenaltySpinBox.setAccelerated(True)
        frequencyPenaltySpinBox.setSingleStep(0.01)
        frequencyPenaltySpinBox.setValue(self.__frequency_penalty)
        frequencyPenaltySpinBox.valueChanged.connect(self.__frequencyPenaltyChanged)

        presencePenaltySpinBox = QDoubleSpinBox()
        presencePenaltySpinBox.setRange(0, 2)
        presencePenaltySpinBox.setAccelerated(True)
        presencePenaltySpinBox.setSingleStep(0.01)
        presencePenaltySpinBox.setValue(self.__presence_penalty)
        presencePenaltySpinBox.valueChanged.connect(self.__presencePenaltyChanged)

        streamChkBox = QCheckBox()
        streamChkBox.setChecked(self.__stream)
        streamChkBox.toggled.connect(self.__streamChecked)
        streamChkBox.setText('Stream')

        finishReasonChkBox = QCheckBox()
        finishReasonChkBox.setChecked(self.__finishReason)
        finishReasonChkBox.toggled.connect(self.__finishReasonChecked)
        finishReasonChkBox.setText('Show Finish Reason')

        saveAsLogButton = QPushButton('Save the Conversation as Log')
        saveAsLogButton.clicked.connect(self.__saveAsLog)

        apiLbl = QLabel('API')
        self.__apiLineEdit = QLineEdit()
        self.__apiLineEdit.setPlaceholderText('Write your API Key...')
        self.__apiLineEdit.setText(openai.api_key)

        self.__apiCheckPreviewLbl = QLabel('')
        self.__modelTable = ModelTable()

        self.__fineTuningBtn = QPushButton('Fine Tuning')
        self.__fineTuningBtn.clicked.connect(self.__fineTuning)

        # TODO move this to the bottom to enhance the readability
        # check if loaded API_KEY from ini file is not empty
        if openai.api_key:
            # check if loaded api is valid
            response = requests.get('https://api.openai.com/v1/engines', headers={'Authorization': f'Bearer {openai.api_key}'})
            f = response.status_code == 200
            self.__lineEdit.setEnabled(f)
            if f:
                self.__setModelInfoByModel(True)
                self.__apiCheckPreviewLbl.setStyleSheet("color: {}".format(QColor(0, 200, 0).name()))
                self.__apiCheckPreviewLbl.setText('API key is valid')
            else:
                self.__apiCheckPreviewLbl.setStyleSheet("color: {}".format(QColor(255, 0, 0).name()))
                self.__apiCheckPreviewLbl.setText('API key is invalid')
            self.__apiCheckPreviewLbl.show()

        # if it is empty
        else:
            self.__lineEdit.setEnabled(False)
            self.__apiCheckPreviewLbl.hide()

        self.__apiLineEdit.returnPressed.connect(self.__setApi)
        self.__apiLineEdit.setEchoMode(QLineEdit.Password)

        apiBtn = QPushButton('Use')
        apiBtn.clicked.connect(self.__setApi)

        lay = QHBoxLayout()
        lay.addWidget(self.__apiLineEdit)
        lay.addWidget(apiBtn)
        lay.setContentsMargins(0, 0, 0, 0)

        apiWidget = QWidget()
        apiWidget.setLayout(lay)

        self.__apiCheckPreviewLbl.setFont(QFont('Arial', 10))

        lay = QVBoxLayout()
        lay.addWidget(apiLbl)
        lay.addWidget(apiWidget)
        lay.addWidget(self.__apiCheckPreviewLbl)
        lay.setAlignment(Qt.AlignTop)

        apiGrpBox = QGroupBox()
        apiGrpBox.setLayout(lay)
        apiGrpBox.setFixedHeight(apiGrpBox.sizeHint().height() + self.__apiCheckPreviewLbl.fontMetrics().boundingRect('M').height())

        seeEveryModelCheckBox = QCheckBox('View every model (not all models may work)')
        seeEveryModelCheckBox.toggled.connect(self.__seeEveryModelToggled)
        seeEveryModelCheckBoxLbl = SvgLabel()
        seeEveryModelCheckBoxLbl.setSvgFile('ico/help.svg')
        seeEveryModelCheckBoxLbl.setToolTip('''Check this box to show all models, including obsolete ones. If you don\'t check this, combobox lists <a href="https://platform.openai.com/docs/models/gpt-3-5">latest models.</a>''')
        seeEveryModelCheckBoxLbl.installEventFilter(self)

        lay = QHBoxLayout()
        lay.addWidget(seeEveryModelCheckBox)
        lay.addWidget(seeEveryModelCheckBoxLbl)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignLeft)

        seeEveryModelWidget = QWidget()
        seeEveryModelWidget.setLayout(lay)

        modelTableSubLbl = QLabel('You can view the information only by entering the valid API key.')
        modelTableSubLbl.setFont(QFont('Arial', 9))

        lay = QVBoxLayout()
        lay.addWidget(modelTableSubLbl)
        lay.addWidget(self.__modelTable)

        modelTableGrpBox = QGroupBox()
        modelTableGrpBox.setTitle('Model Info (testing)')
        modelTableGrpBox.setLayout(lay)

        lay = QFormLayout()
        lay.addRow(seeEveryModelWidget)
        lay.addRow('Model', self.__modelComboBox)
        lay.addRow(modelTableGrpBox)
        lay.addRow('Temperature', temperatureSpinBox)
        lay.addRow('Maximum length', maxTokensSpinBox)
        lay.addRow('Top P', toppSpinBox)
        lay.addRow('Frequency penalty', frequencyPenaltySpinBox)
        lay.addRow('Presence penalty', presencePenaltySpinBox)
        lay.addRow(streamChkBox)
        lay.addRow(finishReasonChkBox)

        modelOptionGrpBox = QGroupBox()
        modelOptionGrpBox.setTitle('Model')
        modelOptionGrpBox.setLayout(lay)

        rememberPastConversationChkBox = QCheckBox('Store Previous Conversation in Real Time (testing)')
        rememberPastConversationChkBox.setChecked(self.__remember_past_conv)
        rememberPastConversationChkBox.setDisabled(True)
        rememberPastConversationChkBox.toggled.connect(self.__rememberPastConversationChkBoxToggled)

        lay = QVBoxLayout()
        lay.addWidget(rememberPastConversationChkBox)
        lay.addWidget(saveAsLogButton)

        generalOptionGrpBox = QGroupBox()
        generalOptionGrpBox.setTitle('General')
        generalOptionGrpBox.setLayout(lay)

        lay = QVBoxLayout()
        lay.addWidget(modelOptionGrpBox)
        lay.addWidget(generalOptionGrpBox)
        lay.setAlignment(Qt.AlignTop)

        optionGrpBox = QGroupBox()
        optionGrpBox.setTitle('Option')
        optionGrpBox.setLayout(lay)

        # find the training data
        self.__findDataLineEdit = QLineEdit()

        findDataBtn = QPushButton('Find...')
        findDataBtn.clicked.connect(self.__findData)

        lay = QHBoxLayout()
        lay.setSpacing(0)
        lay.addWidget(self.__findDataLineEdit)
        lay.addWidget(findDataBtn)
        lay.setAlignment(Qt.AlignTop)
        lay.setContentsMargins(5, 5, 5, 1)

        fineTuneGrpBoxTopWidget = QWidget()
        fineTuneGrpBoxTopWidget.setLayout(lay)

        lay = QVBoxLayout()
        lay.addWidget(self.__fineTuningBtn)
        lay.setAlignment(Qt.AlignTop)

        fineTuneGrpBoxBottomWidget = QWidget()
        fineTuneGrpBoxBottomWidget.setLayout(lay)
        lay.setContentsMargins(5, 1, 5, 5)

        lay = QVBoxLayout()
        lay.addWidget(fineTuneGrpBoxTopWidget)
        lay.addWidget(fineTuneGrpBoxBottomWidget)
        lay.setAlignment(Qt.AlignTop)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)

        fineTuneGrpBox = QGroupBox()
        fineTuneGrpBox.setTitle('Fine-tune training (coming soon)')
        fineTuneGrpBox.setLayout(lay)

        lay = QVBoxLayout()
        lay.addWidget(apiGrpBox)
        lay.addWidget(optionGrpBox)
        lay.addWidget(fineTuneGrpBox)

        self.__rightSidebarWidget = QWidget()
        self.__rightSidebarWidget.setLayout(lay)

        mainWidget = QSplitter()
        mainWidget.addWidget(self.__leftSideBarWidget)
        mainWidget.addWidget(chatWidget)
        mainWidget.addWidget(self.__rightSidebarWidget)
        mainWidget.setSizes([150, 700, 150])
        mainWidget.setChildrenCollapsible(False)
        mainWidget.setHandleWidth(2)
        mainWidget.setStyleSheet(
        '''
        QSplitter::handle:horizontal
        {
            background: #CCC;
            height: 1px;
        }
        ''')

        self.setCentralWidget(mainWidget)
        self.resize(1024, 768)

        self.__setActions()
        self.__setToolBar()

        self.__lineEdit.setFocus()

    def __setActions(self):
        self.__stackAction = QWidgetAction(self)
        self.__stackBtn = SvgButton()
        self.__stackBtn.setIcon('ico/stackontop.svg')
        self.__stackBtn.setCheckable(True)
        self.__stackBtn.toggled.connect(self.__stackToggle)
        self.__stackAction.setDefaultWidget(self.__stackBtn)
        self.__stackBtn.setToolTip('Always On Top')

        self.__sideBarAction = QWidgetAction(self)
        self.__sideBarBtn = SvgButton()
        self.__sideBarBtn.setIcon('ico/sidebar.svg')
        self.__sideBarBtn.setCheckable(True)
        self.__sideBarBtn.toggled.connect(self.__leftSideBarWidget.setVisible)
        self.__sideBarAction.setDefaultWidget(self.__sideBarBtn)
        self.__sideBarBtn.setToolTip('Chat List')
        self.__sideBarBtn.setChecked(True)

        self.__settingAction = QWidgetAction(self)
        self.__settingBtn = SvgButton()
        self.__settingBtn.setIcon('ico/setting.svg')
        self.__settingBtn.toggled.connect(self.__rightSidebarWidget.setVisible)
        self.__settingAction.setDefaultWidget(self.__settingBtn)
        self.__settingBtn.setToolTip('Settings')
        self.__settingBtn.setCheckable(True)
        self.__settingBtn.setChecked(True)
        self.__settingBtn.setChecked(False)

        self.__transparentAction = QWidgetAction(self)
        self.__transparentSpinBox = QSpinBox()
        self.__transparentSpinBox.setRange(0, 100)
        self.__transparentSpinBox.setValue(100)
        self.__transparentSpinBox.valueChanged.connect(self.__setTransparency)
        self.__transparentSpinBox.setToolTip('Set Transparency of Window')

        lay = QHBoxLayout()
        lay.addWidget(QLabel('Window Transparency'))
        lay.addWidget(self.__transparentSpinBox)

        transparencyActionWidget = QWidget()
        transparencyActionWidget.setLayout(lay)
        self.__transparentAction.setDefaultWidget(transparencyActionWidget)

    def __activated(self, reason):
        if reason == 3:
            self.show()

    def __setToolBar(self):
        toolbar = QToolBar()
        lay = QHBoxLayout()
        toolbar.addAction(self.__stackAction)
        toolbar.addAction(self.__sideBarAction)
        toolbar.addAction(self.__settingAction)
        toolbar.addAction(self.__transparentAction)
        toolbar.setLayout(lay)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        # QToolbar's layout can't be set spacing with lay.setSpacing so i've just did this instead
        toolbar.setStyleSheet('QToolBar { spacing: 2px; }')

    def eventFilter(self, source, event):
        if event.type() == QEvent.ToolTip and source.toolTip():
            toolTip = ClickableTooltip.showText(
                QCursor.pos(), source.toolTip(), source)
            toolTip.linkActivated.connect(self.toolTipLinkClicked)
            return True
        return super().eventFilter(source, event)

    def toolTipLinkClicked(self, url):
        webbrowser.open(url)

    def __setApi(self):
        try:
            api_key = self.__apiLineEdit.text()
            response = requests.get('https://api.openai.com/v1/engines', headers={'Authorization': f'Bearer {api_key}'})
            if response.status_code == 200:
                openai.api_key = api_key
                os.environ['OPENAI_API_KEY'] = api_key
                self.__setModelInfoByModel(True)
                self.__apiCheckPreviewLbl.setStyleSheet("color: {}".format(QColor(0, 200, 0).name()))
                self.__apiCheckPreviewLbl.setText('API key is valid')
                self.__settings_struct.setValue('API_KEY', api_key)
                self.__lineEdit.setEnabled(True)
            else:
                raise Exception
        except Exception as e:
            self.__apiCheckPreviewLbl.setStyleSheet("color: {}".format(QColor(255, 0, 0).name()))
            self.__apiCheckPreviewLbl.setText('API key is invalid')
            self.__lineEdit.setEnabled(False)
        finally:
            self.__apiCheckPreviewLbl.show()

    def __rememberPastConversationChkBoxToggled(self, f):
        self.__settings_struct.setValue('REMEMBER_PAST_CONVERSATION', str(int(f)))

    def __seeEveryModelToggled(self, f):
        curModel = self.__modelComboBox.currentText()
        self.__modelComboBox.currentTextChanged.disconnect(self.__modelChanged)
        self.__modelComboBox.clear()
        if f:
            self.__modelComboBox.addItems([model.id for model in self.__modelData.getModelData()])
        else:
            self.__modelComboBox.addItems(getLatestModel())
        self.__modelComboBox.currentTextChanged.connect(self.__modelChanged)
        self.__modelComboBox.setCurrentText(curModel)

    def __chat(self):
        idx = self.__aiTypeCmbBox.currentIndex()
        openai_arg = ''
        if idx == 0:
            if self.__remember_past_conv:
                convs = []
                with open('conv.json', 'r') as f:
                    for line in f:
                        conv = json.loads(line.strip())
                        convs.append(conv)
            # TODO refactoring
            if self.__engine in ['gpt-3.5-turbo', 'gpt-3.5-turbo-0301']:
                # "assistant" below is for making the AI remember the last question
                openai_arg = {
                    'model': self.__engine,
                    'messages': [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "assistant", "content": self.__browser.getAllText()},
                        {"role": "user", "content": self.__lineEdit.toPlainText()},
                    ],
                    'stream': self.__stream,
                }
            else:
                openai_arg = {
                    'engine': self.__engine,
                    'prompt': self.__lineEdit.toPlainText(),
                    'temperature': self.__temperature,
                    'max_tokens': self.__max_tokens,
                    'top_p': self.__top_p,
                    'frequency_penalty': self.__frequency_penalty,
                    'presence_penalty': self.__presence_penalty,
                }
        elif idx == 1:
            openai_arg = {
                "prompt": self.__lineEdit.toPlainText(),
                "n": 1,
                "size": "1024x1024"
            }
        self.__lineEdit.setEnabled(False)
        if self.__browser.isNew():
            self.__addConv()
        self.__browser.showLabel(self.__lineEdit.toPlainText(), True, False, False)

        self.__t = OpenAIThread(self.__engine, openai_arg, idx, self.__remember_past_conv)
        self.__t.replyGenerated.connect(self.__browser.showLabel)
        self.__lineEdit.clear()
        self.__t.start()
        self.__t.finished.connect(self.__afterGenerated)

    def __afterGenerated(self):
        self.__lineEdit.setEnabled(True)
        self.__lineEdit.setFocus()
        if not self.isVisible():
            self.__notifierWidget = NotifierWidget()
            self.__notifierWidget.show()
            self.__notifierWidget.doubleClicked.connect(self.show)

    def __setModelInfoByModel(self, init_model: bool = False):
        if init_model:
            self.__modelData.setModelData()
        self.__modelTable.setModelInfo(self.__modelData.getModelData(), self.__engine, 'allow_fine_tuning')
        self.__fineTuningBtn.setEnabled(self.__modelTable.getModelInfo())

    def __modelChanged(self, v):
        self.__engine = v
        self.__setModelInfoByModel()

    def __temperatureChanged(self, v):
        self.__temperature = round(v, 2)

    def __maxTokensChanged(self, v):
        self.__max_tokens = round(v, 2)

    def __toppChanged(self, v):
        self.__topp = round(v, 2)

    def __frequencyPenaltyChanged(self, v):
        self.__frequency_penalty = round(v, 2)

    def __presencePenaltyChanged(self, v):
        self.__presence_penalty = round(v, 2)

    def __streamChecked(self, f):
        self.__stream = f

    def __finishReasonChecked(self, f):
        self.__finishReason = f

    def __saveAsLog(self):
        filename = QFileDialog.getSaveFileName(self, 'Save', os.path.expanduser('~'), 'Text File (*.txt)')
        if filename[0]:
            filename = filename[0]
            file_extension = os.path.splitext(filename)[-1]
            if file_extension == '.txt':
                with open(filename, 'w') as f:
                    f.write(self.__browser.getAllText())
                os.startfile(os.path.dirname(filename))

    def __stackToggle(self, f):
        if f:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()

    def __setTransparency(self, v):
        self.setWindowOpacity(v / 100)

    def closeEvent(self, e):
        message = 'The window has been closed. Would you like to continue running this app in the background?'
        closeMessageBox = QMessageBox()
        closeMessageBox.setWindowTitle('Wait!')
        closeMessageBox.setText(message)
        closeMessageBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        reply = closeMessageBox.exec()
        # Yes
        if reply == 16384:
            e.accept()
        # No
        elif reply == 65536:
            app.quit()
        return super().closeEvent(e)

    def __findData(self):
        filename = QFileDialog.getOpenFileName(self, 'Open', '', 'JSONL Files (*.jsonl)')
        if filename[0]:
            filename = filename[0]
            self.__findDataLineEdit.setText(filename)
            self.__fineTuningBtn.setEnabled(True)

    def __addConv(self):
        cur_id = 0
        with open('conv_history.json', 'r') as f:
            data = json.load(f)

        with open('conv_history.json', 'w') as f:
            lst = data['each_conv_lst']
            cur_id = max(lst, key=lambda x: x["id"])["id"]+1 if len(lst) > 0 else 0
            data['each_conv_lst'].append({ 'id': cur_id, 'title': 'New Chat', 'conv_data': [] })
            f.write(json.dumps(data) + '\n')

        self.__browser.clear()
        self.__browser.setCurId(cur_id)
        self.__leftSideBarWidget.addToList(cur_id)
        self.__lineEdit.setFocus()

    # TODO set the feature
    def __changeConv(self, item: QListWidgetItem):
        id = item.data(Qt.UserRole)
        with open('conv_history.json', 'r') as f:
            data = json.load(f)
            lst = data['each_conv_lst']
            obj = list(filter(lambda x: x["id"] == id, lst))[0]
            self.__browser.setConversation(id, obj['conv_data'])

    # TODO implement the feature
    def __updateConv(self, id, conv_unit=None, title=None):
        with open('conv_history.json', 'r') as f:
            data = json.load(f)

        with open('conv_history.json', 'w') as f:
            lst = data['each_conv_lst']
            obj = list(filter(lambda x: x["id"] == id, lst))[0]
            if title:
                obj['title'] = title
            if conv_unit:
                obj['conv_data'].append(conv_unit)
            json.dump(data, f)

    def __deleteConv(self, id_lst):
        print(id_lst)
        with open('conv_history.json', 'r') as f:
            data = json.load(f)

        with open('conv_history.json', 'w') as f:
            lst = data['each_conv_lst']
            obj_to_delete = list(filter(lambda x: x["id"] in id_lst, lst))
            for obj in obj_to_delete:
                lst.remove(obj)
            json.dump(data, f)

    def __fineTuning(self):
        if platform.system() == 'Windows':
            subprocess.Popen('cmd.exe', creationflags=subprocess.CREATE_NEW_CONSOLE)
        elif platform.system() in ['Darwin', 'Linux']:
            subprocess.Popen('bash', creationflags=subprocess.CREATE_NEW_CONSOLE)

        # https://platform.openai.com/docs/guides/fine-tuning/cli-data-preparation-tool
        # validating & giving suggestions and reformat the data
        # subprocess.run('openai tools fine_tunes.prepare_data -f data.jsonl')

        # https://platform.openai.com/docs/guides/fine-tuning/create-a-fine-tuned-model
        # create a fine-tuned model
        # subprocess.run('openai api fine_tunes.create -t [TRAIN_FILE_ID_OR_PATH] -m [BASE_MODEL]')

        # run this when event stream is interrupted for any reason
        # subprocess.run('openai api fine_tunes.follow -i [YOUR_FINE_TUNE_JOB_ID]')
        # you can see the job done when it is finished
        # https://platform.openai.com/account/usage
        # https://platform.openai.com/playground

        # list the jobs
        # subprocess.run('openai api fine_tunes.list')

        # get the status of certain job. The resulting object includes
        # job status (which can be one of pending, running, succeeded, or failed)
        # and other information
        # subprocess.run('openai api fine_tunes.get -i [YOUR_FINE_TUNE_JOB_ID]')

        # cancel the job
        # subprocess.run('openai api fine_tunes.cancel -i [YOUR_FINE_TUNE_JOB_ID]')


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = OpenAIChatBot()
    w.show()
    sys.exit(app.exec())