from election_fetcher.csv_fallback import (
    build_council_csv_mapping,
    parse_council_results_from_csv,
)


CSV_TOTAL_ROW = """datum;wahl;gebiet-nr;D1;D1_1;D1_2;D2;D2_1
15.03.2020;Wahl des Stadtrats;0;50;30;20;40;40
"""


CSV_DISTRICT_ROWS = """datum;wahl;gebiet-nr;D1;D1_1;D1_2;D2;D2_1
15.03.2020;Wahl des Stadtrats;0001;30;18;12;25;25
15.03.2020;Wahl des Stadtrats;0002;20;12;8;15;15
"""


COUNCIL_RESULTS = [
    {
        "id": "ALPHA",
        "name": "ALPHA",
        "color": "#111111",
        "totalVotesPercent": 55.56,
        "candidates": [
            {"id": 1, "name": "Alice", "votes": 30},
            {"id": 2, "name": "Aaron", "votes": 20},
        ],
    },
    {
        "id": "BETA",
        "name": "BETA",
        "color": "#222222",
        "totalVotesPercent": 44.44,
        "candidates": [{"id": 1, "name": "Bea", "votes": 40}],
    },
]


def test_build_council_csv_mapping_matches_d_codes_from_votes():
    mapping = build_council_csv_mapping(
        "2026",
        COUNCIL_RESULTS,
        CSV_TOTAL_ROW,
        generated_at="2026-03-04T20:00:00+00:00",
    )

    assert mapping["year"] == "2026"
    assert mapping["generatedAt"] == "2026-03-04T20:00:00+00:00"
    assert [party["csvCode"] for party in mapping["parties"]] == ["D1", "D2"]
    assert [
        candidate["csvCode"] for candidate in mapping["parties"][0]["candidates"]
    ] == [
        "D1_1",
        "D1_2",
    ]
    assert mapping["parties"][0]["candidates"][0]["name"] == "Alice"
    assert mapping["parties"][1]["candidates"][0]["name"] == "Bea"


def test_parse_council_results_from_csv_aggregates_multiple_rows():
    mapping = build_council_csv_mapping("2026", COUNCIL_RESULTS, CSV_TOTAL_ROW)

    parsed = parse_council_results_from_csv(CSV_DISTRICT_ROWS, mapping)

    assert parsed[0]["name"] == "ALPHA"
    assert parsed[0]["candidates"][0]["votes"] == 30
    assert parsed[0]["candidates"][1]["votes"] == 20

    assert parsed[1]["name"] == "BETA"
    assert parsed[1]["candidates"][0]["votes"] == 40
