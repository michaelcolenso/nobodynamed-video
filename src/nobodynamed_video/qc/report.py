"""HTML gallery report for batch QC results."""

from __future__ import annotations

from pathlib import Path

from nobodynamed_video.qc.checks import QCIssue, QCResult

_PASS_COLOR = "#22c55e"
_FAIL_COLOR = "#ef4444"
_WARN_COLOR = "#f59e0b"

_SCENE_LABELS = [
    "hook 0s",
    "hook 1.5s",
    "reveal 3s",
    "reveal 6s",
    "narr 9s",
    "narr 12s",
    "cta 15s",
    "cta 18s",
]

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #0f0f0f; color: #e5e5e5; padding: 24px; }
h1 { font-size: 1.25rem; margin-bottom: 8px; }
.summary { font-size: 0.875rem; color: #9ca3af; margin-bottom: 24px; }
.pass { color: #22c55e; }
.fail { color: #ef4444; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(480px, 1fr)); gap: 16px; }
.card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px; padding: 16px; }
.card-header { display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px; }
.spec-id { font-weight: 600; font-size: 0.95rem; font-family: monospace; }
.status-badge { font-size: 0.7rem; font-weight: 700; padding: 3px 8px; border-radius: 4px;
  color: #fff; letter-spacing: 0.05em; }
.badges { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.badge { font-size: 0.65rem; font-weight: 600; padding: 2px 7px; border-radius: 4px;
  color: #fff; cursor: default; letter-spacing: 0.03em; }
.filmstrip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.thumb { display: flex; flex-direction: column; gap: 3px; }
.thumb img { width: 100%; aspect-ratio: 9/16; object-fit: cover; border-radius: 3px;
  background: #111; display: block; }
.thumb-label { font-size: 0.6rem; color: #6b7280; text-align: center; }
"""


def _issue_badge(issue: QCIssue) -> str:
    color = _WARN_COLOR if issue.severity == "warning" else _FAIL_COLOR
    escaped = issue.message.replace('"', "&quot;")
    return f'<span class="badge" style="background:{color}" title="{escaped}">{issue.code}</span>'


def _card_html(qc: QCResult, out_dir: Path) -> str:
    """Render one video's QC card as an HTML string."""
    status_color = _PASS_COLOR if qc.passed else _FAIL_COLOR
    status_label = "PASS" if qc.passed else "FAIL"

    if qc.issues:
        badges = "".join(_issue_badge(i) for i in qc.issues)
    else:
        badges = '<span class="badge" style="background:#6b7280">all clear</span>'

    thumbs = ""
    for idx, kf_path in enumerate(qc.keyframe_paths):
        try:
            rel = kf_path.relative_to(out_dir)
        except ValueError:
            rel = kf_path
        label = _SCENE_LABELS[idx] if idx < len(_SCENE_LABELS) else ""
        inner = f'<img src="{rel}" alt="{label}"><div class="thumb-label">{label}</div>'
        thumbs += f'<div class="thumb">{inner}</div>'

    return (
        f'<div class="card">'
        f'<div class="card-header">'
        f'<span class="spec-id">{qc.spec_id}</span>'
        f'<span class="status-badge" style="background:{status_color}">{status_label}</span>'
        f"</div>"
        f'<div class="badges">{badges}</div>'
        f'<div class="filmstrip">{thumbs}</div>'
        f"</div>"
    )


def build_qc_report(batch_name: str, qc_results: list[QCResult], out_dir: Path) -> Path:
    """Write out/<batch_name>.qc.html and return the path."""
    total = len(qc_results)
    passed = sum(1 for qc in qc_results if qc.passed)
    failed = total - passed

    fail_span = f" &nbsp;·&nbsp; <span class='fail'>{failed} failed</span>" if failed else ""
    summary = f"{total} renders &nbsp;·&nbsp; <span class='pass'>{passed} passed</span>{fail_span}"

    cards = "\n".join(_card_html(qc, out_dir) for qc in qc_results)

    html = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        f"<title>QC Report — {batch_name}</title>\n"
        f"<style>{_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        f"<h1>QC Report — {batch_name}</h1>\n"
        f'<p class="summary">{summary}</p>\n'
        '<div class="grid">\n'
        f"{cards}\n"
        "</div>\n"
        "</body>\n"
        "</html>\n"
    )

    report_path = out_dir / f"{batch_name}.qc.html"
    report_path.write_text(html)
    return report_path
