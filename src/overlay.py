# Copyright (c) 2026 Squig-AI (squig-ai.com) — MIT License
# See LICENSE file for details.
"""
Squig-AI SC Parse — Transparent in-game overlay.
Shows a live kill/death feed, session stats, and event log on top of the game.
"""

import os
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QScrollArea, QFileDialog, QMenu, QSystemTrayIcon, QSlider, QLineEdit,
    QPushButton, QCheckBox, QDialog, QFormLayout, QDialogButtonBox,
    QFrame, QToolTip,
)
from PyQt6.QtGui import (
    QAction, QIcon, QFont, QColor, QPainter, QPainterPath, QCursor,
    QKeySequence, QShortcut,
)
from PyQt6.QtCore import Qt, QPoint, QSize, QTimer, QEvent, pyqtSignal

from src.config import Config
from src.event_parser import EventType, GameEvent, parse_line
from src.log_monitor import LogMonitor
from src.log_detector import find_game_logs, find_most_recent_log, extract_player_name


# ─── Color Scheme ──────────────────────────────────────────────────────────

COLORS = {
    EventType.PVP_KILL:          "#ff4444",    # Red — PvP kill
    EventType.PVE_KILL:          "#44ff44",    # Green — PvE kill
    EventType.DEATH:             "#ff6600",    # Orange — you died
    EventType.DEATH_OTHER:       "#cc8800",    # Dark orange — someone else died
    EventType.VEHICLE_DESTROYED: "#ff3333",    # Red — vehicle blown up
    EventType.SUICIDE:           "#ff00ff",    # Magenta — suicide
    EventType.CORPSE:            "#888888",    # Gray — corpse
    EventType.JUMP:              "#00ccff",    # Cyan — quantum jump
    EventType.DISCONNECT:        "#ff0000",    # Red — disconnect
    EventType.ACTOR_STALL:       "#ffaa00",    # Amber — stall
    EventType.FPS_KILL:          "#66ff66",    # Light green
    EventType.FPS_DEATH:         "#ff8844",    # Light orange
    EventType.UNKNOWN:           "#666666",    # Dark gray
}

ICONS = {
    EventType.PVP_KILL:          "⚔",
    EventType.PVE_KILL:          "🎯",
    EventType.DEATH:             "☠",
    EventType.DEATH_OTHER:       "💀",
    EventType.VEHICLE_DESTROYED: "💥",
    EventType.SUICIDE:           "🔄",
    EventType.CORPSE:            "⚰",
    EventType.JUMP:              "🚀",
    EventType.DISCONNECT:        "📡",
    EventType.ACTOR_STALL:       "⏸",
    EventType.FPS_KILL:          "🔫",
    EventType.FPS_DEATH:         "🩸",
    EventType.UNKNOWN:           "❓",
}


def format_event(event: GameEvent, player_name: str = None) -> str:
    """Format a GameEvent into a human-readable one-liner for the feed."""
    icon = ICONS.get(event.event_type, "•")
    t = event.timestamp
    pn = player_name.lower() if player_name else ""

    if event.event_type == EventType.DEATH:
        killer_display = event.killer or "Unknown"
        extra = f" ({event.damage_type})" if event.damage_type else ""
        ship = f" [{event.ship}]" if event.ship else ""
        return f"{icon} {t}  {killer_display} killed YOU{extra}{ship}"

    if event.event_type in (EventType.PVP_KILL, EventType.PVE_KILL, EventType.FPS_KILL):
        victim_display = event.victim or "Unknown"
        weapon = f" ({event.weapon})" if event.weapon else ""
        dtype = f" [{event.damage_type}]" if event.damage_type and not event.weapon else ""
        ship = f" in {event.ship}" if event.ship else ""

        if pn and event.killer and event.killer.lower() == pn:
            return f"{icon} {t}  You killed {victim_display}{weapon}{dtype}{ship}"
        else:
            killer = event.killer or "Someone"
            return f"{icon} {t}  {killer} killed {victim_display}{weapon}{dtype}{ship}"

    if event.event_type == EventType.DEATH_OTHER:
        return f"{icon} {t}  {event.killer or '?'} killed {event.victim or '?'}"

    if event.event_type == EventType.VEHICLE_DESTROYED:
        level = "DESTROYED" if event.destruction_level == "full" else "disabled"
        return f"{icon} {t}  {event.vehicle_name or 'Vehicle'} {level}"

    if event.event_type == EventType.SUICIDE:
        who = event.victim or "Someone"
        if pn and who.lower() == pn:
            who = "You"
        return f"{icon} {t}  {who} committed suicide"

    if event.event_type == EventType.CORPSE:
        return f"{icon} {t}  Corpse: {event.victim or 'Unknown'}"

    if event.event_type == EventType.JUMP:
        return f"{icon} {t}  Quantum: {event.jump_state}"

    if event.event_type == EventType.DISCONNECT:
        return f"{icon} {t}  ⚠ DISCONNECTED"

    if event.event_type == EventType.ACTOR_STALL:
        return f"{icon} {t}  ⚠ Actor Stall"

    return f"• {t}  {event.raw_line[:80]}"


# ─── Settings Dialog ───────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    """Settings dialog for configuring the overlay."""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Squig-AI SC Parse — Settings")
        self.setFixedWidth(400)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a2e; color: #ffffff; }
            QLabel { color: #cccccc; font-size: 12px; }
            QLineEdit { background: #0d0d1a; border: 1px solid #333; border-radius: 4px;
                        color: white; padding: 6px; }
            QCheckBox { color: #cccccc; spacing: 8px; }
            QCheckBox::indicator { width: 16px; height: 16px; }
            QPushButton { background: #2d1b69; color: white; border: none;
                         border-radius: 4px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background: #3d2b89; }
            QSlider::groove:horizontal { background: #333; height: 6px; border-radius: 3px; }
            QSlider::handle:horizontal { background: #8b5cf6; width: 16px; height: 16px;
                                         border-radius: 8px; margin: -5px 0; }
        """)

        layout = QVBoxLayout(self)

        # Player name
        form = QFormLayout()
        self.player_input = QLineEdit(config.player_name or "")
        self.player_input.setPlaceholderText("Your Star Citizen handle")
        form.addRow("Player Name:", self.player_input)

        # Opacity
        opacity_row = QHBoxLayout()
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(int(config.overlay.opacity * 100))
        self.opacity_label = QLabel(f"{int(config.overlay.opacity * 100)}%")
        self.opacity_slider.valueChanged.connect(
            lambda v: self.opacity_label.setText(f"{v}%"))
        opacity_row.addWidget(self.opacity_slider)
        opacity_row.addWidget(self.opacity_label)
        form.addRow("Opacity:", opacity_row)

        # Font size
        font_row = QHBoxLayout()
        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setRange(9, 24)
        self.font_slider.setValue(config.overlay.font_size)
        self.font_label = QLabel(f"{config.overlay.font_size}px")
        self.font_slider.valueChanged.connect(
            lambda v: self.font_label.setText(f"{v}px"))
        font_row.addWidget(self.font_slider)
        font_row.addWidget(self.font_label)
        form.addRow("Font Size:", font_row)

        # Hotkey
        self.hotkey_input = QLineEdit(config.toggle_hotkey)
        form.addRow("Toggle Hotkey:", self.hotkey_input)

        layout.addLayout(form)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #333;")
        layout.addWidget(sep)

        # Event filters
        layout.addWidget(QLabel("Show Events:"))
        filters_layout = QVBoxLayout()

        self.filter_checks = {}
        filter_map = {
            "PvP Kills": "show_pvp_kills",
            "PvE Kills": "show_pve_kills",
            "Deaths": "show_deaths",
            "Vehicle Destroyed": "show_vehicle_destroyed",
            "Quantum Jumps": "show_jumps",
            "Corpses": "show_corpses",
            "Disconnects": "show_disconnects",
            "Suicides": "show_suicides",
        }

        for label_text, attr in filter_map.items():
            cb = QCheckBox(label_text)
            cb.setChecked(getattr(config, attr))
            self.filter_checks[attr] = cb
            filters_layout.addWidget(cb)

        layout.addLayout(filters_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.setStyleSheet("""
            QPushButton { min-width: 80px; }
        """)
        layout.addWidget(buttons)

    def apply_to_config(self):
        """Write dialog values back to config."""
        self.config.player_name = self.player_input.text().strip() or None
        self.config.overlay.opacity = self.opacity_slider.value() / 100.0
        self.config.overlay.font_size = self.font_slider.value()
        self.config.toggle_hotkey = self.hotkey_input.text().strip() or "shift+f1"

        for attr, cb in self.filter_checks.items():
            setattr(self.config, attr, cb.isChecked())


# ─── Main Overlay Window ──────────────────────────────────────────────────

class OverlayWindow(QMainWindow):
    """The main transparent overlay window."""

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.events: list[GameEvent] = []
        self.stats = {"kills": 0, "deaths": 0, "pve": 0}
        self._locked = False          # Lock prevents drag/resize
        self._click_through = False   # Click-through passes input to game

        # ─── Window flags for true overlay ───
        self._base_flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # Hides from taskbar
        )
        self.setWindowFlags(self._base_flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(300, 200)
        self.setGeometry(
            config.overlay.x, config.overlay.y,
            config.overlay.width, config.overlay.height,
        )

        # ─── Central widget ───
        central = QWidget()
        central.setObjectName("overlay_bg")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ─── Title bar ───
        title_bar = QWidget()
        title_bar.setObjectName("title_bar")
        title_bar.setFixedHeight(32)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(10, 0, 6, 0)

        self.title_label = QLabel("SQUIG-AI  SC PARSE")
        self.title_label.setObjectName("title_text")
        title_layout.addWidget(self.title_label)

        title_layout.addStretch()

        # Stats in title bar
        self.stats_label = QLabel("K: 0  D: 0  PvE: 0")
        self.stats_label.setObjectName("stats_text")
        title_layout.addWidget(self.stats_label)

        # Help button (shows keyboard shortcuts)
        help_btn = QPushButton("?")
        help_btn.setObjectName("title_btn")
        help_btn.setFixedSize(24, 24)
        help_btn.setToolTip("Keyboard Shortcuts")
        help_btn.clicked.connect(self._show_help)
        title_layout.addWidget(help_btn)

        # Lock button (prevents accidental drag/resize)
        self.lock_btn = QPushButton("🔓")
        self.lock_btn.setObjectName("title_btn")
        self.lock_btn.setFixedSize(24, 24)
        self.lock_btn.setToolTip("Lock position (Ctrl+L)")
        self.lock_btn.clicked.connect(self._toggle_lock)
        title_layout.addWidget(self.lock_btn)

        # Click-through toggle
        self.passthru_btn = QPushButton("👆")
        self.passthru_btn.setObjectName("title_btn")
        self.passthru_btn.setFixedSize(24, 24)
        self.passthru_btn.setToolTip("Click-through mode (Ctrl+P)")
        self.passthru_btn.clicked.connect(self._toggle_click_through)
        title_layout.addWidget(self.passthru_btn)

        # Settings gear button
        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("title_btn")
        settings_btn.setFixedSize(24, 24)
        settings_btn.clicked.connect(self.open_settings)
        title_layout.addWidget(settings_btn)

        # Minimize button
        min_btn = QPushButton("─")
        min_btn.setObjectName("title_btn")
        min_btn.setFixedSize(24, 24)
        min_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(min_btn)

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.quit_app)
        title_layout.addWidget(close_btn)

        root_layout.addWidget(title_bar)

        # ─── Status bar ───
        self.status_label = QLabel("  Waiting for log file...")
        self.status_label.setObjectName("status_bar")
        self.status_label.setFixedHeight(20)
        root_layout.addWidget(self.status_label)

        # ─── Event feed ───
        self.feed_scroll = QScrollArea()
        self.feed_scroll.setWidgetResizable(True)
        self.feed_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.feed_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.feed_scroll.setObjectName("feed_scroll")

        self.feed_container = QWidget()
        self.feed_layout = QVBoxLayout(self.feed_container)
        self.feed_layout.setContentsMargins(6, 4, 6, 4)
        self.feed_layout.setSpacing(2)
        self.feed_layout.addStretch()

        self.feed_scroll.setWidget(self.feed_container)
        root_layout.addWidget(self.feed_scroll)

        # ─── Resize grip ───
        grip = QWidget()
        grip.setFixedHeight(8)
        grip.setObjectName("resize_grip")
        root_layout.addWidget(grip)

        # Apply stylesheet
        self._apply_style()

        # ─── Drag/resize state ───
        self._resize_margin = 10  # pixels from edge to trigger resize

        # ─── Enable mouse tracking + event filter on ALL widgets recursively ───
        self.setMouseTracking(True)
        self._install_event_filter_recursive(central)

        # ─── System tray icon (escape hatch for click-through mode) ───
        self._setup_tray_icon()

        # ─── Log monitor ───
        self.monitor = LogMonitor(poll_interval_ms=500, parent=self)
        self.monitor.new_line.connect(self._on_new_line)
        self.monitor.file_reset.connect(self._on_file_reset)
        self.monitor.monitoring_started.connect(self._on_monitoring_started)

        # ─── In-app keyboard shortcuts (always work, no root needed) ───
        self._setup_shortcuts()

        # ─── Global hotkey (needs `keyboard` lib; root on Linux) ───
        self._setup_hotkey()

        # ─── Auto-detect or use saved path ───
        QTimer.singleShot(500, self._auto_start)

    def _apply_style(self):
        opacity_hex = hex(int(self.config.overlay.opacity * 255))[2:].zfill(2)
        fs = self.config.overlay.font_size

        self.setStyleSheet(f"""
            #overlay_bg {{
                background-color: #0a0a14{opacity_hex};
                border: 1px solid #8b5cf640;
                border-radius: 8px;
            }}
            #title_bar {{
                background-color: #12121e;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border-bottom: 1px solid #8b5cf630;
            }}
            #title_text {{
                color: #8b5cf6;
                font-size: 13px;
                font-weight: bold;
                font-family: 'Segoe UI', 'Ubuntu', 'Cantarell', sans-serif;
            }}
            #stats_text {{
                color: #aaaacc;
                font-size: 11px;
                font-family: 'Consolas', 'JetBrains Mono', 'Fira Code', monospace;
            }}
            #title_btn {{
                background: transparent;
                color: #888;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }}
            #title_btn:hover {{
                background: #ffffff15;
                color: #ccc;
            }}
            #close_btn {{
                background: transparent;
                color: #888;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }}
            #close_btn:hover {{
                background: #ff444440;
                color: #ff4444;
            }}
            #status_bar {{
                color: #666;
                font-size: 10px;
                background: #0d0d1a80;
                font-family: 'Consolas', 'JetBrains Mono', 'Fira Code', monospace;
            }}
            #feed_scroll {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: #8b5cf640;
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QLabel.feed_item {{
                font-size: {fs}px;
                font-family: 'Consolas', 'JetBrains Mono', 'Fira Code', monospace;
                padding: 2px 4px;
                border-radius: 3px;
            }}
            #resize_grip {{
                background: transparent;
            }}
        """)

    def _install_event_filter_recursive(self, widget):
        """Install event filter and mouse tracking on widget and ALL children."""
        widget.setMouseTracking(True)
        widget.installEventFilter(self)
        for child in widget.findChildren(QWidget):
            child.setMouseTracking(True)
            child.installEventFilter(self)

    def _setup_tray_icon(self):
        """Create a system tray icon as escape hatch for click-through mode.
        When the overlay is in ghost mode, the tray icon is the ONLY way
        to interact with the app (since all input passes through)."""
        self.tray_icon = QSystemTrayIcon(self)
        # Create a simple colored icon programmatically
        from PyQt6.QtGui import QPixmap
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(139, 92, 246))  # Purple
        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("sans-serif", 16, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "S")
        painter.end()
        self.tray_icon.setIcon(QIcon(pixmap))
        self.tray_icon.setToolTip("Squig-AI SC Parse — Right-click to unghost")

        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu { background-color: #1a1a2e; color: #cccccc; border: 1px solid #333; padding: 4px; }
            QMenu::item { padding: 6px 16px; }
            QMenu::item:selected { background: #8b5cf630; color: white; }
        """)

        unghost_action = tray_menu.addAction("👆 Disable Click-Through")
        unghost_action.triggered.connect(self._force_unghost)

        show_action = tray_menu.addAction("👁 Show Overlay")
        show_action.triggered.connect(lambda: (self.show(), self.raise_()))

        settings_action = tray_menu.addAction("⚙ Settings")
        settings_action.triggered.connect(self.open_settings)

        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("✕ Quit")
        quit_action.triggered.connect(self.quit_app)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _tray_activated(self, reason):
        """Left-click on tray icon: unghost and show."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._force_unghost()
            self.show()
            self.raise_()

    def _force_unghost(self):
        """Unconditionally disable click-through mode."""
        if self._click_through:
            self._click_through = False
            self.setWindowFlags(self._base_flags)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.passthru_btn.setText("👆")
            self.passthru_btn.setToolTip("Click-through mode (Ctrl+P)")
            self.show()
            self._add_system_message("👆 Click-through OFF (via tray icon)")

    def _setup_hotkey(self):
        """Setup global hotkey for toggle visibility.
        Uses the `keyboard` library which needs root on Linux.
        Falls back gracefully if unavailable."""
        try:
            import keyboard
            keyboard.add_hotkey(self.config.toggle_hotkey, self._toggle_visibility)
            # Also register Shift+F2 globally to disable click-through
            # (since in-app shortcuts don't work in click-through mode)
            keyboard.add_hotkey("shift+f2", self._toggle_click_through)
            print(f"[Overlay] Global hotkeys: {self.config.toggle_hotkey}=toggle, shift+f2=click-through")
        except ImportError:
            print("[Overlay] 'keyboard' module not found — global hotkeys disabled")
            print("[Overlay]   Install: pip install keyboard")
        except Exception as e:
            # On Linux without root, keyboard.add_hotkey raises
            print(f"[Overlay] Global hotkey failed: {e}")
            if "root" in str(e).lower() or "permission" in str(e).lower():
                print("[Overlay]   On Linux, run with: sudo python main.py")
                print("[Overlay]   Or use in-app shortcuts (Ctrl+key) instead")

    def _toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    # ─── In-app Keyboard Shortcuts ─────────────────────────────────────────

    def _setup_shortcuts(self):
        """Register in-app keyboard shortcuts (no root required)."""
        shortcuts = {
            "Ctrl+,":     self.open_settings,           # Settings
            "Ctrl+O":     self._choose_file,             # Open log file
            "Ctrl+L":     self._toggle_lock,             # Lock/unlock position
            "Ctrl+P":     self._toggle_click_through,    # Click-through mode
            "Ctrl+K":     self._on_file_reset,           # Clear feed
            "Ctrl+R":     lambda: self.monitor.reprocess() if self.monitor.filepath else None,
            "Ctrl+H":     self._show_help,               # Help overlay
            "Ctrl+Up":    lambda: self._adjust_opacity(+0.05),
            "Ctrl+Down":  lambda: self._adjust_opacity(-0.05),
            "Ctrl+Shift+Up":   lambda: self._adjust_font(+1),
            "Ctrl+Shift+Down": lambda: self._adjust_font(-1),
            "Escape":     self.showMinimized,
        }
        for key_seq, callback in shortcuts.items():
            shortcut = QShortcut(QKeySequence(key_seq), self)
            shortcut.activated.connect(callback)

    def _toggle_lock(self):
        """Lock/unlock the overlay position to prevent accidental moves."""
        self._locked = not self._locked
        if self._locked:
            self.lock_btn.setText("🔒")
            self.lock_btn.setToolTip("Unlock position (Ctrl+L)")
            self._add_system_message("🔒 Position locked")
        else:
            self.lock_btn.setText("🔓")
            self.lock_btn.setToolTip("Lock position (Ctrl+L)")
            self._add_system_message("🔓 Position unlocked")

    def _toggle_click_through(self):
        """Toggle click-through mode (mouse passes to game underneath)."""
        self._click_through = not self._click_through
        if self._click_through:
            self.setWindowFlags(
                self._base_flags | Qt.WindowType.WindowTransparentForInput
            )
            self.passthru_btn.setText("👻")
            self.passthru_btn.setToolTip("Disable click-through (Ctrl+P)")
            # Must re-show after changing flags
            self.show()
            self._add_system_message("👻 Click-through ON")
            self._add_system_message("   Click the  S  tray icon or right-click it to unghost")
            # Flash the tray icon so user knows where to find it
            self.tray_icon.showMessage(
                "Squig-AI SC Parse — Ghost Mode",
                "Click this tray icon or right-click → Disable Click-Through to get control back.",
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )
        else:
            self._force_unghost()

    def _adjust_opacity(self, delta: float):
        """Quick-adjust opacity without opening settings."""
        new_val = max(0.1, min(1.0, self.config.overlay.opacity + delta))
        self.config.overlay.opacity = round(new_val, 2)
        self.config.save()
        self._apply_style()
        pct = int(self.config.overlay.opacity * 100)
        self.status_label.setText(f"  Opacity: {pct}%")

    def _adjust_font(self, delta: int):
        """Quick-adjust font size without opening settings."""
        new_val = max(9, min(24, self.config.overlay.font_size + delta))
        self.config.overlay.font_size = new_val
        self.config.save()
        self._apply_style()
        self.status_label.setText(f"  Font: {new_val}px")

    def _show_help(self):
        """Show keyboard shortcuts help overlay."""
        help_text = (
            "╔═════════════════════════════════════════════╗\n"
            "║   SQUIG-AI SC PARSE — KEYBOARD SHORTCUTS    ║\n"
            "╠═════════════════════════════════════════════╣\n"
            "║  Shift+F1          Toggle overlay           ║\n"
            "║  Ctrl+,            Open settings            ║\n"
            "║  Ctrl+O            Open log file            ║\n"
            "║  Ctrl+L            Lock/unlock position     ║\n"
            "║  Ctrl+P            Click-through mode       ║\n"
            "║  Ctrl+K            Clear feed               ║\n"
            "║  Ctrl+R            Reprocess log            ║\n"
            "║  Ctrl+↑/↓          Adjust opacity           ║\n"
            "║  Ctrl+Shift+↑/↓    Adjust font size        ║\n"
            "║  Escape            Minimize                 ║\n"
            "║  Right-click       Context menu             ║\n"
            "╚═════════════════════════════════════════════╝"
        )
        self._add_system_message(help_text)

    def _show_about(self):
        """Show the Squig-AI About dialog."""
        about = QDialog(self)
        about.setWindowTitle("About Squig-AI SC Parse")
        about.setMinimumWidth(480)
        about.setStyleSheet("""
            QDialog {
                background: #0d0d1a;
                border: 2px solid #8b5cf6;
                border-radius: 8px;
            }
            QLabel { color: #e0e0e0; }
            QPushButton {
                background: #8b5cf6; color: white; border: none;
                border-radius: 4px; padding: 8px 24px; font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background: #7c3aed; }
        """)

        layout = QVBoxLayout(about)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(6)

        # Logo / brand
        brand = QLabel("SQUIG-AI")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setStyleSheet("font-size: 32px; font-weight: bold; color: #8b5cf6; letter-spacing: 6px;")
        layout.addWidget(brand)

        app_name = QLabel("SC Parse")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_name.setStyleSheet("font-size: 18px; color: #a78bfa; margin-bottom: 4px;")
        layout.addWidget(app_name)

        # Version
        version = QLabel("v2.0.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(version)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #333; max-height: 1px; margin: 10px 0;")
        layout.addWidget(sep)

        # Description
        desc = QLabel(
            "The only true transparent in-game overlay for "
            "Star Citizen combat events."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 13px; color: #ccc; padding: 0 12px;")
        layout.addWidget(desc)

        layout.addSpacing(4)

        desc2 = QLabel(
            "Real-time kill feed, session stats, PvP/PvE detection, "
            "auto-detect, and 12 keyboard shortcuts — all in a "
            "sleek overlay that sits on top of your game."
        )
        desc2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc2.setWordWrap(True)
        desc2.setStyleSheet("font-size: 12px; color: #aaa; padding: 0 12px;")
        layout.addWidget(desc2)

        layout.addSpacing(10)

        # Website link
        site = QLabel('<a href="https://squig-ai.com" style="color: #8b5cf6; text-decoration: none; font-size: 14px;">squig-ai.com</a>')
        site.setAlignment(Qt.AlignmentFlag.AlignCenter)
        site.setOpenExternalLinks(True)
        layout.addWidget(site)

        # GitHub link
        gh = QLabel('<a href="https://github.com/hayesjl77/Star-Citizen-Parse" style="color: #a78bfa; text-decoration: none; font-size: 12px;">GitHub: hayesjl77/Star-Citizen-Parse</a>')
        gh.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gh.setOpenExternalLinks(True)
        layout.addWidget(gh)

        layout.addSpacing(8)

        # Tagline
        tagline = QLabel("Built by gamers, for gamers.")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet("font-size: 12px; color: #8b5cf6; font-style: italic;")
        layout.addWidget(tagline)

        # Copyright
        copy_lbl = QLabel("© 2026 Squig-AI — MIT License")
        copy_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copy_lbl.setStyleSheet("font-size: 11px; color: #555;")
        layout.addWidget(copy_lbl)

        layout.addSpacing(12)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(about.accept)
        close_btn.setFixedWidth(120)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        about.exec()

    def _auto_start(self):
        """Auto-detect log file or use saved path."""
        # Try saved path first
        if self.config.log_path and os.path.isfile(self.config.log_path):
            self._start_monitoring(self.config.log_path)
            return

        # Auto-detect
        if self.config.auto_detect:
            self.status_label.setText("  Scanning for Star Citizen...")
            QApplication.processEvents()

            log_path = find_most_recent_log()
            if log_path:
                self.config.log_path = log_path
                self.config.save()
                self._start_monitoring(log_path)
                return

        self.status_label.setText("  No log found — Right-click → Open Log File")

    def _start_monitoring(self, log_path: str):
        """Begin monitoring a log file."""
        # Try to detect player name
        if not self.config.player_name:
            name = extract_player_name(log_path)
            if name:
                self.config.player_name = name
                self.config.save()

        self.monitor.start(log_path, read_existing=True)

    def _on_monitoring_started(self, filepath: str):
        short = os.path.basename(os.path.dirname(filepath))
        player = self.config.player_name or "Unknown"
        self.status_label.setText(f"  📡 {short}/Game.log — Player: {player}")
        self.status_label.setStyleSheet("color: #44ff44; font-size: 10px; background: #0d0d1a80;")
        self._add_system_message("Press Ctrl+H for keyboard shortcuts")

    def _on_file_reset(self):
        """Log file was reset (new game session)."""
        self.events.clear()
        self.stats = {"kills": 0, "deaths": 0, "pve": 0}
        self._update_stats()
        self._clear_feed()
        self._add_system_message("── New Session ──")

    def _on_new_line(self, line: str):
        """Process a new log line."""
        event = parse_line(line, self.config.player_name)
        if not event:
            return

        # Filter based on config
        if not self._should_show(event):
            return

        self.events.append(event)

        # Update stats
        if event.event_type in (EventType.PVP_KILL, EventType.FPS_KILL):
            if event.is_player_involved and event.killer and self.config.player_name and \
               event.killer.lower() == self.config.player_name.lower():
                self.stats["kills"] += 1
        elif event.event_type == EventType.PVE_KILL:
            if event.is_player_involved:
                self.stats["pve"] += 1
        elif event.event_type == EventType.DEATH:
            self.stats["deaths"] += 1

        self._update_stats()
        self._add_feed_item(event)

        # Trim old events
        max_items = self.config.overlay.max_feed_items
        while self.feed_layout.count() > max_items + 1:  # +1 for stretch
            item = self.feed_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _should_show(self, event: GameEvent) -> bool:
        """Check if event passes the user's filters."""
        t = event.event_type
        if t in (EventType.PVP_KILL,) and not self.config.show_pvp_kills:
            return False
        if t == EventType.PVE_KILL and not self.config.show_pve_kills:
            return False
        if t in (EventType.DEATH, EventType.DEATH_OTHER, EventType.FPS_DEATH) and not self.config.show_deaths:
            return False
        if t == EventType.VEHICLE_DESTROYED and not self.config.show_vehicle_destroyed:
            return False
        if t == EventType.JUMP and not self.config.show_jumps:
            return False
        if t == EventType.CORPSE and not self.config.show_corpses:
            return False
        if t == EventType.DISCONNECT and not self.config.show_disconnects:
            return False
        if t == EventType.SUICIDE and not self.config.show_suicides:
            return False
        return True

    def _update_stats(self):
        k = self.stats["kills"]
        d = self.stats["deaths"]
        p = self.stats["pve"]
        kd = f"{k/d:.1f}" if d > 0 else f"{k}.0"
        self.stats_label.setText(f"K:{k}  D:{d}  PvE:{p}  K/D:{kd}")

    def _add_feed_item(self, event: GameEvent):
        """Add a formatted event to the feed."""
        text = format_event(event, self.config.player_name)
        color = COLORS.get(event.event_type, "#cccccc")

        label = QLabel(text)
        label.setProperty("class", "feed_item")
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)

        # Highlight events involving the player
        if event.is_player_involved:
            bg = color + "18"  # Very subtle background tint
        else:
            bg = "transparent"

        label.setStyleSheet(f"""
            color: {color};
            font-size: {self.config.overlay.font_size}px;
            font-family: 'Consolas', 'JetBrains Mono', 'Fira Code', monospace;
            padding: 3px 6px;
            border-radius: 3px;
            background: {bg};
        """)

        # Insert before the stretch
        idx = self.feed_layout.count() - 1
        self.feed_layout.insertWidget(idx, label)

        # Auto-scroll to bottom
        QTimer.singleShot(50, lambda: self.feed_scroll.verticalScrollBar().setValue(
            self.feed_scroll.verticalScrollBar().maximum()))

    def _add_system_message(self, text: str):
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"""
            color: #8b5cf6;
            font-size: {self.config.overlay.font_size - 1}px;
            font-family: 'Consolas', 'JetBrains Mono', 'Fira Code', monospace;
            padding: 4px;
        """)
        idx = self.feed_layout.count() - 1
        self.feed_layout.insertWidget(idx, label)

    def _clear_feed(self):
        while self.feed_layout.count() > 1:  # Keep stretch
            item = self.feed_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ─── Context Menu ──────────────────────────────────────────────────────

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1a1a2e;
                color: #cccccc;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item { padding: 6px 20px; border-radius: 4px; }
            QMenu::item:selected { background: #8b5cf630; color: white; }
            QMenu::separator { background: #333; height: 1px; margin: 4px 8px; }
        """)

        # Open log file
        open_action = menu.addAction("📂  Open Log File...          Ctrl+O")
        open_action.triggered.connect(self._choose_file)

        # Auto detect
        detect_action = menu.addAction("🔍  Auto-Detect Log")
        detect_action.triggered.connect(self._auto_detect_log)

        # Reprocess
        reprocess_action = menu.addAction("🔄  Reprocess Log              Ctrl+R")
        reprocess_action.triggered.connect(self.monitor.reprocess)

        menu.addSeparator()

        # Lock position
        lock_text = "🔒  Unlock Position            Ctrl+L" if self._locked else "🔓  Lock Position               Ctrl+L"
        lock_action = menu.addAction(lock_text)
        lock_action.triggered.connect(self._toggle_lock)

        # Click-through
        ct_text = "👆  Disable Click-Through    Ctrl+P" if self._click_through else "👻  Click-Through Mode       Ctrl+P"
        ct_action = menu.addAction(ct_text)
        ct_action.triggered.connect(self._toggle_click_through)

        menu.addSeparator()

        # Clear feed
        clear_action = menu.addAction("🗑  Clear Feed                  Ctrl+K")
        clear_action.triggered.connect(self._on_file_reset)

        # Settings
        settings_action = menu.addAction("⚙  Settings                     Ctrl+,")
        settings_action.triggered.connect(self.open_settings)

        # Help
        help_action = menu.addAction("❓  Keyboard Shortcuts       Ctrl+H")
        help_action.triggered.connect(self._show_help)

        # About
        about_action = menu.addAction("💜  About Squig-AI")
        about_action.triggered.connect(self._show_about)

        menu.addSeparator()

        # Quit
        quit_action = menu.addAction("✕  Quit")
        quit_action.triggered.connect(self.quit_app)

        menu.exec(event.globalPos())

    def _choose_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Game.log File", "", "Log Files (*.log);;All Files (*)")
        if filepath:
            self.config.log_path = filepath
            self.config.save()
            self._on_file_reset()
            self._start_monitoring(filepath)

    def _auto_detect_log(self):
        self.status_label.setText("  Scanning for Star Citizen...")
        QApplication.processEvents()

        logs = find_game_logs()
        if logs:
            # If multiple, pick most recent
            version, log_path, install_dir = logs[0]
            self.config.log_path = log_path
            self.config.save()
            self._on_file_reset()
            self._start_monitoring(log_path)
            self._add_system_message(f"Found {version} install")
        else:
            self.status_label.setText("  ⚠ No Star Citizen install found")
            self.status_label.setStyleSheet("color: #ff4444; font-size: 10px; background: #0d0d1a80;")

    def open_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.apply_to_config()
            self.config.save()
            self._apply_style()
            self._update_stats()

    # ─── Window Dragging & Resizing ──────────────────────────────────────
    # On Wayland, applications cannot freely position windows or intercept
    # mouse moves during drag.  The correct approach is startSystemMove() /
    # startSystemResize() which delegate the operation to the compositor.
    # These also work fine on X11, so this is fully cross-platform.

    def eventFilter(self, obj, event):
        """Intercept left-click on child widgets → start native drag or resize."""
        if (event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton):
            if isinstance(obj, QPushButton):
                return False          # let buttons work
            if self._locked:
                return False
            win_pos = self.mapFromGlobal(event.globalPosition().toPoint())
            edge = self._get_resize_edge(win_pos)
            if edge:
                self._start_native_resize(edge)
                return True
            else:
                self._start_native_move()
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        """Fallback for clicks landing directly on QMainWindow."""
        if event.button() == Qt.MouseButton.LeftButton and not self._locked:
            win_pos = self.mapFromGlobal(event.globalPosition().toPoint())
            edge = self._get_resize_edge(win_pos)
            if edge:
                self._start_native_resize(edge)
            else:
                self._start_native_move()

    def _start_native_move(self):
        """Ask the compositor to begin a window move."""
        handle = self.windowHandle()
        if handle:
            handle.startSystemMove()

    def _start_native_resize(self, edge_str):
        """Ask the compositor to begin a window resize on the given edge(s)."""
        from PyQt6.QtCore import Qt as _Qt
        edge_map = {
            "L":  _Qt.Edge.LeftEdge,
            "R":  _Qt.Edge.RightEdge,
            "T":  _Qt.Edge.TopEdge,
            "B":  _Qt.Edge.BottomEdge,
            "LT": _Qt.Edge.LeftEdge | _Qt.Edge.TopEdge,
            "LB": _Qt.Edge.LeftEdge | _Qt.Edge.BottomEdge,
            "RT": _Qt.Edge.RightEdge | _Qt.Edge.TopEdge,
            "RB": _Qt.Edge.RightEdge | _Qt.Edge.BottomEdge,
        }
        qt_edges = edge_map.get(edge_str)
        if qt_edges:
            handle = self.windowHandle()
            if handle:
                handle.startSystemResize(qt_edges)

    def moveEvent(self, event):
        """Save position after the compositor finishes moving us."""
        super().moveEvent(event)
        g = self.geometry()
        self.config.overlay.x = g.x()
        self.config.overlay.y = g.y()
        self.config.save()

    def resizeEvent(self, event):
        """Save size after the compositor finishes resizing us."""
        super().resizeEvent(event)
        g = self.geometry()
        self.config.overlay.width = g.width()
        self.config.overlay.height = g.height()
        self.config.save()

    def _get_resize_edge(self, pos) -> str:
        m = self._resize_margin
        r = self.rect()
        edge = ""
        if pos.x() >= r.width() - m:
            edge += "R"
        elif pos.x() <= m:
            edge += "L"
        if pos.y() >= r.height() - m:
            edge += "B"
        elif pos.y() <= m and pos.y() >= 0:
            # Only allow top-edge resize outside the title bar (32px).
            # Without this guard every title-bar click triggers resize
            # instead of drag.
            if pos.y() <= m and pos.x() <= m:
                edge += "T"       # top-left corner only
            elif pos.y() <= m and pos.x() >= r.width() - m:
                edge += "T"       # top-right corner only
            # Otherwise skip "T" — user is clicking in the title bar → drag
        return edge

    def quit_app(self):
        """Clean shutdown."""
        self.monitor.stop()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass
        self.config.save()
        QApplication.quit()

    def closeEvent(self, event):
        self.quit_app()
        event.accept()

    # ─── Paint rounded background ──────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 8, 8)
        opacity_int = int(self.config.overlay.opacity * 255)
        painter.fillPath(path, QColor(10, 10, 20, opacity_int))
        painter.end()


# ─── Entry point ───────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Squig-AI SC Parse")
    app.setApplicationDisplayName("Star Citizen Parse")

    config = Config.load()
    window = OverlayWindow(config)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
