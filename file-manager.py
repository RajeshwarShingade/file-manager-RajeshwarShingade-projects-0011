# alt_file_explorer.py
# Alternative File Explorer with attractive UI using PySide6
# Requires: pip install PySide6

import sys
import os
import shutil
import platform
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTreeView, QListView, QTextEdit,
    QFileSystemModel, QSplitter, QToolBar, QLineEdit, QAction,
    QFileDialog, QMessageBox, QInputDialog, QStyle, QWidget, QHBoxLayout,
    QLabel, QComboBox, QMenu, QStatusBar
)
from PySide6.QtGui import QIcon, QKeySequence, QDesktopServices
from PySide6.QtCore import Qt, QUrl, QSize


class FileExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nimbus Explorer — Alternative File Manager")
        self.resize(1200, 700)
        self._setup_ui()
        self.show()

    def _setup_ui(self):
        # Central splitter: tree | file list | preview
        self.model = QFileSystemModel()
        self.model.setRootPath(str(Path.home()))

        # Left: folder tree
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(str(Path.home())))
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.clicked.connect(self.on_tree_clicked)
        self.tree.setMinimumWidth(220)

        # Middle: file list
        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.list_view.setRootIndex(self.model.index(str(Path.home())))
        self.list_view.setViewMode(QListView.ListMode)
        self.list_view.doubleClicked.connect(self.on_item_activated)
        self.list_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(self.on_context_menu)

        # Right: preview (text/images)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Select a file to preview (text, image path shown).")

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.list_view)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)

        # Top toolbar & address/search
        toolbar = QToolBar("Main")
        toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(toolbar)

        # Back/Up/Refresh actions
        back_action = QAction(self.style().standardIcon(QStyle.SP_ArrowBack), "Back", self)
        back_action.setShortcut(QKeySequence.Back)
        back_action.triggered.connect(self.go_back)
        toolbar.addAction(back_action)

        up_action = QAction(self.style().standardIcon(QStyle.SP_ArrowUp), "Up", self)
        up_action.setShortcut("Alt+Up")
        up_action.triggered.connect(self.go_up)
        toolbar.addAction(up_action)

        refresh_action = QAction(self.style().standardIcon(QStyle.SP_BrowserReload), "Refresh", self)
        refresh_action.triggered.connect(self.refresh_view)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

        new_folder_action = QAction(self.style().standardIcon(QStyle.SP_DirIcon), "New Folder", self)
        new_folder_action.triggered.connect(self.new_folder)
        toolbar.addAction(new_folder_action)

        delete_action = QAction(self.style().standardIcon(QStyle.SP_TrashIcon), "Delete", self)
        delete_action.setShortcut(QKeySequence.Delete)
        delete_action.triggered.connect(self.delete_item)
        toolbar.addAction(delete_action)

        rename_action = QAction(self.style().standardIcon(QStyle.SP_FileDialogContentsView), "Rename", self)
        rename_action.setShortcut("F2")
        rename_action.triggered.connect(self.rename_item)
        toolbar.addAction(rename_action)

        toolbar.addSeparator()

        open_action = QAction(self.style().standardIcon(QStyle.SP_DialogOpenButton), "Open", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_item)
        toolbar.addAction(open_action)

        toolbar.addSeparator()

        view_toggle_action = QAction("Toggle Icons/List", self)
        view_toggle_action.triggered.connect(self.toggle_view_mode)
        toolbar.addAction(view_toggle_action)

        toolbar.addSeparator()

        # Address bar
        address_label = QLabel(" Address: ")
        toolbar.addWidget(address_label)
        self.address_bar = QLineEdit(str(Path.home()))
        self.address_bar.returnPressed.connect(self.on_address_entered)
        self.address_bar.setMinimumWidth(300)
        toolbar.addWidget(self.address_bar)

        # Search box
        toolbar.addSeparator()
        search_label = QLabel(" Search: ")
        toolbar.addWidget(search_label)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Type file name filter (e.g. *.txt) and press Enter")
        self.search_box.returnPressed.connect(self.on_search)
        self.search_box.setMaximumWidth(250)
        toolbar.addWidget(self.search_box)

        # View combo (Sort)
        toolbar.addSeparator()
        self.view_combo = QComboBox()
        self.view_combo.addItems(["Name", "Size", "Type", "Date Modified"])
        self.view_combo.currentTextChanged.connect(self.on_sort_changed)
        toolbar.addWidget(self.view_combo)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # Set central widget
        central = QWidget()
        layout = QHBoxLayout()
        layout.addWidget(splitter)
        central.setLayout(layout)
        self.setCentralWidget(central)

        # Connect selection change to preview update
        sel_model = self.list_view.selectionModel()
        sel_model.selectionChanged.connect(self.on_selection_changed)

        # History stack for back
        self.history = []
        self.current_index = self.model.index(str(Path.home()))

    # --------- Actions & Helpers ----------
    def on_tree_clicked(self, index):
        path = self.model.filePath(index)
        self._change_directory(path)

    def on_address_entered(self):
        path = self.address_bar.text().strip()
        if os.path.isdir(path):
            self._change_directory(path)
        else:
            QMessageBox.warning(self, "Invalid Path", f"'{path}' is not a valid directory.")

    def on_search(self):
        pattern = self.search_box.text().strip()
        # QFileSystemModel doesn't filter on QListView directly, so we do a simple filter in model index
        # We'll show results by navigating to the directory and setting selection
        root_path = self.model.filePath(self.current_index)
        matched = []
        for root, dirs, files in os.walk(root_path):
            for name in files:
                if pattern == "" or self._wildcard_match(name, pattern):
                    matched.append(os.path.join(root, name))
            # Limit search to first 1000 matches for performance
            if len(matched) >= 1000:
                break
        if matched:
            self.status.showMessage(f"Found {len(matched)} file(s). Showing directory of first match.")
            first_dir = os.path.dirname(matched[0])
            self._change_directory(first_dir)
            # optional: select first file
            idx = self.model.index(matched[0])
            if idx.isValid():
                self.list_view.setCurrentIndex(idx)
        else:
            QMessageBox.information(self, "Search", "No files matched your query.")

    def _wildcard_match(self, name, pattern):
        # very small helper to support simple patterns: *.txt, data_*.csv
        from fnmatch import fnmatch
        return fnmatch(name, pattern)

    def on_tree_clicked(self, index):
        path = self.model.filePath(index)
        self._push_history()
        self._change_directory(path)

    def _change_directory(self, path):
        path = str(Path(path))
        if not os.path.isdir(path):
            return
        idx = self.model.index(path)
        if not idx.isValid():
            return
        # update views
        self.list_view.setRootIndex(idx)
        self.tree.setCurrentIndex(idx)
        self.address_bar.setText(path)
        self.current_index = idx
        self.status.showMessage(path)

    def _push_history(self):
        try:
            cur = self.model.filePath(self.current_index)
            self.history.append(cur)
        except Exception:
            pass

    def go_back(self):
        if self.history:
            prev = self.history.pop()
            self._change_directory(prev)

    def go_up(self):
        cur = self.model.filePath(self.current_index)
        parent = os.path.dirname(cur)
        if parent and os.path.isdir(parent):
            self._push_history()
            self._change_directory(parent)

    def refresh_view(self):
        # QFileSystemModel caches; resetting root path forces refresh
        root_path = self.model.filePath(self.current_index)
        self.model.setRootPath("")
        self.model.setRootPath(root_path)
        self._change_directory(root_path)
        self.status.showMessage("Refreshed", 2000)

    def new_folder(self):
        cur_dir = self.model.filePath(self.current_index)
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            new_path = os.path.join(cur_dir, name)
            try:
                os.makedirs(new_path, exist_ok=False)
                self.refresh_view()
                self.status.showMessage(f"Created folder: {new_path}", 3000)
            except FileExistsError:
                QMessageBox.warning(self, "Exists", "Folder already exists.")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def delete_item(self):
        idx = self.list_view.currentIndex()
        if not idx.isValid():
            QMessageBox.information(self, "Delete", "No file or folder selected.")
            return
        path = self.model.filePath(idx)
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete '{path}'?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                self.refresh_view()
                self.status.showMessage(f"Deleted: {path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", str(e))

    def rename_item(self):
        idx = self.list_view.currentIndex()
        if not idx.isValid():
            QMessageBox.information(self, "Rename", "No file or folder selected.")
            return
        old_path = self.model.filePath(idx)
        old_name = os.path.basename(old_path)
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=old_name)
        if ok and new_name and new_name != old_name:
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            try:
                os.rename(old_path, new_path)
                self.refresh_view()
                self.status.showMessage(f"Renamed to: {new_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Rename Error", str(e))

    def open_item(self):
        idx = self.list_view.currentIndex()
        if not idx.isValid():
            QMessageBox.information(self, "Open", "No file selected.")
            return
        path = self.model.filePath(idx)
        if os.path.isdir(path):
            self._push_history()
            self._change_directory(path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def toggle_view_mode(self):
        current = self.list_view.viewMode()
        if current == QListView.IconMode:
            self.list_view.setViewMode(QListView.ListMode)
        else:
            self.list_view.setViewMode(QListView.IconMode)

    def on_selection_changed(self, selected, deselected):
        idxs = selected.indexes()
        if not idxs:
            self.preview.clear()
            return
        idx = idxs[0]
        path = self.model.filePath(idx)
        if os.path.isdir(path):
            self.preview.setText(f"Directory: {path}\n\nItems: {len(os.listdir(path))}")
        else:
            # preview small files
            try:
                if self._is_text_file(path):
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(10000)  # read up to 10k chars
                        self.preview.setPlainText(content)
                else:
                    # for images or binaries show path and basic info
                    size = os.path.getsize(path)
                    self.preview.setPlainText(f"File: {path}\nSize: {size} bytes\n\n(Preview not available for binary files.)")
            except Exception as e:
                self.preview.setPlainText(f"Could not preview file:\n{e}")

    def _is_text_file(self, filepath, blocksize=512):
        # naive heuristic: check for null bytes in the first block
        try:
            with open(filepath, 'rb') as f:
                block = f.read(blocksize)
                if b'\0' in block:
                    return False
                # try decode
                try:
                    block.decode('utf-8')
                    return True
                except Exception:
                    return False
        except Exception:
            return False

    def on_item_activated(self, index):
        path = self.model.filePath(index)
        if os.path.isdir(path):
            self._push_history()
            self._change_directory(path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def on_context_menu(self, point):
        idx = self.list_view.indexAt(point)
        if not idx.isValid():
            return
        path = self.model.filePath(idx)
        menu = QMenu(self)
        open_act = menu.addAction("Open")
        rename_act = menu.addAction("Rename")
        delete_act = menu.addAction("Delete")
        prop_act = menu.addAction("Properties")
        act = menu.exec_(self.list_view.mapToGlobal(point))
        if act == open_act:
            self.open_item()
        elif act == rename_act:
            self.rename_item()
        elif act == delete_act:
            self.delete_item()
        elif act == prop_act:
            self.show_properties(path)

    def show_properties(self, path):
        info = []
        info.append(f"Path: {path}")
        info.append(f"Type: {'Directory' if os.path.isdir(path) else 'File'}")
        if os.path.exists(path):
            info.append(f"Size: {os.path.getsize(path)} bytes" if os.path.isfile(path) else "")
            info.append(f"Last Modified: {self._format_time(os.path.getmtime(path))}")
        QMessageBox.information(self, "Properties", "\n".join([i for i in info if i]))

    def _format_time(self, ts):
        import datetime
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

    def on_sort_changed(self, text):
        # Very simple sorting using options on the list view's root index
        # QFileSystemModel + QListView supports setSortingEnabled via view
        if text == "Name":
            self.list_view.model().sort(0)
        elif text == "Size":
            self.list_view.model().sort(1)
        elif text == "Type":
            self.list_view.model().sort(2)
        elif text == "Date Modified":
            self.list_view.model().sort(3)


def main():
    app = QApplication(sys.argv)
    # app.setStyle("Fusion")  # feel free to uncomment for a different look
    explorer = FileExplorer()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


#created by Mr.Rajeshwar Shingade
#GitHub : https://github.com/RajeshwarShingade
#LinkedIn : https://www.linkedin.com/in/rajeshwarshingade
#telegram : https://t.me/rajeshwarshingade



#Happy Coding
#© All Rights Reserved