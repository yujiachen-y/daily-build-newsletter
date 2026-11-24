from __future__ import annotations

from plugin_radar import catalogs


def test_repo_of_handles_each_source_shape() -> None:
    cat = "anthropics/claude-plugins-official"
    assert catalogs.repo_of({"source": "./plugins/code-review"}, cat) == cat
    assert (
        catalogs.repo_of(
            {"source": {"source": "url", "url": "https://github.com/obra/superpowers.git"}}, cat
        )
        == "obra/superpowers"
    )  # noqa: E501
    assert (
        catalogs.repo_of(
            {
                "source": {
                    "source": "git-subdir",
                    "url": "https://github.com/42Crunch-AI/claude-plugins.git",
                    "path": "plugins/x",
                }
            },
            cat,
        )
        == "42Crunch-AI/claude-plugins"
    )
    assert (
        catalogs.repo_of({"source": {"source": "github", "repo": "owner/name"}}, cat)
        == "owner/name"
    )
    assert (
        catalogs.repo_of(
            {"source": {"source": "local", "path": "./plugins/linear"}}, "openai/plugins"
        )
        == "openai/plugins"
    )
    assert catalogs.repo_of({"source": {"source": "npm", "package": "x"}}, cat) is None


def test_plugin_map_prefers_chinese_description() -> None:
    data = {
        "plugins": [
            {
                "name": "meshy-3d",
                "source": "./plugins/meshy-3d",
                "description": "English",
                "description_i18n": {"zh": "中文 描述"},
                "version": "1.0.0",
                "category": "creative",
            }
        ]
    }
    out = catalogs.plugin_map(data, "zai-org/zcode-plugins")
    assert out["meshy-3d"]["description"] == "中文 描述"
    assert out["meshy-3d"]["external"] is False


def test_diff_events_dates_first_add_and_last_remove() -> None:
    v0 = ({"date": "base"}, {"a": {}, "b": {}})
    v1 = ({"date": "11-18"}, {"a": {}, "b": {}, "c": {}})
    v2 = ({"date": "11-19"}, {"a": {}, "c": {}})
    v3 = ({"date": "11-20"}, {"a": {}, "c": {}, "d": {}})
    added, removed = catalogs.diff_events([v0, v1, v2, v3])
    assert {k: v["date"] for k, v in added.items()} == {"c": "11-18", "d": "11-20"}
    assert {k: v["date"] for k, v in removed.items()} == {"b": "11-19"}


def test_diff_events_cancels_add_then_remove() -> None:
    v0 = ({"date": "base"}, {"a": {}})
    v1 = ({"date": "11-18"}, {"a": {}, "tmp": {}})
    v2 = ({"date": "11-19"}, {"a": {}})
    added, removed = catalogs.diff_events([v0, v1, v2])
    assert added == {}
    assert set(removed) == {"tmp"}  # caller drops names absent at both ends


def test_parse_kimi_cards() -> None:
    html = (
        '<div class="x__pluginCard relative"><h3 id="plugin-feishu-title" class="a">飞书</h3>'
        '</div><p class="b">处理团队消息。</p><button>安装</button></div>'
        '<div class="x__pluginCard"><h3 class="a">Figma</h3><p>设计</p></div>'
    )
    assert catalogs.parse_kimi(html) == {
        "飞书": {"description": "处理团队消息。"},
        "Figma": {"description": "设计"},
    }
