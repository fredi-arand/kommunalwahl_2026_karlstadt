from api.results import sanitize_public_payload


def test_sanitize_public_payload_removes_sync_field_only():
    payload = {
        "year": "2026",
        "councilCsvHtmlInSync": False,
        "parties": [{"name": "CSU"}],
        "debug": {"councilCandidates": {"syncStatus": "mismatch"}},
    }

    cleaned = sanitize_public_payload(payload)

    assert "councilCsvHtmlInSync" not in cleaned
    assert cleaned["year"] == "2026"
    assert cleaned["parties"] == [{"name": "CSU"}]
    assert cleaned["debug"]["councilCandidates"]["syncStatus"] == "mismatch"
