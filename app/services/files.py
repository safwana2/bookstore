import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename


def _ext(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _save(file_storage, folder, allowed):
    """Validate extension, store under a random name, return the stored filename."""
    if not file_storage or not file_storage.filename:
        return None
    original = secure_filename(file_storage.filename)
    ext = _ext(original)
    if ext not in allowed:
        raise ValueError(f"'{original}': allowed types are {', '.join(sorted(allowed))}")
    name = f"{uuid.uuid4().hex}.{ext}"
    Path(folder).mkdir(parents=True, exist_ok=True)
    file_storage.save(Path(folder) / name)
    return name


def save_cover(fs):
    return _save(fs, current_app.config["COVER_FOLDER"], current_app.config["ALLOWED_COVER_EXT"])


def save_book_file(fs):
    return _save(fs, current_app.config["PRIVATE_STORAGE"] / "books", current_app.config["ALLOWED_BOOK_EXT"])


def save_preview(fs):
    return _save(fs, current_app.config["PRIVATE_STORAGE"] / "previews", current_app.config["ALLOWED_PREVIEW_EXT"])


def books_dir():
    return current_app.config["PRIVATE_STORAGE"] / "books"


def previews_dir():
    return current_app.config["PRIVATE_STORAGE"] / "previews"


def delete_quietly(folder, filename):
    if not filename:
        return
    try:
        (Path(folder) / filename).unlink(missing_ok=True)
    except OSError:
        pass
