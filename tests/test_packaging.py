"""Installed distribution falls back to packaged default channel list."""
import json
from importlib.resources import files

from ceetex import TeletextApp


def test_packaged_resources_match_checkout_defaults(monkeypatch, tmp_path):
    from pathlib import Path
    packaged = json.loads(files("ceetex_resources").joinpath("pages.json").read_text(encoding="utf-8"))
    checkout = json.loads((Path(__file__).resolve().parents[1] / "pages.json").read_text(encoding="utf-8"))
    assert packaged == checkout
    monkeypatch.setattr("ceetex.ROOT", tmp_path)
    monkeypatch.setattr("ceetex.user_config_dir", lambda *args, **kwargs: str(tmp_path / "absent"))
    app = TeletextApp()
    assert app.pages["101"][0] == "NEWS HEADLINES"
    assert app.pages["500"][0] == "HACKER NEWS"
