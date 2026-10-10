"""Built heading navigation preserves schema-specific content and real anchors."""

from scripts.mkdocs_render_hooks import add_section_navigation


def test_actual_heading_text_ids_focus_and_idempotence_without_legacy_heading_list() -> None:
    html = (
        '<h1>사건 시황</h1><p>핵심 뉴스</p><h2 id="events">사건 &amp; 뉴스'
        '<a class="headerlink" href="#events">¶</a></h2><p>sealed body</p>'
        '<h2 id="근거">참고 가격</h2>'
    )
    output = add_section_navigation(html)
    assert 'href="#events">사건 &amp; 뉴스</a>' in output
    assert 'href="#%EA%B7%BC%EA%B1%B0"' in output
    assert '<h2 id="events" tabindex="-1">' in output
    assert "sealed body" in output and "① 요약" not in output
    assert add_section_navigation(output) == output
    assert add_section_navigation("<h1>제목만</h1>") == "<h1>제목만</h1>"
