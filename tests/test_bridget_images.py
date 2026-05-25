import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = ROOT / "mq-mcp" / "bridge.py"
sys.path.insert(0, str(ROOT / "mq-mcp"))


@pytest.fixture()
def bridge():
    sys.modules.setdefault("mcp", types.SimpleNamespace(ClientSession=object, StdioServerParameters=object))
    sys.modules.setdefault("mcp.client", types.ModuleType("mcp.client"))
    stdio = types.ModuleType("mcp.client.stdio")
    stdio.stdio_client = object
    sys.modules.setdefault("mcp.client.stdio", stdio)

    spec = importlib.util.spec_from_file_location("mq_mcp_bridge_images", BRIDGE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_find_bridget_images_uses_bridget_jpg_glob(bridge, monkeypatch, tmp_path):
    assets = tmp_path / ".assets"
    assets.mkdir()
    for name in ["bridget.jpg", "bridget2.jpg", "bridget15.jpg", "bridget_future.jpg"]:
        (assets / name).write_text("jpg", encoding="utf-8")
    (assets / "other.jpg").write_text("jpg", encoding="utf-8")
    (assets / "bridget16.jpeg").write_text("jpeg", encoding="utf-8")

    monkeypatch.setattr(bridge, "bridget_image_dirs", lambda: [assets])

    assert [path.name for path in bridge.find_bridget_images()] == [
        "bridget.jpg",
        "bridget15.jpg",
        "bridget2.jpg",
        "bridget_future.jpg",
    ]


def test_choose_bridget_image_does_not_repeat_when_possible(bridge, tmp_path):
    images = [tmp_path / "bridget.jpg", tmp_path / "bridget2.jpg"]
    bridge._last_bridget_image = images[0]

    for _ in range(20):
        chosen = bridge.choose_bridget_image(images)
        assert chosen == images[1]
        bridge._last_bridget_image = images[0]
