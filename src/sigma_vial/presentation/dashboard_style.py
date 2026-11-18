"""Paleta y estados visuales del tablero SIGMA."""

STYLE = """
QWidget { color: #0e213f; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow, QWidget#root, QScrollArea#bodyScroll { background: #edf1f8; }
QFrame#header { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
    stop:0 #082448, stop:1 #193a63); border: none; }
QFrame#header QLabel { background: transparent; color: white; }
QLabel#title { font-size: 30px; font-weight: 800; }
QLabel#company { color: #b9c9df; font-size: 12px; }
QLabel#subtitle { font-size: 15px; }
QLabel#status { font-size: 14px; font-weight: 600; }
QFrame#card { background: #fcfdff; border: 1px solid #cbd5e4; border-radius: 12px; }
QFrame#controls { background: #f8faff; border-bottom: 1px solid #d0d9e8; }
QLabel { background: transparent; }
QLabel#section { color: #0b2448; font-size: 21px; font-weight: 700; }
QLabel#muted { color: #536583; font-size: 12px; }
QLabel#clock { font-size: 15px; font-weight: 600; }
QLabel#badge { background: #e0e7f1; color: #52627e; border-radius: 9px; padding: 4px 9px; }
QLabel#summary { background: #edf2f8; border: 1px solid #d5dfed;
    border-radius: 9px; padding: 9px; font-weight: 600; }
QLabel#decision { background: #d6f4ed; border: 1px solid #b7e7db;
    border-radius: 9px; padding: 9px; }
QLabel#reading { color: #092a24; font-size: 15px; font-weight: 600; }
QLabel#confirmation { background: #e7edf5; color: #536583; border-radius: 12px; padding: 7px; }
QLabel#confirmation[state="confirmed"] { background: #d5f5e9; color: #08724f; }
QLabel#confirmation[state="pending"] { background: #fff1d3; color: #956500; }
QLabel#confirmation[state="error"] { background: #f8e4e5; color: #9a4249; }
QLabel#record { border-top: 1px solid #d4deeb; padding-top: 10px; font-size: 14px; }
QPushButton { background: #f7f9ff; color: #0e213f; border: 1px solid #aab8ce;
    border-radius: 8px; padding: 7px 12px; font-weight: 600; }
QPushButton:hover { background: #e7f2ff; border-color: #318fc7; }
QPushButton:pressed { background: #d5e8fc; }
QPushButton:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #04b99a; }
QPushButton:disabled { color: #8795ab; background: #e7ecf3; border-color: #d6deea; }
QPushButton#primaryAction { background: #073c87; color: white; border-color: #073c87; }
QPushButton#primaryAction:hover { background: #1457a7; }
QToolButton { background: #f0f5fb; border: none; border-radius: 5px;
    padding: 5px 8px; color: #465e7d; text-align: left; }
QToolButton:checked { color: #007d6a; background: #e0f5ee; }
QToolButton:hover { background: #deeee9; }
QComboBox, QSpinBox, QDoubleSpinBox { background: #fdfefe; color: #172f50;
    border: 1px solid #abbad0; border-radius: 7px; padding: 5px 7px; min-height: 22px; }
QComboBox QAbstractItemView { background: white; color: #172f50;
    selection-background-color: #d2f2e9; selection-color: #0a554b; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { padding: 10px 20px; font-size: 16px; color: #263f5d;
    border-bottom: 1px solid #bfcbe0; background: transparent; }
QTabBar::tab:selected { background: #d4f2eb; color: #092644;
    border-bottom: 4px solid #04b89a; font-weight: 700; }
QTabBar::tab:hover { background: #e6f7f1; }
QCheckBox { spacing: 10px; padding: 4px 0; }
QCheckBox::indicator { width: 40px; height: 22px; border-radius: 11px;
    background: #a8b7c9; border: 1px solid #a8b7c9; }
QCheckBox::indicator:checked { background: #04bc9b; border-color: #04bc9b; }
QCheckBox::indicator:focus { border: 2px solid #073c87; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: #e6edf5; width: 7px; margin: 0; }
QScrollBar::handle:vertical { background: #a9bacd; min-height: 25px; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""
