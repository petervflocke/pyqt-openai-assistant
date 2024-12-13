from __future__ import annotations

import os

from typing import TYPE_CHECKING

from qtpy.QtCore import QPointF, Qt, Signal
from qtpy.QtGui import QBrush, QColor, QLinearGradient, QPixmap
from qtpy.QtWidgets import QApplication, QFileDialog, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QHBoxLayout, QWidget

from pyqt_openai import ICON_ADD, ICON_COPY, ICON_DELETE, ICON_SAVE
from pyqt_openai.lang.translations import LangClass
from pyqt_openai.widgets.button import Button

if TYPE_CHECKING:
    from qtpy.QtCore import QEvent
    from qtpy.QtGui import QEnterEvent, QMouseEvent, QResizeEvent, QWheelEvent


class ThumbnailView(QGraphicsView):
    clicked = Signal(QPixmap)

    def __init__(self):
        super().__init__()
        self.__initVal()
        self.__initUi()

    def __initVal(self):
        self._scene: QGraphicsScene = QGraphicsScene()
        self._p: QPixmap = QPixmap()
        self._item: QGraphicsPixmapItem = QGraphicsPixmapItem()
        self.__aspectRatioMode: Qt.AspectRatioMode = Qt.AspectRatioMode.KeepAspectRatio

        self.__factor: float = 1.1  # Zoom factor

    def __initUi(self):
        self.__setControlWidget()

        # set mouse event
        # to make buttons appear and apply gradient
        # above the top of an image when you hover the mouse cursor over it
        self.setMouseTracking(True)
        self.__defaultBrush: QBrush = self.foregroundBrush()
        gradient = QLinearGradient(QPointF(0, 0), QPointF(0, self.viewport().height()))
        gradient.setColorAt(0, QColor(0, 0, 0, 200))
        gradient.setColorAt(1, QColor(0, 0, 0, 0))
        self.__brush: QBrush = QBrush(gradient)

        self.setMinimumSize(150, 150)

    def __setControlWidget(self):
        # copy the image
        copyBtn = Button()
        copyBtn.setStyleAndIcon(ICON_COPY)
        copyBtn.clicked.connect(self.__copy)

        # download the image
        saveBtn = Button()
        saveBtn.setStyleAndIcon(ICON_SAVE)
        saveBtn.clicked.connect(self.__save)

        # zoom in
        zoomInBtn = Button()
        zoomInBtn.setStyleAndIcon(ICON_ADD)
        zoomInBtn.clicked.connect(self.__zoomIn)

        # zoom out
        zoomOutBtn = Button()
        zoomOutBtn.setStyleAndIcon(ICON_DELETE)
        zoomOutBtn.clicked.connect(self.__zoomOut)

        lay = QHBoxLayout()
        lay.addWidget(copyBtn)
        lay.addWidget(saveBtn)
        lay.addWidget(zoomInBtn)
        lay.addWidget(zoomOutBtn)

        self.__controlWidget: QWidget = QWidget(self)
        self.__controlWidget.setLayout(lay)

        self.__controlWidget.hide()

    def __refreshSceneAndView(self):
        self._item: QGraphicsPixmapItem = self._scene.addPixmap(self._p)
        self._item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        rect = (
            self.sceneRect()
            if (self._item.boundingRect().width() > self.sceneRect().width()) or (self._item.boundingRect().height() > self.sceneRect().height())
            else self._item.boundingRect()
        )
        self.fitInView(rect, self.__aspectRatioMode)
        self.setScene(self._scene)

    def setFilename(
        self,
        filename: str,
    ):
        self._scene = QGraphicsScene()
        self._p = QPixmap(filename)
        self.__refreshSceneAndView()

    def setContent(
        self,
        content: bytes,
    ):
        self._scene = QGraphicsScene()
        self._p.loadFromData(content)
        self.__refreshSceneAndView()

    def setPixmap(
        self,
        pixmap: QPixmap,
    ):
        self._scene = QGraphicsScene()
        self._p = pixmap
        self.__refreshSceneAndView()

    def setAspectRatioMode(
        self,
        mode: Qt.AspectRatioMode,
    ):
        self.__aspectRatioMode = mode

    def __copy(self):
        QApplication.clipboard().setPixmap(self._p)

    def __save(self):
        filename: tuple[str, str] = QFileDialog.getSaveFileName(
            self,
            LangClass.TRANSLATIONS["Save"],
            os.path.expanduser("~"),
            "Image file (*.png)",
        )
        if filename[0] and filename[0].strip():
            filename = filename[0]
            if filename:
                self._p.save(filename)

    def __zoomIn(self):
        self.scale(self.__factor, self.__factor)

    def __zoomOut(self):
        self.scale(1 / self.__factor, 1 / self.__factor)

    def enterEvent(
        self,
        event: QEnterEvent,
    ):
        # Show the button when the mouse enters the view
        if self._item.pixmap().width():
            self.__controlWidget.move(self.rect().x(), self.rect().y())
            self.setForegroundBrush(self.__brush)
            self.__controlWidget.show()
        return super().enterEvent(event)

    def leaveEvent(
        self,
        event: QEvent,
    ):
        # Hide the button when the mouse leaves the view
        self.__controlWidget.hide()
        self.setForegroundBrush(self.__defaultBrush)
        return super().leaveEvent(event)

    def resizeEvent(
        self,
        event: QResizeEvent,
    ):
        if self._item.pixmap().width():
            self.setScene(self._scene)
        return super().resizeEvent(event)

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ):
        self.clicked.emit(self._p)
        return super().mousePressEvent(event)

    def wheelEvent(
        self,
        event: QWheelEvent,
    ):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Check if Ctrl key is pressed
            if event.angleDelta().y() > 0:
                # Ctrl + wheel up, zoom in
                self.__zoomIn()
            else:
                # Ctrl + wheel down, zoom out
                self.__zoomOut()
            event.accept()  # Accept the event if Ctrl is pressed
        else:
            super().wheelEvent(event)  # Default behavior for other cases
