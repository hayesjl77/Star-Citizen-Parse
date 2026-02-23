# Copyright (c) 2026 Squig-AI (squig-ai.com) — MIT License
# See LICENSE file for details.
"""
Real-time log file monitor using QFileSystemWatcher + polling fallback.
Emits new lines via Qt signals for thread-safe UI updates.
"""

import os
from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class LogMonitor(QObject):
    """Watches a log file for new lines and emits them as signals."""

    new_line = pyqtSignal(str)       # Emitted for each new line
    file_reset = pyqtSignal()         # Emitted when the file is truncated/recreated
    monitoring_started = pyqtSignal(str)  # Emitted with filepath when monitoring begins

    def __init__(self, poll_interval_ms: int = 500, parent=None):
        super().__init__(parent)
        self._filepath = None
        self._file_offset = 0
        self._file_size = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._poll_interval = poll_interval_ms

    @property
    def filepath(self) -> str:
        return self._filepath

    def start(self, filepath: str, read_existing: bool = False):
        """Start monitoring a log file."""
        self.stop()
        self._filepath = filepath

        if not os.path.isfile(filepath):
            print(f"[Monitor] File not found: {filepath}")
            return

        if read_existing:
            self._file_offset = 0
        else:
            # Start from end of file
            self._file_offset = os.path.getsize(filepath)

        self._file_size = os.path.getsize(filepath)
        self.monitoring_started.emit(filepath)
        self._timer.start(self._poll_interval)
        print(f"[Monitor] Watching: {filepath} (offset: {self._file_offset})")

    def stop(self):
        """Stop monitoring."""
        self._timer.stop()
        self._filepath = None
        self._file_offset = 0

    def reprocess(self):
        """Re-read the entire log file from the beginning."""
        if self._filepath:
            self._file_offset = 0
            self._poll()

    def _poll(self):
        """Check for new data in the log file."""
        if not self._filepath or not os.path.isfile(self._filepath):
            return

        try:
            current_size = os.path.getsize(self._filepath)

            # File was truncated or recreated (new game session)
            if current_size < self._file_offset:
                self._file_offset = 0
                self.file_reset.emit()

            if current_size > self._file_offset:
                with open(self._filepath, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(self._file_offset)
                    new_data = f.read()
                    self._file_offset = f.tell()

                for line in new_data.splitlines():
                    line = line.strip()
                    if line:
                        self.new_line.emit(line)

            self._file_size = current_size

        except Exception as e:
            print(f"[Monitor] Poll error: {e}")
