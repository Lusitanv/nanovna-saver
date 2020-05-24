#  NanoVNASaver
#  A python program to view and export Touchstone data from a NanoVNA
#  Copyright (C) 2019.  Rune B. Broberg
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
import logging
import math
import sys
import threading
from time import sleep, strftime, localtime
from typing import List

import serial
from PyQt5 import QtWidgets, QtCore, QtGui

from .Windows import AboutWindow, AnalysisWindow, \
    DeviceSettingsWindow, DisplaySettingsWindow, SweepSettingsWindow, \
    TDRWindow
from .Hardware import get_interfaces, get_VNA, InvalidVNA
from .RFTools import RFTools, Datapoint
from .Charts.Chart import Chart
from .Charts import CapacitanceChart, \
    CombinedLogMagChart, GroupDelayChart, InductanceChart, \
    LogMagChart, PhaseChart, \
    MagnitudeChart, MagnitudeZChart, \
    QualityFactorChart, VSWRChart, PermeabilityChart, PolarChart, \
    RealImaginaryChart, \
    SmithChart, SParameterChart, TDRChart
from .Calibration import CalibrationWindow, Calibration
from .Inputs import FrequencyInputWidget
from .Marker import Marker
from .SweepWorker import SweepWorker
from .Settings import BandsModel
from .Touchstone import Touchstone
from .about import version as ver

logger = logging.getLogger(__name__)


class NanoVNASaver(QtWidgets.QWidget):
    version = ver
    dataAvailable = QtCore.pyqtSignal()
    scaleFactor = 1

    sweepTitle = ""

    def __init__(self):
        super().__init__()
        if getattr(sys, 'frozen', False):
            logger.debug("Running from pyinstaller bundle")
            self.icon = QtGui.QIcon(sys._MEIPASS + "/icon_48x48.png")  # pylint: disable=no-member
        else:
            self.icon = QtGui.QIcon("icon_48x48.png")
        self.setWindowIcon(self.icon)
        self.settings = QtCore.QSettings(QtCore.QSettings.IniFormat,
                                         QtCore.QSettings.UserScope,
                                         "NanoVNASaver", "NanoVNASaver")
        print("Settings: " + self.settings.fileName())
        self.threadpool = QtCore.QThreadPool()
        self.worker = SweepWorker(self)

        self.worker.signals.updated.connect(self.dataUpdated)
        self.worker.signals.finished.connect(self.sweepFinished)
        self.worker.signals.sweepError.connect(self.showSweepError)
        self.worker.signals.fatalSweepError.connect(self.showFatalSweepError)

        self.bands = BandsModel()

        self.noSweeps = 1  # Number of sweeps to run

        self.serialLock = threading.Lock()
        self.serial = serial.Serial()
        self.vna = InvalidVNA(self, serial)

        self.dataLock = threading.Lock()
        self.data: List[Datapoint] = []
        self.data21: List[Datapoint] = []
        self.referenceS11data: List[Datapoint] = []
        self.referenceS21data: List[Datapoint] = []

        self.sweepSource = ""
        self.referenceSource = ""

        self.calibration = Calibration()

        self.markers = []

        self.serialPort = ""

        logger.debug("Building user interface")

        self.baseTitle = "NanoVNA Saver " + NanoVNASaver.version
        self.updateTitle()
        layout = QtWidgets.QGridLayout()
        scrollarea = QtWidgets.QScrollArea()
        outer = QtWidgets.QVBoxLayout()
        outer.addWidget(scrollarea)
        self.setLayout(outer)
        scrollarea.setWidgetResizable(True)
        window_width = self.settings.value("WindowWidth", 1350, type=int)
        window_height = self.settings.value("WindowHeight", 950, type=int)
        self.resize(window_width, window_height)
        scrollarea.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        scrollarea.setWidget(widget)

        # outer.setContentsMargins(2, 2, 2, 2)  # Small screen mode, reduce margins?

        self.s11SmithChart = SmithChart("S11 Smith Chart")
        self.s21PolarChart = PolarChart("S21 Polar Plot")
        self.s11SParameterChart = SParameterChart("S11 Real/Imaginary")
        self.s21SParameterChart = SParameterChart("S21 Real/Imaginary")
        self.s11LogMag = LogMagChart("S11 Return Loss")
        self.s21LogMag = LogMagChart("S21 Gain")
        self.s11Mag = MagnitudeChart("|S11|")
        self.s21Mag = MagnitudeChart("|S21|")
        self.s11MagZ = MagnitudeZChart("S11 |Z|")
        self.s11Phase = PhaseChart("S11 Phase")
        self.s21Phase = PhaseChart("S21 Phase")
        self.s11GroupDelay = GroupDelayChart("S11 Group Delay")
        self.s11CapacitanceChart = CapacitanceChart("S11 Serial C")
        self.s11InductanceChart = InductanceChart("S11 Serial L")
        self.s21GroupDelay = GroupDelayChart("S21 Group Delay", reflective=False)
        self.permabilityChart = PermeabilityChart("S11 R/\N{GREEK SMALL LETTER OMEGA} & X/\N{GREEK SMALL LETTER OMEGA}")
        self.s11VSWR = VSWRChart("S11 VSWR")
        self.s11QualityFactor = QualityFactorChart("S11 Quality Factor")
        self.s11RealImaginary = RealImaginaryChart("S11 R+jX")
        self.tdr_chart = TDRChart("TDR")
        self.tdr_mainwindow_chart = TDRChart("TDR")
        self.combinedLogMag = CombinedLogMagChart("S11 & S21 LogMag")

        # List of all the S11 charts, for selecting
        self.s11charts: List[Chart] = []
        self.s11charts.append(self.s11SmithChart)
        self.s11charts.append(self.s11LogMag)
        self.s11charts.append(self.s11Mag)
        self.s11charts.append(self.s11MagZ)
        self.s11charts.append(self.s11Phase)
        self.s11charts.append(self.s11GroupDelay)
        self.s11charts.append(self.s11VSWR)
        self.s11charts.append(self.s11RealImaginary)
        self.s11charts.append(self.s11QualityFactor)
        self.s11charts.append(self.s11SParameterChart)
        self.s11charts.append(self.s11CapacitanceChart)
        self.s11charts.append(self.s11InductanceChart)
        self.s11charts.append(self.permabilityChart)

        # List of all the S21 charts, for selecting
        self.s21charts: List[Chart] = []
        self.s21charts.append(self.s21PolarChart)
        self.s21charts.append(self.s21LogMag)
        self.s21charts.append(self.s21Mag)
        self.s21charts.append(self.s21Phase)
        self.s21charts.append(self.s21GroupDelay)
        self.s21charts.append(self.s21SParameterChart)

        # List of all charts that use both S11 and S21
        self.combinedCharts: List[Chart] = []
        self.combinedCharts.append(self.combinedLogMag)

        # List of all charts that can be selected for display
        self.selectable_charts = self.s11charts + self.s21charts + self.combinedCharts
        self.selectable_charts.append(self.tdr_mainwindow_chart)

        # List of all charts that subscribe to updates (including duplicates!)
        self.subscribing_charts = []
        self.subscribing_charts.extend(self.selectable_charts)
        self.subscribing_charts.append(self.tdr_chart)

        for c in self.subscribing_charts:
            c.popoutRequested.connect(self.popoutChart)

        self.charts_layout = QtWidgets.QGridLayout()

        left_column = QtWidgets.QVBoxLayout()
        self.marker_column = QtWidgets.QVBoxLayout()
        self.marker_frame = QtWidgets.QFrame()
        self.marker_column.setContentsMargins(0, 0, 0, 0)
        self.marker_frame.setLayout(self.marker_column)
        right_column = QtWidgets.QVBoxLayout()
        right_column.addLayout(self.charts_layout)
        self.marker_frame.setHidden(not self.settings.value("MarkersVisible", True, bool))

        layout.addLayout(left_column, 0, 0)
        layout.addWidget(self.marker_frame, 0, 1)
        layout.addLayout(right_column, 0, 2)

        ################################################################################################################
        #  Sweep control
        ################################################################################################################

        sweep_control_box = QtWidgets.QGroupBox()
        sweep_control_box.setMaximumWidth(250)
        sweep_control_box.setTitle("Sweep control")
        sweep_control_layout = QtWidgets.QFormLayout(sweep_control_box)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.VLine)

        sweep_input_layout = QtWidgets.QHBoxLayout()
        sweep_input_left_layout = QtWidgets.QFormLayout()
        sweep_input_right_layout = QtWidgets.QFormLayout()
        sweep_input_layout.addLayout(sweep_input_left_layout)
        sweep_input_layout.addWidget(line)
        sweep_input_layout.addLayout(sweep_input_right_layout)
        sweep_control_layout.addRow(sweep_input_layout)

        self.sweepStartInput = FrequencyInputWidget()
        self.sweepStartInput.setMinimumWidth(60)
        self.sweepStartInput.setAlignment(QtCore.Qt.AlignRight)
        self.sweepStartInput.textEdited.connect(self.updateCenterSpan)
        self.sweepStartInput.textChanged.connect(self.updateStepSize)
        sweep_input_left_layout.addRow(QtWidgets.QLabel("Start"), self.sweepStartInput)

        self.sweepEndInput = FrequencyInputWidget()
        self.sweepEndInput.setAlignment(QtCore.Qt.AlignRight)
        self.sweepEndInput.textEdited.connect(self.updateCenterSpan)
        self.sweepEndInput.textChanged.connect(self.updateStepSize)
        sweep_input_left_layout.addRow(QtWidgets.QLabel("Stop"), self.sweepEndInput)

        self.sweepCenterInput = FrequencyInputWidget()
        self.sweepCenterInput.setMinimumWidth(60)
        self.sweepCenterInput.setAlignment(QtCore.Qt.AlignRight)
        self.sweepCenterInput.textEdited.connect(self.updateStartEnd)

        sweep_input_right_layout.addRow(QtWidgets.QLabel("Center"), self.sweepCenterInput)

        self.sweepSpanInput = FrequencyInputWidget()
        self.sweepSpanInput.setAlignment(QtCore.Qt.AlignRight)
        self.sweepSpanInput.textEdited.connect(self.updateStartEnd)

        sweep_input_right_layout.addRow(QtWidgets.QLabel("Span"), self.sweepSpanInput)

        self.sweepCountInput = QtWidgets.QLineEdit(self.settings.value("Segments", "1"))
        self.sweepCountInput.setAlignment(QtCore.Qt.AlignRight)
        self.sweepCountInput.setFixedWidth(60)
        self.sweepCountInput.textEdited.connect(self.updateStepSize)

        self.sweepStepLabel = QtWidgets.QLabel("Hz/step")
        self.sweepStepLabel.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        segment_layout = QtWidgets.QHBoxLayout()
        segment_layout.addWidget(self.sweepCountInput)
        segment_layout.addWidget(self.sweepStepLabel)
        sweep_control_layout.addRow(QtWidgets.QLabel("Segments"), segment_layout)

        self.sweepSettingsWindow = SweepSettingsWindow(self)
        btn_sweep_settings_window = QtWidgets.QPushButton("Sweep settings ...")
        btn_sweep_settings_window.clicked.connect(self.displaySweepSettingsWindow)

        sweep_control_layout.addRow(btn_sweep_settings_window)

        self.sweepProgressBar = QtWidgets.QProgressBar()
        self.sweepProgressBar.setMaximum(100)
        self.sweepProgressBar.setValue(0)
        sweep_control_layout.addRow(self.sweepProgressBar)

        self.btnSweep = QtWidgets.QPushButton("Sweep")
        self.btnSweep.clicked.connect(self.sweep)
        self.btnSweep.setShortcut(QtCore.Qt.Key_W | QtCore.Qt.CTRL)
        self.btnStopSweep = QtWidgets.QPushButton("Stop")
        self.btnStopSweep.clicked.connect(self.stopSweep)
        self.btnStopSweep.setShortcut(QtCore.Qt.Key_Escape)
        self.btnStopSweep.setDisabled(True)
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.btnSweep)
        btn_layout.addWidget(self.btnStopSweep)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout_widget = QtWidgets.QWidget()
        btn_layout_widget.setLayout(btn_layout)
        sweep_control_layout.addRow(btn_layout_widget)

        left_column.addWidget(sweep_control_box)

        ################################################################################################################
        #  Marker control
        ################################################################################################################

        marker_control_box = QtWidgets.QGroupBox()
        marker_control_box.setTitle("Markers")
        marker_control_box.setMaximumWidth(250)
        self.marker_control_layout = QtWidgets.QFormLayout(marker_control_box)

        marker_count = max(self.settings.value("MarkerCount", 3, int), 1)
        for i in range(marker_count):
            marker = Marker("", self.settings)
            marker.updated.connect(self.markerUpdated)
            label, layout = marker.getRow()
            self.marker_control_layout.addRow(label, layout)
            self.markers.append(marker)
            if i == 0:
                marker.isMouseControlledRadioButton.setChecked(True)

        self.showMarkerButton = QtWidgets.QPushButton()
        if self.marker_frame.isHidden():
            self.showMarkerButton.setText("Show data")
        else:
            self.showMarkerButton.setText("Hide data")
        self.showMarkerButton.clicked.connect(self.toggleMarkerFrame)
        lock_radiobutton = QtWidgets.QRadioButton("Locked")
        lock_radiobutton.setLayoutDirection(QtCore.Qt.RightToLeft)
        lock_radiobutton.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.showMarkerButton)
        hbox.addWidget(lock_radiobutton)
        self.marker_control_layout.addRow(hbox)

        for c in self.subscribing_charts:
            c.setMarkers(self.markers)
            c.setBands(self.bands)
        left_column.addWidget(marker_control_box)

        self.marker_data_layout = QtWidgets.QVBoxLayout()
        self.marker_data_layout.setContentsMargins(0, 0, 0, 0)

        for m in self.markers:
            self.marker_data_layout.addWidget(m.getGroupBox())

        self.marker_column.addLayout(self.marker_data_layout)

        ################################################################################################################
        #  Statistics/analysis
        ################################################################################################################

        s11_control_box = QtWidgets.QGroupBox()
        s11_control_box.setTitle("S11")
        s11_control_layout = QtWidgets.QFormLayout()
        s11_control_box.setLayout(s11_control_layout)

        self.s11_min_swr_label = QtWidgets.QLabel()
        s11_control_layout.addRow("Min VSWR:", self.s11_min_swr_label)
        self.s11_min_rl_label = QtWidgets.QLabel()
        s11_control_layout.addRow("Return loss:", self.s11_min_rl_label)

        self.marker_column.addWidget(s11_control_box)

        s21_control_box = QtWidgets.QGroupBox()
        s21_control_box.setTitle("S21")
        s21_control_layout = QtWidgets.QFormLayout()
        s21_control_box.setLayout(s21_control_layout)

        self.s21_min_gain_label = QtWidgets.QLabel()
        s21_control_layout.addRow("Min gain:", self.s21_min_gain_label)

        self.s21_max_gain_label = QtWidgets.QLabel()
        s21_control_layout.addRow("Max gain:", self.s21_max_gain_label)

        self.marker_column.addWidget(s21_control_box)

        self.marker_column.addStretch(1)
        self.analysis_window = AnalysisWindow(self)

        btn_show_analysis = QtWidgets.QPushButton("Analysis ...")
        btn_show_analysis.clicked.connect(self.displayAnalysisWindow)
        self.marker_column.addWidget(btn_show_analysis)

        ################################################################################################################
        # TDR
        ################################################################################################################

        self.tdr_window = TDRWindow(self)
        self.tdr_chart.tdrWindow = self.tdr_window
        self.tdr_mainwindow_chart.tdrWindow = self.tdr_window
        self.tdr_window.updated.connect(self.tdr_chart.update)
        self.tdr_window.updated.connect(self.tdr_mainwindow_chart.update)

        tdr_control_box = QtWidgets.QGroupBox()
        tdr_control_box.setTitle("TDR")
        tdr_control_layout = QtWidgets.QFormLayout()
        tdr_control_box.setLayout(tdr_control_layout)
        tdr_control_box.setMaximumWidth(250)

        self.tdr_result_label = QtWidgets.QLabel()
        tdr_control_layout.addRow("Estimated cable length:", self.tdr_result_label)

        self.tdr_button = QtWidgets.QPushButton("Time Domain Reflectometry ...")
        self.tdr_button.clicked.connect(self.displayTDRWindow)

        tdr_control_layout.addRow(self.tdr_button)

        left_column.addWidget(tdr_control_box)

        ################################################################################################################
        #  Spacer
        ################################################################################################################

        left_column.addSpacerItem(QtWidgets.QSpacerItem(1, 1, QtWidgets.QSizePolicy.Fixed,
                                                        QtWidgets.QSizePolicy.Expanding))

        ################################################################################################################
        #  Reference control
        ################################################################################################################

        reference_control_box = QtWidgets.QGroupBox()
        reference_control_box.setMaximumWidth(250)
        reference_control_box.setTitle("Reference sweep")
        reference_control_layout = QtWidgets.QFormLayout(reference_control_box)

        btn_set_reference = QtWidgets.QPushButton("Set current as reference")
        btn_set_reference.clicked.connect(self.setReference)
        self.btnResetReference = QtWidgets.QPushButton("Reset reference")
        self.btnResetReference.clicked.connect(self.resetReference)
        self.btnResetReference.setDisabled(True)

        reference_control_layout.addRow(btn_set_reference)
        reference_control_layout.addRow(self.btnResetReference)

        left_column.addWidget(reference_control_box)

        ################################################################################################################
        #  Serial control
        ################################################################################################################

        serial_control_box = QtWidgets.QGroupBox()
        serial_control_box.setMaximumWidth(250)
        serial_control_box.setTitle("Serial port control")
        serial_control_layout = QtWidgets.QFormLayout(serial_control_box)
        self.serialPortInput = QtWidgets.QComboBox()
        self.rescanSerialPort()
        self.serialPortInput.setEditable(True)
        btn_rescan_serial_port = QtWidgets.QPushButton("Rescan")
        btn_rescan_serial_port.setFixedWidth(60)
        btn_rescan_serial_port.clicked.connect(self.rescanSerialPort)
        serial_port_input_layout = QtWidgets.QHBoxLayout()
        serial_port_input_layout.addWidget(self.serialPortInput)
        serial_port_input_layout.addWidget(btn_rescan_serial_port)
        serial_control_layout.addRow(QtWidgets.QLabel("Serial port"), serial_port_input_layout)

        serial_button_layout = QtWidgets.QHBoxLayout()

        self.btnSerialToggle = QtWidgets.QPushButton("Connect to device")
        self.btnSerialToggle.clicked.connect(self.serialButtonClick)
        serial_button_layout.addWidget(self.btnSerialToggle, stretch=1)

        self.deviceSettingsWindow = DeviceSettingsWindow(self)
        self.btnDeviceSettings = QtWidgets.QPushButton("Manage")
        self.btnDeviceSettings.clicked.connect(self.displayDeviceSettingsWindow)
        serial_button_layout.addWidget(self.btnDeviceSettings, stretch=0)
        serial_control_layout.addRow(serial_button_layout)
        left_column.addWidget(serial_control_box)

        ################################################################################################################
        #  File control
        ################################################################################################################

        self.fileWindow = QtWidgets.QWidget()
        self.fileWindow.setWindowTitle("Files")
        self.fileWindow.setWindowIcon(self.icon)
        self.fileWindow.setMinimumWidth(200)
        QtWidgets.QShortcut(QtCore.Qt.Key_Escape, self.fileWindow, self.fileWindow.hide)
        file_window_layout = QtWidgets.QVBoxLayout()
        self.fileWindow.setLayout(file_window_layout)

        load_file_control_box = QtWidgets.QGroupBox("Import file")
        load_file_control_box.setMaximumWidth(300)
        load_file_control_layout = QtWidgets.QFormLayout(load_file_control_box)

        btn_load_sweep = QtWidgets.QPushButton("Load as sweep")
        btn_load_sweep.clicked.connect(self.loadSweepFile)
        btn_load_reference = QtWidgets.QPushButton("Load reference")
        btn_load_reference.clicked.connect(self.loadReferenceFile)
        load_file_control_layout.addRow(btn_load_sweep)
        load_file_control_layout.addRow(btn_load_reference)

        file_window_layout.addWidget(load_file_control_box)

        save_file_control_box = QtWidgets.QGroupBox("Export file")
        save_file_control_box.setMaximumWidth(300)
        save_file_control_layout = QtWidgets.QFormLayout(save_file_control_box)

        btn_export_file = QtWidgets.QPushButton("Save 1-Port file (S1P)")
        btn_export_file.clicked.connect(self.exportFileS1P)
        save_file_control_layout.addRow(btn_export_file)

        btn_export_file = QtWidgets.QPushButton("Save 2-Port file (S2P)")
        btn_export_file.clicked.connect(self.exportFileS2P)
        save_file_control_layout.addRow(btn_export_file)

        file_window_layout.addWidget(save_file_control_box)

        btn_open_file_window = QtWidgets.QPushButton("Files ...")
        btn_open_file_window.clicked.connect(self.displayFileWindow)

        ################################################################################################################
        #  Calibration
        ################################################################################################################

        btnOpenCalibrationWindow = QtWidgets.QPushButton("Calibration ...")
        self.calibrationWindow = CalibrationWindow(self)
        btnOpenCalibrationWindow.clicked.connect(self.displayCalibrationWindow)

        ################################################################################################################
        #  Display setup
        ################################################################################################################

        btn_display_setup = QtWidgets.QPushButton("Display setup ...")
        btn_display_setup.setMaximumWidth(250)
        self.displaySetupWindow = DisplaySettingsWindow(self)
        btn_display_setup.clicked.connect(self.displaySettingsWindow)

        self.aboutWindow = AboutWindow(self)

        btn_about = QtWidgets.QPushButton("About ...")
        btn_about.setMaximumWidth(250)

        btn_about.clicked.connect(self.displayAboutWindow)

        button_grid = QtWidgets.QGridLayout()
        button_grid.addWidget(btn_open_file_window, 0, 0)
        button_grid.addWidget(btnOpenCalibrationWindow, 0, 1)
        button_grid.addWidget(btn_display_setup, 1, 0)
        button_grid.addWidget(btn_about, 1, 1)
        left_column.addLayout(button_grid)

        logger.debug("Finished building interface")

    def rescanSerialPort(self):
        self.serialPortInput.clear()
        for port in get_interfaces():
            self.serialPortInput.insertItem(1, port[1], port[0])

    def exportFileS1P(self):
        if len(self.data) == 0:
            # No data to save, alert the user
            QtWidgets.QMessageBox.warning(self, "No data to save", "There is no data to save.")
            return

        filedialog = QtWidgets.QFileDialog(self)
        filedialog.setDefaultSuffix("s1p")
        filedialog.setNameFilter("Touchstone 1-Port Files (*.s1p);;All files (*.*)")
        filedialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        selected = filedialog.exec()
        if selected:
            filename = filedialog.selectedFiles()[0]
        else:
            return
        if filename == "":
            logger.debug("No file name selected.")
            return
        logger.debug("Save S1P file to %s", filename)
        if len(self.data) == 0:
            logger.warning("No data stored, nothing written.")
            return
        # TODO: should be delegated to Touchstone module
        try:
            logger.debug("Opening %s for writing", filename)
            with open(filename, "w+") as tsfile:
                logger.debug("Writing file")
                tsfile.write("# Hz S RI R 50\n")
                freq_prev = 0
                for data in self.data:
                    if data.freq <= freq_prev:
                        continue
                    tsfile.write(f"{data.freq} {data.re} {data.im}\n")
            logger.debug("File written")
        except Exception as e:
            logger.exception("Error during file export: %s", e)
            return

    def exportFileS2P(self):
        if len(self.data21) == 0:
            # No S21 data to save, alert the user
            QtWidgets.QMessageBox.warning(self, "No S21 data to save", "There is no S21 data to save.")
            return

        filedialog = QtWidgets.QFileDialog(self)
        filedialog.setDefaultSuffix("s2p")
        filedialog.setNameFilter("Touchstone 2-Port Files (*.s2p);;All files (*.*)")
        filedialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        selected = filedialog.exec()
        if selected:
            filename = filedialog.selectedFiles()[0]
        else:
            return
        if filename == "":
            logger.debug("No file name selected.")
            return
        logger.debug("Save S2P file to %s", filename)
        if len(self.data) == 0 or len(self.data21) == 0:
            logger.warning("No data stored, nothing written.")
            return
        # TODO: should be delegated to Touchstone module
        try:
            logger.debug("Opening %s for writing", filename)
            file = open(filename, "w+")
            logger.debug("Writing file")
            file.write("# Hz S RI R 50\n")
            for i in range(len(self.data)):
                if i == 0 or self.data[i].freq != self.data[i-1].freq:
                    file.write(str(self.data[i].freq) + " " + str(self.data[i].re) + " " + str(self.data[i].im) + " " +
                               str(self.data21[i].re) + " " + str(self.data21[i].im) + " 0 0 0 0\n")
            file.close()
            logger.debug("File written")
        except Exception as e:
            logger.exception("Error during file export: %s", e)
            return

    def serialButtonClick(self):
        if self.serial.is_open:
            self.stopSerial()
        else:
            self.startSerial()
        return

    def startSerial(self):
        if self.serialLock.acquire():
            self.serialPort = self.serialPortInput.currentData()
            if self.serialPort == "":
                self.serialPort = self.serialPortInput.currentText()
            logger.info("Opening serial port %s", self.serialPort)
            try:
                self.serial = serial.Serial(port=self.serialPort, baudrate=115200)
                self.serial.timeout = 0.05
            except serial.SerialException as exc:
                logger.error("Tried to open %s and failed: %s", self.serialPort, exc)
                self.serialLock.release()
                return
            self.btnSerialToggle.setText("Disconnect")

            self.serialLock.release()
            sleep(0.05)

            self.vna = get_VNA(self, self.serial)
            self.vna.validateInput = self.settings.value("SerialInputValidation", True, bool)
            self.worker.setVNA(self.vna)

            logger.info(self.vna.readFirmware())

            frequencies = self.vna.readFrequencies()
            if frequencies:
                logger.info("Read starting frequency %s and end frequency %s", frequencies[0], frequencies[100])
                if int(frequencies[0]) == int(frequencies[100]) and (self.sweepStartInput.text() == "" or
                                                                     self.sweepEndInput.text() == ""):
                    self.sweepStartInput.setText(RFTools.formatSweepFrequency(int(frequencies[0])))
                    self.sweepEndInput.setText(RFTools.formatSweepFrequency(int(frequencies[100]) + 100000))
                elif self.sweepStartInput.text() == "" or self.sweepEndInput.text() == "":
                    self.sweepStartInput.setText(RFTools.formatSweepFrequency(int(frequencies[0])))
                    self.sweepEndInput.setText(RFTools.formatSweepFrequency(int(frequencies[100])))
                self.sweepStartInput.textEdited.emit(self.sweepStartInput.text())
                self.sweepStartInput.textChanged.emit(self.sweepStartInput.text())
            else:
                logger.warning("No frequencies read")
                return
            logger.debug("Starting initial sweep")
            self.sweep()
            return

    def stopSerial(self):
        if self.serialLock.acquire():
            logger.info("Closing connection to NanoVNA")
            self.serial.close()
            self.serialLock.release()
            self.btnSerialToggle.setText("Connect to NanoVNA")

    def toggleSweepSettings(self, disabled):
        self.sweepStartInput.setDisabled(disabled)
        self.sweepEndInput.setDisabled(disabled)
        self.sweepSpanInput.setDisabled(disabled)
        self.sweepCenterInput.setDisabled(disabled)
        self.sweepCountInput.setDisabled(disabled)

    def sweep(self):
        # Run the serial port update
        if not self.serial.is_open:
            return
        self.worker.stopped = False

        self.sweepProgressBar.setValue(0)
        self.btnSweep.setDisabled(True)
        self.btnStopSweep.setDisabled(False)
        self.toggleSweepSettings(True)
        for m in self.markers:
            m.resetLabels()
        self.s11_min_rl_label.setText("")
        self.s11_min_swr_label.setText("")
        self.s21_min_gain_label.setText("")
        self.s21_max_gain_label.setText("")
        self.tdr_result_label.setText("")

        if self.sweepCountInput.text().isdigit():
            self.settings.setValue("Segments", self.sweepCountInput.text())

        logger.debug("Starting worker thread")
        self.threadpool.start(self.worker)

    def stopSweep(self):
        self.worker.stopped = True

    def saveData(self, data, data12, source=None):
        if self.dataLock.acquire(blocking=True):
            self.data = data
            self.data21 = data12
        else:
            logger.error("Failed acquiring data lock while saving.")
        self.dataLock.release()
        if source is not None:
            self.sweepSource = source
        elif self.sweepTitle != "":
            self.sweepSource = self.sweepTitle + " " + strftime("%Y-%m-%d %H:%M:%S", localtime())
        else:
            self.sweepSource = strftime("%Y-%m-%d %H:%M:%S", localtime())

    def markerUpdated(self, marker: Marker):
        if self.dataLock.acquire(blocking=True):
            marker.findLocation(self.data)
            for m in self.markers:
                m.resetLabels()
                m.updateLabels(self.data, self.data21)

            for c in self.subscribing_charts:
                c.update()
        self.dataLock.release()

    def dataUpdated(self):
        if self.dataLock.acquire(blocking=True):
            for m in self.markers:
                m.findLocation(self.data)
                m.resetLabels()
                m.updateLabels(self.data, self.data21)

            for c in self.s11charts:
                c.setData(self.data)

            for c in self.s21charts:
                c.setData(self.data21)

            for c in self.combinedCharts:
                c.setCombinedData(self.data, self.data21)

            self.sweepProgressBar.setValue(self.worker.percentage)
            self.tdr_window.updateTDR()

            # Find the minimum S11 VSWR:
            min_vswr = 100
            min_vswr_freq = -1
            for d in self.data:
                vswr = d.vswr
                if min_vswr > vswr > 0:
                    min_vswr = vswr
                    min_vswr_freq = d.freq

            if min_vswr_freq > -1:
                self.s11_min_swr_label.setText(str(round(min_vswr, 3)) + " @ " + RFTools.formatFrequency(min_vswr_freq))
                if min_vswr > 1:
                    self.s11_min_rl_label.setText(str(round(20*math.log10((min_vswr-1)/(min_vswr+1)), 3)) + " dB")
                else:
                    # Infinite return loss?
                    self.s11_min_rl_label.setText("\N{INFINITY} dB")
            else:
                self.s11_min_swr_label.setText("")
                self.s11_min_rl_label.setText("")
            min_gain = 100
            min_gain_freq = -1
            max_gain = -100
            max_gain_freq = -1
            for d in self.data21:
                gain = d.gain
                if gain > max_gain:
                    max_gain = gain
                    max_gain_freq = d.freq
                if gain < min_gain:
                    min_gain = gain
                    min_gain_freq = d.freq

            if max_gain_freq > -1:
                self.s21_min_gain_label.setText(
                    str(round(min_gain, 3)) + " dB @ " + RFTools.formatFrequency(min_gain_freq))
                self.s21_max_gain_label.setText(
                    str(round(max_gain, 3)) + " dB @ " + RFTools.formatFrequency(max_gain_freq))
            else:
                self.s21_min_gain_label.setText("")
                self.s21_max_gain_label.setText("")

        else:
            logger.error("Failed acquiring data lock while updating.")
        self.updateTitle()
        self.dataLock.release()
        self.dataAvailable.emit()

    def sweepFinished(self):
        self.sweepProgressBar.setValue(100)
        self.btnSweep.setDisabled(False)
        self.btnStopSweep.setDisabled(True)
        self.toggleSweepSettings(False)

    def updateCenterSpan(self):
        fstart = RFTools.parseFrequency(self.sweepStartInput.text())
        fstop = RFTools.parseFrequency(self.sweepEndInput.text())
        fspan = fstop - fstart
        fcenter = int(round((fstart+fstop)/2))
        if fspan < 0 or fstart < 0 or fstop < 0:
            return
        self.sweepSpanInput.setText(RFTools.formatSweepFrequency(fspan))
        self.sweepCenterInput.setText(RFTools.formatSweepFrequency(fcenter))

    def updateStartEnd(self):
        fcenter = RFTools.parseFrequency(self.sweepCenterInput.text())
        fspan = RFTools.parseFrequency(self.sweepSpanInput.text())
        if fspan < 0 or fcenter < 0:
            return
        fstart = int(round(fcenter - fspan/2))
        fstop = int(round(fcenter + fspan/2))
        if fstart < 0 or fstop < 0:
            return
        self.sweepStartInput.setText(RFTools.formatSweepFrequency(fstart))
        self.sweepEndInput.setText(RFTools.formatSweepFrequency(fstop))

    def updateStepSize(self):
        fspan = RFTools.parseFrequency(self.sweepSpanInput.text())
        if fspan < 0:
            return
        if self.sweepCountInput.text().isdigit():
            segments = int(self.sweepCountInput.text())
            if segments > 0:
                fstep = fspan / (segments * 101 - 1)
                self.sweepStepLabel.setText(RFTools.formatShortFrequency(fstep) + "/step")

    def setReference(self, s11data=None, s21data=None, source=None):
        if not s11data:
            s11data = self.data
        if not s21data:
            s21data = self.data21
        self.referenceS11data = s11data
        for c in self.s11charts:
            c.setReference(s11data)

        self.referenceS21data = s21data
        for c in self.s21charts:
            c.setReference(s21data)

        for c in self.combinedCharts:
            c.setCombinedReference(s11data, s21data)

        self.btnResetReference.setDisabled(False)

        if source is not None:
            # Save the reference source info
            self.referenceSource = source
        else:
            self.referenceSource = self.sweepSource
        self.updateTitle()

    def updateTitle(self):
        title = self.baseTitle
        insert = ""
        if self.sweepSource != "":
            insert += "Sweep: " + self.sweepSource + " @ " + str(len(self.data)) + " points"
        if self.referenceSource != "":
            if insert != "":
                insert += ", "
            insert += "Reference: " + self.referenceSource + " @ " + str(len(self.referenceS11data)) + " points"
        if insert != "":
            title = title + " (" + insert + ")"
        self.setWindowTitle(title)

    def toggleMarkerFrame(self):
        if self.marker_frame.isHidden():
            self.marker_frame.setHidden(False)
            self.settings.setValue("MarkersVisible", True)
            self.showMarkerButton.setText("Hide data")
        else:
            self.marker_frame.setHidden(True)
            self.settings.setValue("MarkersVisible", False)
            self.showMarkerButton.setText("Show data")

    def resetReference(self):
        self.referenceS11data = []
        self.referenceS21data = []
        self.referenceSource = ""
        self.updateTitle()
        for c in self.subscribing_charts:
            c.resetReference()
        self.btnResetReference.setDisabled(True)

    def loadReferenceFile(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(filter="Touchstone Files (*.s1p *.s2p);;All files (*.*)")
        if filename != "":
            self.resetReference()
            t = Touchstone(filename)
            t.load()
            self.setReference(t.s11data, t.s21data, filename)

    def loadSweepFile(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(filter="Touchstone Files (*.s1p *.s2p);;All files (*.*)")
        if filename != "":
            self.data = []
            self.data21 = []
            t = Touchstone(filename)
            t.load()
            self.saveData(t.s11data, t.s21data, filename)
            self.dataUpdated()

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(1100, 950)

    def displaySettingsWindow(self):
        self.displaySetupWindow.show()
        QtWidgets.QApplication.setActiveWindow(self.displaySetupWindow)

    def displaySweepSettingsWindow(self):
        self.sweepSettingsWindow.show()
        QtWidgets.QApplication.setActiveWindow(self.sweepSettingsWindow)

    def displayDeviceSettingsWindow(self):
        self.deviceSettingsWindow.show()
        QtWidgets.QApplication.setActiveWindow(self.deviceSettingsWindow)

    def displayCalibrationWindow(self):
        self.calibrationWindow.show()
        QtWidgets.QApplication.setActiveWindow(self.calibrationWindow)

    def displayFileWindow(self):
        self.fileWindow.show()
        QtWidgets.QApplication.setActiveWindow(self.fileWindow)

    def displayTDRWindow(self):
        self.tdr_window.show()
        QtWidgets.QApplication.setActiveWindow(self.tdr_window)

    def displayAnalysisWindow(self):
        self.analysis_window.show()
        QtWidgets.QApplication.setActiveWindow(self.analysis_window)

    def displayAboutWindow(self):
        self.aboutWindow.show()
        QtWidgets.QApplication.setActiveWindow(self.aboutWindow)

    def showError(self, text):
        QtWidgets.QMessageBox.warning(self, "Error", text)

    def showFatalSweepError(self):
        self.showError(self.worker.error_message)
        self.stopSerial()

    def showSweepError(self):
        self.showError(self.worker.error_message)
        self.serial.flushInput()  # Remove any left-over data
        self.sweepFinished()

    def popoutChart(self, chart: Chart):
        logger.debug("Requested popout for chart: %s", chart.name)
        new_chart = self.copyChart(chart)
        new_chart.isPopout = True
        new_chart.show()
        new_chart.setWindowTitle(new_chart.name)

    def copyChart(self, chart: Chart):
        new_chart = chart.copy()
        self.subscribing_charts.append(new_chart)
        if chart in self.s11charts:
            self.s11charts.append(new_chart)
        if chart in self.s21charts:
            self.s21charts.append(new_chart)
        if chart in self.combinedCharts:
            self.combinedCharts.append(new_chart)
        new_chart.popoutRequested.connect(self.popoutChart)
        return new_chart

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.worker.stopped = True
        self.settings.setValue("MarkerCount", Marker.count())
        for marker in self.markers:
            marker.update_settings()

        self.settings.setValue("WindowHeight", self.height())
        self.settings.setValue("WindowWidth", self.width())
        self.settings.sync()
        self.bands.saveSettings()
        self.threadpool.waitForDone(2500)
        a0.accept()
        sys.exit()

    def changeFont(self, font: QtGui.QFont) -> None:
        qf_new = QtGui.QFontMetricsF(font)
        normal_font = QtGui.QFont(font)
        normal_font.setPointSize(8)
        qf_normal = QtGui.QFontMetricsF(normal_font)
        standard_string = "0.123456789 0.123456789 MHz \N{OHM SIGN}"  # Characters we would normally display
        new_width = qf_new.boundingRect(standard_string).width()
        old_width = qf_normal.boundingRect(standard_string).width()
        self.scaleFactor = new_width / old_width
        logger.debug("New font width: %f, normal font: %f, factor: %f", new_width, old_width, self.scaleFactor)
        # TODO: Update all the fixed widths to account for the scaling
        for m in self.markers:
            m.getGroupBox().setFont(font)
            m.setScale(self.scaleFactor)

    def setSweepTitle(self, title):
        self.sweepTitle = title
        for c in self.subscribing_charts:
            c.setSweepTitle(title)
