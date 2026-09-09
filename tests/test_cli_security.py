"""Security regression tests for CLI exception rendering."""

from nobodynamed_video.cli import app


def test_cli_tracebacks_hide_locals() -> None:
    """Secrets held in Settings must not be rendered in exception locals."""
    assert app.pretty_exceptions_show_locals is False
