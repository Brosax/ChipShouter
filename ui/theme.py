"""
Dark-theme QSS stylesheet for the application.

Extracted from MainWindow.apply_dark_theme() so it can be reused or
swapped without touching widget code.
"""

DARK_THEME_QSS = """
QMainWindow, QWidget {
    background-color: #121212;
    color: #e0e0e0;
}
QGroupBox {
    border: 1px solid #444;
    border-radius: 6px;
    margin-top: 12px;
    font-weight: bold;
    color: #ddd;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
}
QPushButton {
    background-color: #333;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px;
    color: #fff;
}
QPushButton:hover {
    background-color: #444;
    border-color: #666;
}
QPushButton:pressed {
    background-color: #222;
    border-color: #444;
}
QPushButton:disabled {
    background-color: #1a1a1a;
    color: #555;
    border-color: #333;
}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #1e1e1e;
    color: #eee;
    border: 1px solid #444;
    border-radius: 3px;
    padding: 4px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #007acc;
}
QTabWidget::pane {
    border: 1px solid #444;
    top: -1px;
}
QTabBar::tab {
    background: #222;
    color: #888;
    padding: 8px 16px;
    border: 1px solid #444;
    border-bottom: none;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background: #333;
    color: #fff;
    border-bottom: 2px solid #007acc;
}
QTabBar::tab:hover {
    background: #2a2a2a;
}
QScrollBar:vertical {
    background: #121212;
    width: 12px;
}
QScrollBar::handle:vertical {
    background: #444;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QLabel { color: #ccc; }
QDockWidget {
    color: #e0e0e0;
    border: 1px solid #444;
}
QDockWidget::title {
    background: #2a2a2a;
    padding-left: 5px;
    padding-top: 2px;
    border-bottom: 1px solid #444;
}
"""
