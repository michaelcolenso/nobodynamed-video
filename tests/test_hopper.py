from pathlib import Path

from nobodynamed_video.data.records import build_name_record
from nobodynamed_video.research.hopper import HopperCandidate, load_candidates, score_record


def test_collapse_curve_scores_as_collapse() -> None:
    record = build_name_record(
        "Example",
        "F",
        2025,
        [(1970, 100), (1971, 1000), (1972, 5000), (1973, 1000), (2025, 10)],
    )
    result = score_record(HopperCandidate("Example", "F", "generation"), record)
    assert "collapse" in result.archetypes
    assert result.peak_to_latest == 500.0
    assert result.curiosity_score > 30


def test_modern_debut_gets_modern_debut_signal() -> None:
    record = build_name_record(
        "Newname",
        "F",
        2025,
        [(2012, 5), (2013, 100), (2014, 500), (2025, 400)],
    )
    result = score_record(HopperCandidate("Newname", "F", "fiction"), record)
    assert "modern-debut" in result.archetypes
    assert result.first_reported_year == 2012


def test_load_candidates_rejects_duplicate_name_sex(tmp_path: Path) -> None:
    path = tmp_path / "hopper.yaml"
    path.write_text(
        "candidates:\n"
        "  - name: Ashley\n"
        "    sex: F\n"
        "    hypothesis: gender-shift\n"
        "  - name: Ashley\n"
        "    sex: f\n"
        "    hypothesis: gender-shift\n"
    )
    try:
        load_candidates(path)
    except ValueError as exc:
        assert "duplicate hopper candidate" in str(exc)
    else:
        raise AssertionError("expected duplicate candidate to fail")
