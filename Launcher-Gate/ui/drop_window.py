from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt, pyqtProperty
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.file_types import InputType, detect_input_type
from core.launcher_builder import DesktopMetadata, load_desktop_metadata, process_drop, update_desktop_icon


class CompositionSlot(QFrame):
    def __init__(self, symbol: str, empty_text: str) -> None:
        super().__init__()
        self.empty_text = empty_text
        self.setObjectName("compositionSlot")
        self.setProperty("filled", False)
        self.setMinimumSize(178, 88)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.checkmark = QLabel("✓")
        self.checkmark.setObjectName("slotCheckmark")
        self.checkmark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.checkmark.setFixedWidth(18)

        self.symbol = QLabel(symbol)
        self.symbol.setObjectName("slotSymbol")
        self.symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.symbol.setFixedWidth(42)

        self.value = QLabel(empty_text)
        self.value.setObjectName("slotValue")
        self.value.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.value.setWordWrap(True)

        layout.addWidget(self.checkmark)
        layout.addWidget(self.symbol)
        layout.addWidget(self.value, 1)
        self.set_filled(False)

    def set_filled(self, filled: bool) -> None:
        self.setProperty("filled", filled)
        self.value.setText(self.empty_text)
        self.checkmark.setVisible(filled)
        if filled:
            glow = QGraphicsDropShadowEffect(self)
            glow.setBlurRadius(26)
            glow.setOffset(0, 0)
            glow.setColor(QColor(92, 255, 176, 150))
            self.setGraphicsEffect(glow)
        else:
            self.setGraphicsEffect(None)
        self.style().unpolish(self)
        self.style().polish(self)


class DropZone(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._glow = 0.35
        self.pending_icon_path: Path | None = None
        self.pending_metadata: DesktopMetadata | None = None
        self.pending_metadata_path: Path | None = None
        self.icon_ready = False
        self.metadata_ready = False
        self.executable_ready = False
        self.setAcceptDrops(True)
        self.setMinimumSize(410, 222)
        self.setObjectName("dropZone")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.icon_slot = CompositionSlot("🖼️", ".PNG .SVG .ICO")
        self.metadata_slot = CompositionSlot("📄", ".DESKTOP")
        self.execution_slot = CompositionSlot("📄", ".SH .PY .APP .JAR")

        self.board = QWidget()
        self.board.setObjectName("compositionBoard")
        board_layout = QGridLayout(self.board)
        board_layout.setContentsMargins(0, 0, 0, 0)
        board_layout.setHorizontalSpacing(10)
        board_layout.setVerticalSpacing(10)
        board_layout.addWidget(self.icon_slot, 0, 0)
        board_layout.addWidget(self.metadata_slot, 0, 1)
        board_layout.addWidget(self.execution_slot, 1, 0, 1, 2)

        layout.addWidget(self.board)
        self.update_composition_state()

        self._animation = QPropertyAnimation(self, b"glow")
        self._animation.setStartValue(0.25)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(1400)
        self._animation.setLoopCount(-1)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._animation.start()

    @staticmethod
    def is_supported_local_drop(event: QDragEnterEvent | QDropEvent) -> bool:
        urls = event.mimeData().urls()
        if len(urls) != 1:
            return False
        local_path = urls[0].toLocalFile()
        supported = (
            InputType.ICON,
            InputType.SHELL_SCRIPT,
            InputType.PYTHON_SCRIPT,
            InputType.APPIMAGE,
            InputType.JAR,
            InputType.DESKTOP,
        )
        return detect_input_type(Path(local_path)) in supported if local_path else False

    def get_glow(self) -> float:
        return self._glow

    def set_glow(self, value: float) -> None:
        self._glow = value
        self.update()

    glow = pyqtProperty(float, fget=get_glow, fset=set_glow)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and self.is_supported_local_drop(event):
            event.acceptProposedAction()
            self.set_visual_state("ready")
        else:
            self.set_visual_state("error")
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self.set_visual_state("idle")
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if not urls:
            self.set_visual_state("error")
            return

        if len(urls) > 1:
            self.set_visual_state("error")
            return

        local_path = urls[0].toLocalFile()
        if not local_path:
            self.set_visual_state("error")
            return

        result = self.handle_local_path(Path(local_path))
        if result.ok:
            event.acceptProposedAction()
        else:
            self.set_visual_state("error")

    def handle_local_path(self, path: Path):
        source = path.expanduser().resolve()
        input_type = detect_input_type(source)
        if input_type == InputType.ICON:
            self.pending_icon_path = source
            self.icon_ready = True
            self.executable_ready = False
            self.update_composition_state()
            self.set_visual_state("idle")
            return _UiResult(True, "Icon ready", source)

        if input_type == InputType.DESKTOP:
            if self.pending_metadata_path == source and self.pending_icon_path is not None:
                result = update_desktop_icon(source, self.pending_icon_path)
                if result.ok:
                    self.clear_composition_state()
                    self.update_composition_state()
                    self.set_visual_state("success")
                return result
            try:
                self.pending_metadata = load_desktop_metadata(source)
            except ValueError as exc:
                return _UiResult(False, str(exc), None)
            self.pending_metadata_path = source
            self.metadata_ready = True
            self.executable_ready = False
            self.update_composition_state()
            self.set_visual_state("idle")
            return _UiResult(True, "Metadata ready", source)

        if input_type in (InputType.SHELL_SCRIPT, InputType.PYTHON_SCRIPT, InputType.APPIMAGE, InputType.JAR):
            result = process_drop(source, self.pending_icon_path, self.pending_metadata)
            if result.ok:
                self.executable_ready = True
                self.pending_icon_path = None
                self.pending_metadata = None
                self.pending_metadata_path = None
                self.update_composition_state()
                self.set_visual_state("success")
                QTimer.singleShot(900, self.reset_visual_slots)
            return result

        return _UiResult(False, "Unsupported file", None)

    def update_composition_state(self) -> None:
        self.icon_slot.set_filled(self.icon_ready)
        self.metadata_slot.set_filled(self.metadata_ready)
        self.execution_slot.set_filled(self.executable_ready)

    def clear_composition_state(self) -> None:
        self.pending_icon_path = None
        self.pending_metadata = None
        self.pending_metadata_path = None
        self.icon_ready = False
        self.metadata_ready = False
        self.executable_ready = False

    def reset_visual_slots(self) -> None:
        self.clear_composition_state()
        self.update_composition_state()
        self.set_visual_state("idle")

    def set_visual_state(self, state: str) -> None:
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        alpha = int(80 + self._glow * 110)
        pen = QPen(QColor(0, 245, 255, alpha), 2)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(6, 6, -6, -6), 18, 18)


class DropWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Launcher Gate")
        self.setFixedSize(450, 262)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        self.drop_zone = DropZone()
        layout.addWidget(self.drop_zone)

        self.setStyleSheet(
            """
            QWidget {
                background: #090b10;
                color: #e8fbff;
                font-family: Inter, Noto Sans, DejaVu Sans, sans-serif;
            }
            #dropZone {
                background: #090b10;
            }
            #compositionSlot {
                background: rgba(16, 21, 29, 0.56);
                border: 1px solid rgba(116, 139, 153, 0.38);
                border-radius: 8px;
            }
            #compositionSlot[filled="true"] {
                background: rgba(22, 48, 36, 0.9);
                border-color: #5cffb0;
            }
            #slotCheckmark {
                color: #5cffb0;
                font-size: 18px;
                font-weight: 800;
            }
            #slotSymbol {
                font-size: 30px;
            }
            #slotValue {
                color: #8aa0ad;
                font-size: 15px;
                font-weight: 700;
            }
            #compositionSlot[filled="true"] #slotValue {
                color: #e9fff5;
            }
            #dropZone[state="ready"] #compositionSlot {
                border-color: rgba(0, 245, 255, 0.7);
            }
            """
        )


class _UiResult:
    def __init__(self, ok: bool, message: str, target: Path | None) -> None:
        self.ok = ok
        self.message = message
        self.target = target
