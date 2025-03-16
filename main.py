import sys
import re
import webbrowser
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QPushButton, QWidget, QFileDialog,
    QMenuBar, QMenu, QDialog, QListWidget, QHBoxLayout, QTextEdit, QLabel, QLineEdit
)
from PyQt6.QtGui import QAction, QTextCursor
from PyQt6.QtCore import Qt, QPoint, QRect
from functools import partial
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


# LogFileMonitor Class: Tracks file changes and processes logs
class LogFileMonitor(FileSystemEventHandler):
    def __init__(self, callback, tags=None):
        super().__init__()
        self.callback = callback
        self.filepath = None
        self.file_offset = 0
        self.tags = tags or []

    def set_filepath(self, filepath):
        self.filepath = filepath
        self.file_offset = 0
        self.read_existing_file()

    def read_existing_file(self):
        if not self.filepath:
            return
        try:
            with open(self.filepath, "r") as file:
                for line in file:
                    self.process_line(line.strip())
                self.file_offset = file.tell()
        except Exception as e:
            print(f"Error while reading file: {e}")

    def on_modified(self, event):
        if self.filepath and event.src_path == self.filepath:
            try:
                with open(self.filepath, "r") as file:
                    file.seek(self.file_offset)
                    for line in file:
                        self.process_line(line.strip())
                    self.file_offset = file.tell()
            except Exception as e:
                print(f"Error while reading new changes: {e}")

    def process_line(self, line):
        for tag in self.tags:
            if re.search(re.escape(tag), line):
                self.callback(tag, line)
                break

    def reparse_log_file(self, tag_name=None):
        if not self.filepath:
            return
        try:
            with open(self.filepath, "r") as file:
                lines = file.readlines()
            if tag_name:
                tag_lines = [line.strip() for line in lines if re.search(re.escape(tag_name), line)]
                for line in tag_lines:
                    self.callback(tag_name, line)
            else:
                for line in lines:
                    self.process_line(line.strip())
        except Exception as e:
            print(f"Error reparsing log file: {e}")


# OverlayWindow Class: Main Application Window
class OverlayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Enable frameless design
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150); border-radius: 10px;")
        self.setGeometry(100, 100, 800, 600)

        # Variables for dragging and resizing
        self._drag_active = False
        self._drag_position = QPoint()
        self._resizing = False
        self._resize_margin = 8
        self._resize_direction = None
        self._initial_geometry = None

        # Minimum size for resizing
        self.setMinimumSize(400, 300)

        # Tags and colors
        self.tags = ["<Actor Death>", "<Corpse>", "<Jump Drive Changing State>"]
        self.tag_colors = {
            "<Actor Death>": "orange",
            "<Corpse>": "yellow",
            "<Jump Drive Changing State>": "green",
        }

        # Dictionary to hold log sections by tag
        self.log_sections = {}

        # Central widget and layout
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("background-color: rgba(0, 0, 0, 150); border-radius: 10px;")
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        self.create_all_tag_sections()

        self.exit_button = QPushButton("Exit")
        self.exit_button.clicked.connect(self.close_application)
        self.exit_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        self.layout.addWidget(self.exit_button)

        # Menu Bar
        self.menu = QMenuBar(self)
        self.menu.setStyleSheet("background-color: rgba(0, 0, 0, 150); color: white; font-size: 14px;")
        self.setMenuBar(self.menu)

        # File menu
        file_menu = self.menu.addMenu("File")
        open_file = QAction("Open Log File", self)
        open_file.triggered.connect(self.choose_file)
        file_menu.addAction(open_file)

        # Tags menu
        tags_menu = self.menu.addMenu("Tags")
        manage_tags = QAction("Manage Tags", self)
        manage_tags.triggered.connect(self.open_tag_manager)
        tags_menu.addAction(manage_tags)

        # Donate menu
        donate_menu = self.menu.addMenu("Donate")
        donate_action = QAction("Donate to Developer", self)
        donate_action.triggered.connect(self.open_donate_link)
        donate_menu.addAction(donate_action)

        self.start_file_watcher()

    ### Moving and Resizing ###
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_on_resize_edge(event.pos()) and not self.is_on_left_edge(event.pos()):
                self._resizing = True
                self._resize_direction = self.get_resize_direction(event.pos())
                self._initial_geometry = self.geometry()
                self._drag_position = event.globalPosition().toPoint()
            else:
                self._drag_active = True
                self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._resizing:
            delta = event.globalPosition().toPoint() - self._drag_position
            rect = QRect(self._initial_geometry)
            if "Right" in self._resize_direction:
                rect.setRight(rect.right() + delta.x())
            if "Bottom" in self._resize_direction:
                rect.setBottom(rect.bottom() + delta.y())
            if "Left" in self._resize_direction:
                rect.setLeft(rect.left() + delta.x())
            if "Top" in self._resize_direction:
                rect.setTop(rect.top() + delta.y())
            if rect.width() >= self.minimumWidth() and rect.height() >= self.minimumHeight():
                self.setGeometry(rect)
        elif self._drag_active:
            self.move(event.globalPosition().toPoint() - self._drag_position)
        elif self.is_on_resize_edge(event.pos()) and not self.is_on_left_edge(event.pos()):
            self.setCursor(self.get_resize_cursor(event.pos()))
        else:
            self.unsetCursor()

    def mouseReleaseEvent(self, event):
        self._drag_active = False
        self._resizing = False
        event.accept()

    def is_on_resize_edge(self, pos):
        rect = self.rect()
        return (pos.x() >= rect.width() - self._resize_margin or
                pos.y() >= rect.height() - self._resize_margin or
                pos.x() <= self._resize_margin or
                pos.y() <= self._resize_margin)

    def is_on_left_edge(self, pos):
        # Check if the position is within the left edge but not resizing
        return pos.x() <= self._resize_margin

    def get_resize_direction(self, pos):
        rect = self.rect()
        direction = ""
        if pos.x() >= rect.width() - self._resize_margin:
            direction += "Right"
        if pos.y() >= rect.height() - self._resize_margin:
            direction += "Bottom"
        if pos.x() <= self._resize_margin and not self.is_on_left_edge(pos):
            direction += "Left"
        if pos.y() <= self._resize_margin:
            direction += "Top"
        return direction

    def get_resize_cursor(self, pos):
        direction = self.get_resize_direction(pos)
        if direction in ("RightBottom", "LeftTop"):
            return Qt.CursorShape.SizeFDiagCursor
        elif direction in ("RightTop", "LeftBottom"):
            return Qt.CursorShape.SizeBDiagCursor
        elif "Right" in direction or "Left" in direction:
            return Qt.CursorShape.SizeHorCursor
        elif "Top" in direction or "Bottom" in direction:
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    ### Existing Functionalities ###
    def open_donate_link(self):
        webbrowser.open("https://paypal.me/hayesjl77?country.x=US&locale.x=en_US")

    def create_all_tag_sections(self):
        for tag in self.tags:
            self.add_tag_section(tag)

    def add_tag_section(self, tag):
        if tag not in self.log_sections:
            text_edit, container = self.create_scrollable_section(tag)
            self.layout.insertWidget(self.layout.count() - 1, container)
            self.log_sections[tag] = text_edit

    def create_scrollable_section(self, tag):
        container = QWidget()
        container_layout = QVBoxLayout(container)
        title = QPushButton(f"[{tag}] Logs (Click to Clear)")
        title.setStyleSheet(f"color: {self.tag_colors.get(tag, 'white')}; font-weight: bold;")
        title.clicked.connect(partial(self.clear_logs, tag))
        container_layout.addWidget(title)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("""
            background-color: black;
            color: white;
            font-size: 14px;
            font-weight: bold;
        """)
        container_layout.addWidget(text_edit)
        return text_edit, container

    def update_log_section(self, tag, message):
        if tag in self.log_sections:
            text_edit = self.log_sections[tag]
            text_edit.moveCursor(QTextCursor.MoveOperation.End)
            color = self.tag_colors.get(tag, "white")
            text_edit.append(f"<span style='color:{color}'>{message}</span>")

    def clear_logs(self, tag):
        if tag in self.log_sections:
            self.log_sections[tag].clear()

    def start_file_watcher(self):
        self.log_monitor = LogFileMonitor(self.add_event, self.tags)
        self.observer = Observer()
        self.observer.schedule(self.log_monitor, ".", recursive=False)
        self.observer.start()

    def add_event(self, category, event_text):
        self.update_log_section(category, event_text)

    def open_tag_manager(self):
        dialog = TagManagerDialog(self, self.tags)
        if dialog.exec():
            self.tags = dialog.tags
            self.log_monitor.tags = self.tags
            self.reparse_log_file()
            self.update_ui_for_tags()

    def reparse_log_file(self):
        self.log_monitor.read_existing_file()

    def update_ui_for_tags(self):
        current_tags = set(self.log_sections.keys())
        new_tags = set(self.tags)
        for tag in current_tags - new_tags:
            self.remove_tag_section(tag)
        for tag in new_tags - current_tags:
            self.add_tag_section(tag)

    def remove_tag_section(self, tag):
        if tag in self.log_sections:
            text_edit = self.log_sections.pop(tag)
            container = text_edit.parentWidget()
            self.layout.removeWidget(container)
            container.deleteLater()

    def choose_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Log File")
        if filepath:
            for text_edit in self.log_sections.values():
                text_edit.clear()
            self.log_monitor.set_filepath(filepath)

    def close_application(self):
        self.observer.stop()
        self.observer.join()
        QApplication.quit()


class TagManagerDialog(QDialog):
    def __init__(self, parent, tags):
        super().__init__(parent)
        self.tags = tags
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        self.setMinimumSize(400, 300)

        self.layout = QVBoxLayout(self)

        self.tag_list = QListWidget(self)
        self.tag_list.setStyleSheet("""
            color: white;
            background-color: black;
            font-size: 14px;
            border: 1px solid white;
        """)
        self.tag_list.addItems(tags)
        self.layout.addWidget(self.tag_list)

        buttons = QHBoxLayout()
        add_button = QPushButton("Add Tag")
        add_button.setStyleSheet("""
            background-color: #333; color: white; border-radius: 5px;
        """)
        add_button.clicked.connect(self.add_tag)
        remove_button = QPushButton("Remove Tag")
        remove_button.setStyleSheet("""
            background-color: #333; color: white; border-radius: 5px;
        """)
        remove_button.clicked.connect(self.remove_selected_tag)
        buttons.addWidget(add_button)
        buttons.addWidget(remove_button)
        self.layout.addLayout(buttons)

        dialog_buttons = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.setStyleSheet("background-color: green; color: white; border-radius: 5px;")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("background-color: red; color: white; border-radius: 5px;")
        cancel_button.clicked.connect(self.reject)
        dialog_buttons.addWidget(ok_button)
        dialog_buttons.addWidget(cancel_button)
        self.layout.addLayout(dialog_buttons)

    def add_tag(self):
        dialog = AddTagDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_tag = dialog.new_tag
            if new_tag:
                self.tags.append(new_tag)
                self.tag_list.addItem(new_tag)
                if hasattr(self.parent(), 'add_new_tag_and_update'):
                    self.parent().add_new_tag_and_update(new_tag)

    def remove_selected_tag(self):
        for item in self.tag_list.selectedItems():
            self.tags.remove(item.text())
            self.tag_list.takeItem(self.tag_list.row(item))


class AddTagDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 180); color: white;")
        self.setWindowTitle("Add Tag")
        self.setFixedSize(400, 200)
        self.new_tag = ""

        layout = QVBoxLayout(self)

        self.label = QLabel("Enter new tag:")
        self.label.setStyleSheet("font-size: 14px; color: white;")
        layout.addWidget(self.label)

        self.input_field = QLineEdit()
        self.input_field.setStyleSheet("background-color: black; color: white; border: 1px solid white;")
        layout.addWidget(self.input_field)

        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.setStyleSheet("background-color: green; color: white; border-radius: 5px;")
        self.ok_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("background-color: red; color: white; border-radius: 5px;")
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

    def accept(self):
        self.new_tag = self.input_field.text().strip()
        super().accept()

    def reject(self):
        super().reject()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OverlayWindow()
    window.show()
    sys.exit(app.exec())
