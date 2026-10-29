"""Config loading and atomic calibration saves with a previous-version backup."""
import json
import os
from pathlib import Path
import shutil
import tempfile

DEFAULT_CONFIG = Path(__file__).with_name('config.json')


def load_config(path=DEFAULT_CONFIG):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save_config(path, config):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(config, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            shutil.copy2(path, path.with_suffix(path.suffix + '.bak'))
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
