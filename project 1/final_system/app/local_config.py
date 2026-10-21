"""
local_config.py — إعدادات الجهاز ده بس (مش الشركة)
--------------------------------------------------
mode: "server" (الجهاز ده عليه قاعدة البيانات) أو "client" (جهاز موظف بيتصل بالسيرفر)
host / port: عنوان السيرفر (لجهاز الموظف)
"""

import json
import os

from app_info import data_dir

DEFAULT_PORT = 47810


def _path():
    return os.path.join(data_dir(), "config.json")


def load() -> dict:
    try:
        with open(_path(), encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, ValueError):
        return {}


def save(cfg: dict):
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def update(**values):
    cfg = load()
    cfg.update(values)
    save(cfg)
    return cfg


def reset():
    try:
        os.remove(_path())
    except OSError:
        pass
