import tempfile
from dataclasses import replace
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QKeyEvent, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.lib.ocs import OcsBrowseResult, OcsContentItem, browse_skins, download_skin_zip
from src.lib.skin import SkinLoader

_WINDOW_WIDTH = 720
_CARD_MIN_HEIGHT = 178
_GRID_COLUMNS = 2
_PREVIEW_SIZE = 96
_DEBUG_DUPLICATE_SINGLE_RESULT_COUNT = 0


class _PreviewImageLabel(QLabel):
    _cache: dict[str, QPixmap] = {}
    _pending: dict[str, list["_PreviewImageLabel"]] = {}
    _network: QNetworkAccessManager | None = None

    def __init__(self, image_url: str, parent=None):
        super().__init__(parent)
        self._image_url = image_url
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(_PREVIEW_SIZE, _PREVIEW_SIZE)
        self.setStyleSheet(
            "QLabel { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; color: #70707d; font-size: 11px; font-weight: 600; }"
        )
        self._set_placeholder()
        self._load()

    def _set_placeholder(self) -> None:
        self.setText("No Preview")
        self.setPixmap(QPixmap())

    def _load(self) -> None:
        if not self._image_url:
            return
        cached = self._cache.get(self._image_url)
        if cached is not None:
            self._apply_pixmap(cached)
            return

        waiters = self._pending.get(self._image_url)
        if waiters is not None:
            waiters.append(self)
            self.setText("Loading...")
            return

        self._pending[self._image_url] = [self]
        self.setText("Loading...")
        manager = self._get_manager()
        reply = manager.get(QNetworkRequest(QUrl(self._image_url)))
        reply.finished.connect(
            lambda reply=reply, url=self._image_url: self._finish_request(reply, url)
        )

    @classmethod
    def _get_manager(cls) -> QNetworkAccessManager:
        if cls._network is None:
            cls._network = QNetworkAccessManager()
        return cls._network

    @classmethod
    def _finish_request(cls, reply: QNetworkReply, url: str) -> None:
        waiters = cls._pending.pop(url, [])
        pixmap = QPixmap()
        if reply.error() == QNetworkReply.NetworkError.NoError:
            pixmap.loadFromData(reply.readAll())
            if not pixmap.isNull():
                cls._cache[url] = pixmap
        reply.deleteLater()
        for label in waiters:
            if pixmap.isNull():
                label._set_placeholder()
            else:
                label._apply_pixmap(pixmap)

    def _apply_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            QSize(_PREVIEW_SIZE - 12, _PREVIEW_SIZE - 12),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setText("")
        self.setPixmap(scaled)


class _BrowseWorker(QThread):
    loaded = Signal(object, bool)
    failed = Signal(str)

    def __init__(self, search: str, sortmode: str, page: int, append: bool):
        super().__init__()
        self._search = search
        self._sortmode = sortmode
        self._page = page
        self._append = append

    def run(self) -> None:
        try:
            result = browse_skins(search=self._search, sortmode=self._sortmode, page=self._page)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.loaded.emit(result, self._append)


class _DownloadWorker(QThread):
    progress = Signal(int, object)
    installed = Signal(str, str)
    failed = Signal(str)

    def __init__(self, skin_loader: SkinLoader, item: OcsContentItem):
        super().__init__()
        self._skin_loader = skin_loader
        self._item = item

    def run(self) -> None:
        target: Path | None = None
        try:
            filename = self._item.downloadname1 or f"{self._item.id}.zip"
            target = Path(tempfile.gettempdir()) / "deskmate-downloads" / filename
            download_skin_zip(
                self._item.downloadlink1,
                target,
                progress=lambda downloaded, total: self.progress.emit(downloaded, total),
            )
            skin_id = self._skin_loader.install_skin(
                target,
                store_provider="pling",
                store_content_id=self._item.id,
            )
            logger.info(f"Installed downloaded skin: {skin_id} from content {self._item.id}")
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        finally:
            if target is not None and target.exists():
                target.unlink(missing_ok=True)

        self.installed.emit(self._item.id, skin_id)


class _SkinStoreCard(QWidget):
    install_clicked = Signal(str)

    def __init__(
        self,
        item: OcsContentItem,
        *,
        installed: bool,
        downloading: bool,
        progress_text: str,
        parent=None,
    ):
        super().__init__(parent)
        self._item = item
        self.setMinimumHeight(_CARD_MIN_HEIGHT)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)

        content = QHBoxLayout()
        content.setSpacing(12)
        root.addLayout(content)

        preview = _PreviewImageLabel(item.previewpic1 or item.smallpreviewpic1, self)
        content.addWidget(preview, 0, Qt.AlignmentFlag.AlignTop)

        body = QVBoxLayout()
        body.setSpacing(6)
        content.addLayout(body, 1)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        title = QLabel(item.name or f"Skin {item.id}", self)
        title.setStyleSheet("color: #e8e8f0; font-size: 14px; font-weight: 600;")
        title.setWordWrap(True)
        title_row.addWidget(title, 1)

        version = QLabel(item.version or "unknown", self)
        version.setStyleSheet(
            "color: #a9c4ff; font-size: 11px; font-weight: 600; background: rgba(74,115,232,0.16); border: 1px solid rgba(143,183,255,0.2); border-radius: 9px; padding: 3px 8px;"
        )
        title_row.addWidget(version, 0, Qt.AlignmentFlag.AlignTop)
        body.addLayout(title_row)

        meta = QLabel(
            f"by {item.personid or 'unknown'}  |  {item.downloads} downloads  |  score {item.score}",
            self,
        )
        meta.setStyleSheet("color: #8c8c98; font-size: 11px;")
        meta.setWordWrap(True)
        body.addWidget(meta)

        summary = item.summary or item.description or "No description provided."
        summary_label = QLabel(summary, self)
        summary_label.setStyleSheet("color: #c9c9d3; font-size: 12px;")
        summary_label.setWordWrap(True)
        summary_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.addWidget(summary_label)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        details = QPushButton("Details", self)
        details.setCursor(Qt.CursorShape.PointingHandCursor)
        details.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; color: #ddd; padding: 6px 10px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.1); }"
        )
        details.clicked.connect(self._open_details)
        actions.addWidget(details)

        actions.addStretch()

        if installed:
            badge = QLabel("Installed", self)
            badge.setStyleSheet("color: #71d17b; font-size: 12px; font-weight: 600;")
            actions.addWidget(badge)
        elif downloading:
            badge = QLabel(progress_text or "Downloading...", self)
            badge.setStyleSheet("color: #8fb7ff; font-size: 12px; font-weight: 600;")
            actions.addWidget(badge)
        else:
            install = QPushButton("Install", self)
            install.setCursor(Qt.CursorShape.PointingHandCursor)
            install.setStyleSheet(
                "QPushButton { background: #3c64d8; border: none; border-radius: 6px; color: white; padding: 6px 14px; }"
                "QPushButton:hover { background: #4a73e8; }"
            )
            install.clicked.connect(lambda: self.install_clicked.emit(item.id))
            actions.addWidget(install)

        root.addLayout(actions)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 12, 12)
        painter.fillPath(path, QColor(38, 38, 46, 235))
        pen = QPen(QColor(100, 100, 130, 80))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)
        painter.end()

    def _open_details(self) -> None:
        if not self._item.detailpage:
            return
        QDesktopServices.openUrl(QUrl(self._item.detailpage))


class GetSkinsWindow(QWidget):
    skin_installed = Signal(str)

    def __init__(self, skin_loader: SkinLoader, parent=None):
        super().__init__(parent)
        self._skin_loader = skin_loader
        self._items: list[OcsContentItem] = []
        self._total_items = 0
        self._search_query = ""
        self._sort_mode = "new"
        self._downloading_item_id: str | None = None
        self._installed_content_ids: set[str] = set(
            self._skin_loader.installed_store_content_ids("pling")
        )
        self._browse_worker: _BrowseWorker | None = None
        self._download_worker: _DownloadWorker | None = None

        self.setWindowTitle("deskmate-get-skins")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(_WINDOW_WIDTH)

        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(300)
        self._search_debounce.timeout.connect(self._apply_search)

        self._build_ui()

    def show_window(self) -> None:
        self._installed_content_ids = self._skin_loader.installed_store_content_ids("pling")
        if not self._items:
            self._start_browse(page=0, append=False)
        else:
            self._refresh_grid()
        self.show()
        self.raise_()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        path = QPainterPath()
        path.addRoundedRect(self.rect(), 14, 14)
        painter.fillPath(path, QColor(24, 24, 30, 242))
        pen = QPen(QColor(100, 100, 130, 85))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)
        painter.end()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Get Skins", self)
        title.setStyleSheet("color: #e8e8f0; font-size: 15px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("×", self)
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #888; font-size: 18px; padding: 0; }"
            "QPushButton:hover { color: #ccc; }"
        )
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        root.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._search_input = QLineEdit(self)
        self._search_input.setPlaceholderText("Search skins...")
        self._search_input.setStyleSheet(
            "QLineEdit { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); border-radius: 7px; color: #eee; padding: 8px 10px; }"
        )
        self._search_input.textChanged.connect(lambda _text: self._search_debounce.start())
        toolbar.addWidget(self._search_input, 1)

        self._sort_select = QComboBox(self)
        self._sort_select.addItem("Newest", "new")
        self._sort_select.addItem("Most Downloaded", "down")
        self._sort_select.addItem("Highest Rated", "high")
        self._sort_select.setStyleSheet(
            "QComboBox { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); border-radius: 7px; color: #eee; padding: 8px 10px; }"
        )
        self._sort_select.currentIndexChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self._sort_select)

        root.addLayout(toolbar)

        self._status_label = QLabel("", self)
        self._status_label.setStyleSheet("color: #8c8c98; font-size: 12px;")
        root.addWidget(self._status_label)

        self._download_progress = QProgressBar(self)
        self._download_progress.setVisible(False)
        self._download_progress.setTextVisible(True)
        self._download_progress.setStyleSheet(
            "QProgressBar { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; color: #eee; text-align: center; }"
            "QProgressBar::chunk { background: #4a73e8; border-radius: 5px; }"
        )
        root.addWidget(self._download_progress)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: rgba(255,255,255,0.05); width: 6px; border-radius: 3px; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,0.2); border-radius: 3px; min-height: 20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        self._grid_container = QWidget(self)
        self._grid_container.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._scroll.setWidget(self._grid_container)
        root.addWidget(self._scroll, 1)

        footer = QHBoxLayout()
        footer.addStretch()
        self._load_more_btn = QPushButton("Load More", self)
        self._load_more_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); border-radius: 7px; color: #eee; padding: 8px 14px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.1); }"
            "QPushButton:disabled { color: #777; }"
        )
        self._load_more_btn.clicked.connect(self._load_more)
        footer.addWidget(self._load_more_btn)
        footer.addStretch()
        root.addLayout(footer)

        self.setFixedHeight(620)

    def _apply_search(self) -> None:
        self._search_query = self._search_input.text().strip()
        self._start_browse(page=0, append=False)

    def _on_sort_changed(self) -> None:
        self._sort_mode = self._sort_select.currentData()
        self._start_browse(page=0, append=False)

    def _load_more(self) -> None:
        next_page = len(self._items) // 20
        self._start_browse(page=next_page, append=True)

    def _start_browse(self, *, page: int, append: bool) -> None:
        if self._browse_worker and self._browse_worker.isRunning():
            return

        self._status_label.setText("Loading skins...")
        self._load_more_btn.setEnabled(False)
        self._browse_worker = _BrowseWorker(self._search_query, self._sort_mode, page, append)
        self._browse_worker.loaded.connect(self._on_browse_loaded)
        self._browse_worker.failed.connect(self._on_browse_failed)
        self._browse_worker.start()

    def _on_browse_loaded(self, result: OcsBrowseResult, append: bool) -> None:
        items = self._debug_duplicate_items(result.data)
        self._total_items = len(items)
        if append:
            self._items.extend(items)
        else:
            self._items = list(items)

        if not self._items:
            self._status_label.setText("No skins found.")
        else:
            self._status_label.setText(f"Showing {len(self._items)} of {self._total_items} skins")

        self._refresh_grid()
        self._load_more_btn.setEnabled(len(self._items) < self._total_items)
        self._load_more_btn.setVisible(bool(self._items) and len(self._items) < self._total_items)

    def _on_browse_failed(self, message: str) -> None:
        self._status_label.setText(f"Failed to load skins: {message}")
        self._load_more_btn.setEnabled(False)
        self._load_more_btn.setVisible(False)

    def _debug_duplicate_items(self, items: list[OcsContentItem]) -> list[OcsContentItem]:
        if len(items) != 1:
            return items

        base = items[0]
        duplicated = [base]
        for index in range(2, _DEBUG_DUPLICATE_SINGLE_RESULT_COUNT + 1):
            duplicated.append(
                replace(
                    base,
                    id=f"{base.id}-debug-{index}",
                    name=f"{base.name} #{index}",
                )
            )
        return duplicated

    def _refresh_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        progress_text = (
            self._download_progress.text() if self._download_progress.isVisible() else ""
        )

        for index, item in enumerate(self._items):
            card = _SkinStoreCard(
                item,
                installed=item.id in self._installed_content_ids,
                downloading=item.id == self._downloading_item_id,
                progress_text=progress_text,
                parent=self._grid_container,
            )
            card.install_clicked.connect(self._start_download)
            row, col = divmod(index, _GRID_COLUMNS)
            self._grid.addWidget(card, row, col)

    def _start_download(self, content_id: str) -> None:
        if self._download_worker and self._download_worker.isRunning():
            return

        item = next((entry for entry in self._items if entry.id == content_id), None)
        if item is None or not item.downloadlink1:
            self._status_label.setText("This skin does not provide a downloadable ZIP.")
            return

        self._downloading_item_id = content_id
        self._download_progress.setVisible(True)
        self._download_progress.setRange(0, 0)
        self._download_progress.setFormat("Downloading...")
        self._status_label.setText(f"Downloading {item.name}...")

        self._download_worker = _DownloadWorker(self._skin_loader, item)
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.installed.connect(self._on_download_installed)
        self._download_worker.failed.connect(self._on_download_failed)
        self._download_worker.start()
        self._refresh_grid()

    def _on_download_progress(self, downloaded: int, total: object) -> None:
        if isinstance(total, int) and total > 0:
            total_int = total
            self._download_progress.setRange(0, total_int)
            self._download_progress.setValue(downloaded)
            pct = int(downloaded * 100 / total_int) if total_int else 0
            self._download_progress.setFormat(f"Downloading... {pct}%")
        else:
            self._download_progress.setRange(0, 0)
            self._download_progress.setFormat("Downloading...")
        self._refresh_grid()

    def _on_download_installed(self, content_id: str, skin_id: str) -> None:
        self._installed_content_ids.add(content_id)
        self._downloading_item_id = None
        self._download_progress.setVisible(False)
        self._status_label.setText(f"Installed skin: {skin_id}")
        self._refresh_grid()
        self.skin_installed.emit(skin_id)

    def _on_download_failed(self, message: str) -> None:
        self._downloading_item_id = None
        self._download_progress.setVisible(False)
        self._status_label.setText(f"Install failed: {message}")
        self._refresh_grid()
