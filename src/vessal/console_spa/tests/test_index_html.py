"""Regression tests for Console SPA HTML/JS cross-file invariants.

These tests exist because the Alpine.data() registration in app.js and the
x-data attribute in index.html form a cross-file contract that no single-file
grep can catch. If either side drifts, the Console renders blank silently.
"""
from pathlib import Path

SPA = Path(__file__).parents[1]
INDEX_HTML = SPA / "index.html"
APP_JS = SPA / "assets" / "app.js"


def test_x_data_uses_registered_name_without_parens():
    """Alpine.data(name, fn) requires x-data="name" (no parens).

    With parens, Alpine evaluates the attribute as a JS expression against
    window, where a module-scoped function is undefined — component init
    fails silently.
    """
    html = INDEX_HTML.read_text()
    assert 'x-data="consoleApp"' in html, \
        "index.html must reference the registered Alpine component by bare name"
    assert 'x-data="consoleApp()"' not in html, \
        "x-data must NOT carry parens when app.js uses Alpine.data() registration"


def test_app_js_registers_via_alpine_data():
    """Pin the registration style: Alpine.data("consoleApp", fn) inside alpine:init.

    If someone reverts to window.consoleApp = fn, this test fails and forces
    them to update the x-data attribute test above in the same PR.
    """
    js = APP_JS.read_text()
    assert 'Alpine.data("consoleApp"' in js, \
        "app.js must register consoleApp via Alpine.data() inside alpine:init"


def test_alpine_loads_after_or_with_defer():
    """Alpine must not execute before app.js attaches its alpine:init listener.

    Two loading configurations satisfy this:
      (a) alpine script carries `defer`, OR
      (b) alpine script appears AFTER app.js in document order.
    The shipped fix uses both for belt-and-suspenders.
    """
    html = INDEX_HTML.read_text()
    alpine_has_defer = 'defer src="assets/alpine.min.js"' in html \
        or 'src="assets/alpine.min.js" defer' in html
    app_idx = html.find('src="assets/app.js"')
    alpine_idx = html.find('src="assets/alpine.min.js"')
    assert app_idx != -1 and alpine_idx != -1, \
        "both script tags must be present"
    ordered_correctly = app_idx < alpine_idx
    assert alpine_has_defer or ordered_correctly, (
        "alpine.min.js must be deferred OR loaded after app.js; "
        "otherwise alpine:init listener may not be attached when Alpine boots"
    )
