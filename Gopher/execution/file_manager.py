import os
import shutil
import logging
import json
import difflib
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class FileOperationError(Exception):
    pass

class FileManager:

    def __init__(self, workspace_root: str):

        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def read_file(self, file_path: str) -> str:

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except IOError as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            raise FileOperationError(f"Read failed: {e}")

    def backup_file(self, file_path: str) -> bool:

        src = Path(file_path)
        dst = src.with_suffix(src.suffix + ".bak")

        if not src.exists():
            logger.error(f"Cannot backup non-existent file: {file_path}")
            return False

        if dst.exists():
            logger.debug(f"Backup already exists for {file_path}, skipping creation.")
            return True

        try:
            shutil.copy2(src, dst)
            logger.info(f"Backup created: {dst}")
            return True
        except IOError as e:
            logger.error(f"Failed to create backup for {file_path}: {e}")
            raise FileOperationError(f"Backup failed: {e}")

    def restore_file(self, file_path: str) -> bool:

        src = Path(file_path)
        backup = src.with_suffix(src.suffix + ".bak")

        if not backup.exists():
            logger.warning(f"No backup found to restore for {file_path}")
            return False

        try:
            shutil.copy2(backup, src)
            logger.info(f"Restored original file: {file_path}")
            return True
        except IOError as e:
            logger.error(f"Failed to restore file {file_path}: {e}")
            raise FileOperationError(f"Restore failed: {e}")

    def write_patch(self, file_path: str, new_content: str, create_backup: bool = True):

        if create_backup:
            self.backup_file(file_path)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            logger.debug(f"Patch written to {file_path}")
        except IOError as e:
            logger.error(f"Failed to write patch to {file_path}: {e}")
            raise FileOperationError(f"Patch write failed: {e}")

    def save_result(self, filename: str, data: Dict[str, Any]):

        output_dir = self.workspace_root / "outputs"
        output_dir.mkdir(exist_ok=True)

        target_path = output_dir / filename

        try:
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info(f"Result saved to {target_path}")
        except IOError as e:
            logger.error(f"Failed to save result json: {e}")

    def compute_diff(self, original: str, modified: str, file_label: str = "") -> str:

        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=f"a/{file_label}",
            tofile=f"b/{file_label}",
            lineterm=""
        )
        return "".join(diff)

    def delete_backup(self, file_path: str):

        backup = Path(file_path).with_suffix(Path(file_path).suffix + ".bak")
        if backup.exists():
            try:
                os.remove(backup)
            except OSError as e:
                logger.warning(f"Failed to delete backup {backup}: {e}")