from dataclasses import dataclass
from typing import List, Any, Dict, Tuple

from PySide2.QtCore import QAbstractListModel, Qt, QModelIndex, QAbstractTableModel, Signal, SignalInstance

# from can_backend import BackendDevice
from devprop.client import Node
from devprop.model import Manifest, Property
# from udpbackend import BackendDevice


class NodeListModel(QAbstractListModel):
    # changed: SignalInstance = Signal()

    nodes: List[Node]
    device_selected: Dict[str, bool]

    def __init__(self):
        super().__init__()
        self.nodes = []
        self.device_selected = {}

    def is_device_selected(self, device_name: str):
        return self.device_selected[device_name]

    def set_device_list(self, devices: List[Node]):
        self.beginResetModel()

        self.nodes = devices
        # This preserves the current state and sets True for newly found devices
        self.device_selected = {**{device.name: True for device in devices}, **self.device_selected}

        self.endResetModel()

    def data(self, index, role):
        if index.column() == 0 and role == Qt.CheckStateRole:
            device = self.nodes[index.row()]
            return Qt.Checked if self.device_selected[device.name] else Qt.Unchecked

        if role == Qt.DisplayRole:
            return self.nodes[index.row()].name

    def setData(self, index: QModelIndex, value: Any, role) -> bool:
        # print("setData", index, value, role)
        if index.column() == 0 and role == Qt.CheckStateRole:
            device = self.nodes[index.row()]
            self.device_selected[device.name] = (value == Qt.Checked)
            self.dataChanged.emit(index, index, role)
            return True
        else:
            return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        # print(index, super().flags(index))
        return super().flags(index) | Qt.ItemFlag.ItemIsUserCheckable

    def rowCount(self, index):
        return len(self.nodes)


class PropertyTableModel(QAbstractTableModel):
    ADDRESS_COLUMN = 0
    DEVICE_NAME_COLUMN = 1
    PROPERTY_NAME_COLUMN = 2
    VALUE_COLUMN = 3
    RANGE_COLUMN = 4
    NUM_COLUMNS = 5

    tuples: List[Tuple[Node, Property]]
    property_selected: Dict[str, bool]
    values: Dict[str, str]

    property_value_changed: SignalInstance = Signal(Node, Property, str)

    def __init__(self):
        super().__init__()

        self.tuples = []
        self.property_selected = {}
        self.values = {}

    def set_property_list(self, tuples: List[Tuple[Node, Property]]):
        self.beginResetModel()
        self.tuples = tuples
        self.endResetModel()

    def set_property_value(self, key: str, value: Any):
        self.values[key] = value

    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            if index.column() == self.VALUE_COLUMN:
                # BUG https://bugreports.qt.io/browse/PYSIDE-168
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        elif role == Qt.CheckStateRole:
            if index.column() == self.ADDRESS_COLUMN:
                device, property = self.tuples[index.row()]
                property_path = device.get_property_path(property)
                selected = self.property_selected.get(property_path, False)

                return Qt.Checked if selected else Qt.Unchecked
        elif role == Qt.DisplayRole:
            if index.column() == self.ADDRESS_COLUMN:
                device, property = self.tuples[index.row()]
                # return f"{device.address_str}/{property.index}"
                return device.address_str
            elif index.column() == self.DEVICE_NAME_COLUMN:
                # return self.tuples[index.row()][0].manifest.device_name
                return self.tuples[index.row()][0].manifest.device_name
            elif index.column() == self.PROPERTY_NAME_COLUMN:
                return self.tuples[index.row()][1].name
            elif index.column() == self.VALUE_COLUMN:
                device, property = self.tuples[index.row()]
                property_path = device.get_property_path(property)
                return self.values.get(device.get_property_path(property), "")
            elif index.column() == self.RANGE_COLUMN:
                property = self.tuples[index.row()][1]
                return f"{property.range_str[0]} .. {property.range_str[1]} {property.unit}"

    def setData(self, index: QModelIndex, value: Any, role) -> bool:
        # print("setData", index, value, role)
        # TODO: per https://doc.qt.io/qt-5/qabstractitemmodel.html#setData,
        #       The dataChanged() signal should be emitted if the data was successfully set.

        if index.column() == self.ADDRESS_COLUMN and role == Qt.CheckStateRole:
            device, property = self.tuples[index.row()]
            property_path = device.get_property_path(property)
            self.property_selected[property_path] = (value == Qt.Checked)
            return True
        elif index.column() == self.VALUE_COLUMN and role == Qt.EditRole:
            assert isinstance(value, str)

            node, property = self.tuples[index.row()]
            property_path = node.get_property_path(property)
            self.values[property_path] = value

            self.property_value_changed.emit(node, property, value)
            return True
        else:
            return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        flags = {
            self.ADDRESS_COLUMN:        Qt.ItemFlag.ItemIsUserCheckable,
            self.DEVICE_NAME_COLUMN:    Qt.ItemFlag.NoItemFlags,
            self.PROPERTY_NAME_COLUMN:  Qt.ItemFlag.NoItemFlags,
            self.VALUE_COLUMN:          Qt.ItemFlag.ItemIsEditable,
            self.RANGE_COLUMN:          Qt.ItemFlag.NoItemFlags,
        }
        return Qt.ItemFlag.ItemIsEnabled | flags[index.column()]

    def rowCount(self, index):
        # The length of the outer list.
        return len(self.tuples)

    def columnCount(self, index):
        return self.NUM_COLUMNS

    def headerData(self, section:int, orientation: Qt.Orientation, role:int) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.DisplayRole:
            column_names = {
                self.ADDRESS_COLUMN: "Address",
                self.DEVICE_NAME_COLUMN: "Device",
                self.PROPERTY_NAME_COLUMN: "Property",
                self.VALUE_COLUMN: "Value",
                self.RANGE_COLUMN: "Range",
            }
            return column_names[section]

        res = super().headerData(section, orientation, role)
        # print(section, orientation, role, "=>", res)
        return res
