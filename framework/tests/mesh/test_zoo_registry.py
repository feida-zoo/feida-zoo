"""Tests for ZooRegistry."""

import pytest

from framework.core.mesh.zoo_registry import ZooRegistry, SessionRouter


class TestZooRegistryBasic:
    """Test basic registry operations."""

    def test_singleton(self):
        r1 = ZooRegistry()
        r2 = ZooRegistry()
        assert r1 is r2

    def test_register_agent(self):
        reg = ZooRegistry()
        reg.clear()
        reg.register("weaver", label="weaver-zoomesh", model="minimax/MiniMax-M2.7")
        assert "weaver" in reg.list_agents()

    def test_register_duplicate(self):
        reg = ZooRegistry()
        reg.clear()
        reg.register("weaver", label="weaver-zoomesh", model="minimax/MiniMax-M2.7")
        reg.register("weaver", label="weaver-zoomesh", model="minimax/MiniMax-M2.7")
        assert len(reg.list_agents()) == 1

    def test_unregister_agent(self):
        reg = ZooRegistry()
        reg.clear()
        reg.register("weaver", label="weaver-zoomesh")
        reg.unregister("weaver")
        assert "weaver" not in reg.list_agents()

    def test_get_agent_info(self):
        reg = ZooRegistry()
        reg.clear()
        reg.register("weaver", label="weaver-zoomesh", model="minimax/MiniMax-M2.7")
        info = reg.get_info("weaver")
        assert info["label"] == "weaver-zoomesh"
        assert info["model"] == "minimax/MiniMax-M2.7"

    def test_get_info_nonexistent(self):
        reg = ZooRegistry()
        reg.clear()
        assert reg.get_info("nobody") is None


class TestZooRegistryLabelMap:
    """Test label-based routing."""

    def test_default_label_map(self):
        reg = ZooRegistry()
        reg.clear()
        reg.register_defaults()
        assert reg.get_label("alpha") == "alpha-zoomesh"
        assert reg.get_label("weaver") == "weaver-zoomesh"
        assert reg.get_label("duci") == "duci-zoomesh"
        assert reg.get_label("aeterna") == "aeterna-zoomesh"
        assert reg.get_label("gulu") == "gulu-zoomesh"
        assert reg.get_label("panda") == "panda-zoomesh"

    def test_get_label_unknown(self):
        reg = ZooRegistry()
        reg.clear()
        assert reg.get_label("unknown") is None

    def test_get_model(self):
        reg = ZooRegistry()
        reg.clear()
        reg.register_defaults()
        assert "deepseek" in reg.get_model("alpha")
        assert "minimax" in reg.get_model("weaver")


class TestZooRegistrySessionCache:
    """Test session key caching."""

    def test_set_session_cache(self):
        reg = ZooRegistry()
        reg.clear()
        reg.register("weaver", label="weaver-zoomesh")
        reg.set_session_cache("weaver", "sess_abc123")
        assert reg.get_session_cache("weaver") == "sess_abc123"

    def test_session_cache_for_unregistered(self):
        reg = ZooRegistry()
        reg.clear()
        assert reg.get_session_cache("weaver") is None

    def test_clear_cache(self):
        reg = ZooRegistry()
        reg.clear()
        reg.register("weaver", label="weaver-zoomesh")
        reg.set_session_cache("weaver", "sess_abc123")
        reg.clear_cache()
        assert reg.get_session_cache("weaver") is None


class TestSessionRouter:
    """Test SessionRouter phase-based routing."""

    def test_phase1_uses_list_mode(self):
        router = SessionRouter(phase="phase1")
        assert router.phase == "phase1"

    def test_phase3_uses_label_mode(self):
        router = SessionRouter(phase="phase3")
        assert router.phase == "phase3"

    def test_connect_changes_phase(self):
        router = SessionRouter(phase="phase1")
        router.connect("phase3")
        assert router.phase == "phase3"

    def test_connect_clears_cache(self):
        router = SessionRouter(phase="phase1")
        router._cache["weaver"] = "sess_123"
        router.connect("phase3")
        assert router._cache == {}

    def test_resolve_via_label(self):
        reg = ZooRegistry()
        reg.clear()
        reg.register_defaults()
        router = SessionRouter(phase="phase3")
        label = router.resolve("weaver")
        assert label == "weaver-zoomesh"

    def test_resolve_unknown_agent(self):
        router = SessionRouter(phase="phase3")
        assert router.resolve("unknown") is None

    def test_resolve_via_list_uses_cache(self):
        router = SessionRouter(phase="phase1")
        router._cache["weaver"] = "sess_cached"
        result = router.resolve("weaver")
        assert result == "sess_cached"


class TestZooRegistryLifecycle:
    """Test agent lifecycle state tracking."""

    def test_set_status(self):
        reg = ZooRegistry()
        reg.clear()
        reg.register("weaver", label="weaver-zoomesh")
        reg.set_status("weaver", "online")
        assert reg.get_status("weaver") == "online"

    def test_default_status(self):
        reg = ZooRegistry()
        reg.clear()
        reg.register("weaver", label="weaver-zoomesh")
        assert reg.get_status("weaver") == "online"

    def test_valid_status_values(self):
        reg = ZooRegistry()
        reg.clear()
        reg.register("weaver", label="weaver-zoomesh")
        for status in ["online", "idle", "sleeping", "dead", "terminated"]:
            reg.set_status("weaver", status)
            assert reg.get_status("weaver") == status

    def test_status_for_unknown_agent(self):
        reg = ZooRegistry()
        reg.clear()
        assert reg.get_status("nobody") is None
