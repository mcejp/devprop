#!/usr/bin/env python3

import html
import logging
import sys
import traceback
from typing import List, Dict, Tuple

from PySide2.QtCore import Qt, QThread, Signal, QObject, SignalInstance
from PySide2.QtWidgets import *
from PySide2.QtGui import QFont

from devprop.client import Client
from devprop.can_bus.python_can_adapter import PythonCanAdapter
from devprop.model import Property
from devprop.property import decode_value
from devprop.protocol_can_ext_v1.model import NodeId

# ./venv/bin/pyside2-uic mainwindow.ui -o ui_mainwindow.py
from .models import NodeListModel, PropertyTableModel, Node
from .configtoolsharedlogger import logger
from .ui_mainwindow import Ui_MainWindow


TIMEOUT = 2


def display_exception(parent: QFrame, ex: BaseException):
    traceback.print_exception(type(ex), ex, ex.__traceback__)

    exc_info = traceback.format_exception_only(type(ex), ex)
    QMessageBox.warning(parent, "Unhandled exception", "\n".join(exc_info) + "\n(see the log for details)")


def make_signal_promise(*args):
    class SignalPromise(QObject):
        then: SignalInstance = Signal(*args)
        catch: SignalInstance = Signal(BaseException)

        def reject(self, error: BaseException):
            if self.catch is not None:
                self.catch.emit(error)
            else:
                traceback.print_exc()

        def resolve(self, *args):
            self.then.emit(*args)

    return SignalPromise()


dumb_thread_list = []


def run_async(function):
    thread = QThread()

    promise = make_signal_promise(dict)

    def func():
        try:
            res = function()
            promise.resolve(res)
        except BaseException as ex:
            # necessary to catch all exceptions in QThread.run, otherwise app hangs on quit
            # import traceback
            # traceback.print_exc()
            promise.reject(ex)
        finally:
            QApplication.restoreOverrideCursor()

    thread.run = func
    thread.start()
    dumb_thread_list.append(thread)
    QApplication.setOverrideCursor(Qt.WaitCursor)
    return promise


class MainWindow(QMainWindow):
    device_list_model: NodeListModel
    property_table_model: PropertyTableModel

    logevent: SignalInstance = Signal(str, str)

    client: Client

    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.actionScanBus.clicked.connect(self.scan_bus)
        self.ui.actionGetAll.clicked.connect(self.get_all_properties)

        self.device_list_model = NodeListModel()
        self.ui.deviceList.setModel(self.device_list_model)
        self.device_list_model.dataChanged.connect(self.device_selection_changed)
        self.device_list_model.modelReset.connect(self.device_selection_changed)

        self.property_table_model = PropertyTableModel()
        self.ui.properties.setModel(self.property_table_model)
        self.property_table_model.property_value_changed.connect(self.property_value_changed)

        class MyLogger(logging.Handler):
            def __init__(self, event: SignalInstance, **kwargs):
                super().__init__(**kwargs)
                self.signal = event

            def emit(self, record: logging.LogRecord):
                msg = self.format(record)
                self.signal.emit(record.levelname, msg)

        logger.addHandler(MyLogger(self.logevent, level=logging.INFO))
        self.logevent.connect(self.log_event)

        font = QFont("Monospace")
        font.setStyleHint(QFont.TypeWriter)
        self.ui.log.setFont(font)

        # Init back-end
        # self.backend = MockBackend()
        self.client = Client(PythonCanAdapter())

        logger.info("Ready.")

    def log_event(self, level: str, message: str):
        self.ui.log.append(f"<b>{level}</b> {html.escape(message)}")

    def scan_bus(self):
        self.ui.actionScanBus.setEnabled(False)

        promise = run_async(lambda: self.client.enumerate_nodes(timeout_sec=TIMEOUT))
        promise.then.connect(self.bus_scan_finished)
        promise.catch.connect(lambda ex: display_exception(self, ex))

    def bus_scan_finished(self, nodes: Dict[NodeId, Node]):
        devices = sorted(nodes.values(), key=lambda node: node.name)
        self.all_devices_by_name = {dev.name: dev for dev in devices}

        self.device_list_model.set_device_list(devices)

        self.ui.actionScanBus.setEnabled(True)
        self.ui.statusbar.showMessage(f"Bus scan finished: {len(devices)} node(s)", timeout=5000)

    def device_selection_changed(self):
        logger.debug("device_selection_changed")
        tuples = []

        for dev in self.all_devices_by_name.values():
            if self.device_list_model.is_device_selected(dev.name):
                for property in dev.manifest.properties:
                    # FIXME: this trashes already retrieved values; better backing model needed!
                    tuples.append((dev, property))

        self.property_table_model.set_property_list(tuples)
        self.ui.properties.resizeColumnsToContents()
        self.ui.properties.horizontalHeader().setStretchLastSection(True) # TODO init

    def get_all_properties(self):
        self.ui.actionGetAll.setEnabled(False)

        query = []

        for dev in self.all_devices_by_name.values():
            if self.device_list_model.is_device_selected(dev.name):
                for prop in dev.manifest.properties:
                    query.append((dev, prop))

        promise = run_async(lambda: (query, self.client.query_properties(query, timeout_sec=TIMEOUT)))
        promise.then.connect(self.get_all_finished)
        promise.catch.connect(lambda ex: display_exception(self, ex))
        # FIXME: if an exception occurs, button is never re-enabled

        self.ui.properties.resizeColumnsToContents()
        self.ui.properties.horizontalHeader().setStretchLastSection(True) # TODO init

    def get_all_finished(self, res):
        self.ui.actionGetAll.setEnabled(True)
        query: List[Tuple[Node, Property]]
        results: List[bytes]
        query, results = res
        # print(query, results)

        self.property_table_model.beginResetModel() # TODO
        for (node, property), raw_value in zip(query, results):
            key = node.get_property_path(property)
            value = decode_value(property, raw_value)
            self.property_table_model.set_property_value(key, value)
        self.property_table_model.endResetModel() # TODO

        self.ui.statusbar.showMessage(f"Queried {len(results)} properties", timeout=5000)

    def property_value_changed(self, node: Node, property: Property, value: str):
        # print("property_value_changed", node, property, value)

        self.ui.actionGetAll.setEnabled(False)

        promise = run_async(lambda: self.client.set_property(node, property, float(value), timeout_sec=TIMEOUT))
        promise.then.connect(self.set_finished)
        promise.catch.connect(lambda ex: [display_exception(self, ex), self.ui.actionGetAll.setEnabled(True)])
        # FIXME: if an exception occurs, button is never re-enabled

    def set_finished(self, result):
        self.ui.actionGetAll.setEnabled(True)
        print(result)

        self.ui.statusbar.showMessage(f"Set to value: {str(result)}", timeout=5000)


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger("devprop").setLevel(logging.DEBUG)

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
