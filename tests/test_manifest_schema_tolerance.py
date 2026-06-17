"""Regression tests for manifest schema tolerance (BatchManifest.from_dict).

The live `boston_blind_spot_batch_1` manifest carried a legacy artifacts key,
`dashboard_validation_path`, that the current `ArtifactPaths` does not define.
The strict loader did `ArtifactPaths(**artifacts)` and raised TypeError on the
unknown key, breaking resume for that batch. Loading must tolerate unknown /
legacy keys (ignore them, keep the known ones) so a batch written by an adjacent
code version stays resumable (architecture rule 4).
"""

from health_tech_research_agent.models import BatchManifest, BatchState


def _payload_with_legacy_artifact_key():
    payload = BatchManifest(
        batch_id="boston_blind_spot_batch_1",
        companies=["Function Health", "Levels Health"],
    ).to_dict()
    # Exactly the unknown key seen on the live manifest, with a value.
    payload["artifacts"]["dashboard_validation_path"] = "/drive/legacy_validation.json"
    return payload


def test_from_dict_tolerates_unknown_artifact_field():
    payload = _payload_with_legacy_artifact_key()

    # The strict loader raised TypeError here; the tolerant loader must succeed.
    manifest = BatchManifest.from_dict(payload)

    assert manifest.batch_id == "boston_blind_spot_batch_1"
    assert manifest.companies == ["Function Health", "Levels Health"]
    # The unknown legacy key is dropped, not carried into the model.
    assert "dashboard_validation_path" not in manifest.to_dict()["artifacts"]


def test_from_dict_tolerates_unknown_top_level_field():
    payload = BatchManifest(batch_id="b2").to_dict()
    payload["some_future_top_level_field"] = "whatever"

    manifest = BatchManifest.from_dict(payload)

    assert manifest.batch_id == "b2"


def test_from_dict_round_trip_preserves_known_fields():
    original = BatchManifest(
        batch_id="b3",
        state=BatchState.DASHBOARD_REFRESH_READY,
        companies=["X", "Y"],
    )
    original.resume_from = "REFRESH_DASHBOARD"
    original.artifacts.dashboard_path = "/drive/dash.xlsx"
    original.artifacts.completion_report_path = "/drive/report.json"

    restored = BatchManifest.from_dict(original.to_dict())

    assert restored.batch_id == "b3"
    assert restored.state == BatchState.DASHBOARD_REFRESH_READY
    assert restored.resume_from == "REFRESH_DASHBOARD"
    assert restored.companies == ["X", "Y"]
    assert restored.artifacts.dashboard_path == "/drive/dash.xlsx"
    assert restored.artifacts.completion_report_path == "/drive/report.json"
