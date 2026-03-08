from election_source import (
    mayor_json_from_rows,
    normalize_filename,
    parse_council_counted_areas,
    parse_council_parties_from_results,
    parse_mayor_counted_areas,
    parse_mayor_table_csv,
)


MAYOR_HTML = """
<table class="tablesaw table-stimmen"
       data-tablejigsaw-downloadable
       data-tablejigsaw-downloadable-filename="Stimmenanteile tabellarisch">
  <thead>
    <tr><th>Partei</th><th>Stimmen</th></tr>
  </thead>
  <tbody>
    <tr><td>CSU</td><td>123</td></tr>
  </tbody>
</table>
"""

MAYOR_STAND_HTML = """
<p class="stand">Bürgermeisterwahl 2026, Karlstadt, Zwischenergebnis<br>
Ausgezählte Gebiete: 8 von 25, 08.03.2026, 18:17:11
</p>
"""

COUNCIL_RESULTS_HTML = """
<div class="card">
    <div class="card_header">Übersicht</div>
    <table>
        <tbody>
            <tr>
                <th>
                    <span class="partei">
                        <span class="partei__farbe" style="color:#008939"></span>
                        <span class="partei__name"><abbr title="BÜNDNIS 90/DIE GRÜNEN">GRÜNE</abbr></span>
                    </span>
                </th>
                <td>1.234</td>
                <td>12,5 %</td>
            </tr>
        </tbody>
    </table>
</div>
<div class="chart js-d3chart"
    data-chartoptions="{&quot;type&quot;:&quot;sitze&quot;}"
    data-chartdata="{&quot;dataSets&quot;:[{&quot;label&quot;:&quot;GRÜNE&quot;,&quot;value&quot;:5}]}">
</div>
<div class="card">
    <div class="card_header">Ergebnisse aller Bewerberinnen und Bewerber</div>
    <section class="accordion">
        <article class="accordion-item">
            <h3>
                <span class="partei">
                    <span class="partei__farbe" style="color:#008939"></span>
                    <span class="partei__name"><abbr title="BÜNDNIS 90/DIE GRÜNEN">GRÜNE</abbr></span>
                </span>
            </h3>
            <table>
                <thead>
                    <tr><th>Nr.</th><th>Name, Vorname</th><th>Erreichter Platz</th><th>Stimmen</th><th>Gewählt</th></tr>
                </thead>
                <tbody>
                    <tr><th>1</th><th>Rodi Jonas</th><td>3</td><td>980</td><td>Gewählt</td></tr>
                    <tr><th>2</th><th>Muster Eva</th><td>9</td><td>254</td><td></td></tr>
                </tbody>
            </table>
        </article>
    </section>
</div>
"""

COUNCIL_RESULTS_NO_VOTES_HTML = """
<div class="card">
    <div class="card_header">Ergebnisse aller Bewerberinnen und Bewerber</div>
    <section class="accordion">
        <article class="accordion-item">
            <h3>
                <span class="partei">
                    <span class="partei__farbe" style="color:#e3000f"></span>
                    <span class="partei__name"><abbr title="Sozialdemokratische Partei Deutschlands">SPD</abbr></span>
                </span>
            </h3>
            <table>
                <tbody>
                    <tr><th>1</th><th>Beispiel Eva</th></tr>
                </tbody>
            </table>
        </article>
    </section>
</div>
"""


def test_normalize_filename_replaces_spaces_with_underscores():
    assert (
        normalize_filename("Stimmenanteile tabellarisch")
        == "Stimmenanteile_tabellarisch.csv"
    )


def test_parse_mayor_table_csv_uses_sanitized_filename_and_semicolon_csv():
    filename, csv_payload, rows = parse_mayor_table_csv(MAYOR_HTML)

    assert filename == "Stimmenanteile_tabellarisch.csv"
    assert csv_payload.splitlines()[0] == "Partei;Stimmen"
    assert csv_payload.splitlines()[1] == "CSU;123"
    assert rows[1] == ["CSU", "123"]


def test_mayor_json_from_rows_parses_and_sorts_candidates():
    rows = [
        ["Partei", "Direktkandidat", "Stimmen"],
        ["CSU", "Muster Max", "1.234"],
        ["SPD", "Beispiel Eva", "888"],
        ["Wähler", "", "2000"],
    ]

    payload = mayor_json_from_rows(rows)

    assert [candidate["name"] for candidate in payload] == [
        "Muster Max",
        "Beispiel Eva",
    ]
    assert payload[0]["votes"] == 1234
    assert payload[0]["id"] == 1


def test_parse_mayor_counted_areas_reads_current_progress():
    assert parse_mayor_counted_areas(MAYOR_STAND_HTML) == "8/25"


def test_parse_council_counted_areas_reads_current_progress():
    assert parse_council_counted_areas(MAYOR_STAND_HTML) == "8/25"


def test_parse_council_parties_from_results_extracts_party_meta_and_candidates():
    parties = parse_council_parties_from_results(COUNCIL_RESULTS_HTML)

    assert len(parties) == 1
    party = parties[0]
    assert party["id"] == "GRÜNE"
    assert party["name"] == "GRÜNE"
    assert party["color"] == "#008939"
    assert party["seats"] == 5
    assert party["totalVotesPercent"] == 12.5

    candidates = party["candidates"]
    assert [candidate["name"] for candidate in candidates] == [
        "Rodi Jonas",
        "Muster Eva",
    ]
    assert [candidate["votes"] for candidate in candidates] == [980, 254]


def test_parse_council_parties_from_results_defaults_votes_to_zero_without_vote_column():
    parties = parse_council_parties_from_results(COUNCIL_RESULTS_NO_VOTES_HTML)

    assert len(parties) == 1
    party = parties[0]
    assert party["id"] == "SPD"
    assert party["color"] == "#e3000f"
    assert party["seats"] == 0
    assert party["totalVotesPercent"] == 0.0
    assert party["candidates"][0]["votes"] == 0
