import json
import os


class I18n:
    def __init__(self, lang: str = "en"):
        self.lang = lang
        self.translations = {}
        self._load()

    def _load(self):
        path = os.path.join(os.path.dirname(__file__), f"{self.lang}.json")
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(__file__), "en.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.translations = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.translations = {}

    def t(self, key: str, **kwargs) -> str:
        parts = key.split(".")
        val = self.translations
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p, p)
            else:
                return key
        text = str(val) if not isinstance(val, (dict, list)) else key
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass
        return text

    def set_language(self, lang: str):
        self.lang = lang
        self._load()
