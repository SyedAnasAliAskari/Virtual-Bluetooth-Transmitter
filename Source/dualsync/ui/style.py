STYLESHEET = """
QWidget { color: #eeeae0; font: 10pt "Segoe UI"; }
QLabel { background: transparent; border: none; }
QFrame#popup, QDialog { background: #101012; }
QFrame#popup { border: 1px solid #332d22; border-radius: 14px; }
QFrame#deviceRow {
    background: #171719; border: 1px solid #343238; border-radius: 11px;
}
QFrame#sourceBar {
    background: #161618; border: 1px solid #302d28; border-radius: 9px;
}
QFrame#emptyState {
    background: #151517; border: 1px dashed #343238; border-radius: 10px;
}
QLabel#title { color: #fffaf0; font-size: 18pt; font-weight: 650; }
QLabel#eyebrow {
    color: #d7ac53; font-size: 8pt; font-weight: 700; letter-spacing: 1px;
}
QLabel#muted { color: #99968f; }
QLabel#fieldLabel { color: #aaa69e; font-size: 9pt; }
QLabel#value { color: #eeeae0; font-size: 9pt; min-width: 35px; }
QLabel#deviceStatus { color: #b9a77f; font-size: 9pt; }
QLabel#sourceName { color: #d8d4ca; font-size: 9pt; }
QLabel#sectionTitle { color: #e5e1d8; font-weight: 600; }
QLabel#emptyTitle { color: #ded9cf; font-weight: 600; }
QPushButton#statusOn {
    color: #f1d584; background: #2a2418; border: 1px solid #665128;
    border-radius: 9px; padding: 4px 12px; font-weight: 700; min-height: 24px;
}
QPushButton#statusOff {
    color: #aaa69e; background: #19191c; border: 1px solid #36353b;
    border-radius: 9px; padding: 4px 12px; font-weight: 700; min-height: 24px;
}
QPushButton#statusOn:hover, QPushButton#statusOff:hover { border-color: #d9ad50; }
QFrame#deviceSlot {
    min-height: 58px; background: #151517; border: 1px dashed #454149;
    border-radius: 9px;
}
QFrame#deviceSlot:hover { background: #1d1b18; border-color: #a17d37; }
QLabel#slotRole { color: #8e8a83; font-size: 7pt; font-weight: 700; }
QLabel#slotEmpty { color: #d9ad50; font-size: 18pt; font-weight: 400; }
QLabel#slotName { color: #eeeae0; font-size: 8pt; font-weight: 600; }
QPushButton {
    min-height: 20px; background: #202023; border: 1px solid #3a393f;
    border-radius: 8px; padding: 7px 12px; text-align: center;
}
QPushButton:hover { background: #292722; border-color: #8b713a; }
QPushButton:pressed { background: #312915; }
QPushButton:disabled { color: #615f5a; border-color: #262629; }
QPushButton#primary {
    color: #18130a; background: #d9ad50; border: 1px solid #efc76f;
    font-weight: 700;
}
QPushButton#primary:hover { background: #e7bc61; }
QPushButton#danger { color: #e4b7ac; }
QPushButton#danger:hover { border-color: #805048; background: #2a2020; }
QToolButton#minimizeButton, QToolButton#closeButton {
    min-width: 34px; min-height: 34px; padding: 0; border-radius: 9px;
    border: 1px solid transparent; background: transparent;
}
QToolButton#minimizeButton:hover { border-color: #3a393f; background: #242428; }
QToolButton#closeButton:hover { border-color: #a44747; background: #8f3030; }
QPushButton#compact { min-height: 18px; padding: 5px 9px; font-size: 9pt; }
QComboBox, QSpinBox, QDoubleSpinBox {
    background: #1b1b1e; border: 1px solid #3a393f; border-radius: 7px;
    padding: 6px 8px; selection-background-color: #6f5625;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #8b713a; }
QSlider::groove:horizontal {
    height: 4px; background: #35343a; border-radius: 2px;
}
QSlider::sub-page:horizontal { background: #d6a84b; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 14px; margin: -5px 0; background: #f4d98a;
    border: 1px solid #8a5a12; border-radius: 7px;
}
QScrollArea, QScrollArea QWidget { border: 0; background: transparent; }
QScrollBar:vertical { background: transparent; width: 7px; margin: 2px 0; }
QScrollBar::handle:vertical {
    background: #4b4437; border-radius: 3px; min-height: 28px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip {
    background: #24231f; color: #fff8e7; border: 1px solid #6f5625; padding: 5px;
}
QMenu { background: #18181b; border: 1px solid #3a393f; padding: 5px; }
QMenu::item { padding: 7px 24px 7px 12px; border-radius: 5px; }
QMenu::item:selected { background: #2a251b; color: #f1d584; }
QTabWidget#deviceTabs::pane {
    border: 1px solid #343238; border-radius: 10px; background: #121214;
    top: -1px; padding: 10px;
}
QTabBar::tab {
    color: #99968f; background: transparent; border: none;
    padding: 8px 16px; margin-right: 4px;
}
QTabBar::tab:selected {
    color: #f1d584; border-bottom: 2px solid #d9ad50; font-weight: 600;
}
QTabBar::tab:hover { color: #e7e1d6; }
"""
