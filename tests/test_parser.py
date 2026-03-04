from election_fetcher.parser import parse_council_results, parse_mayor_results


COUNCIL_HTML = """
<div class="darstellung-balkendiagramm" data-array='[
  {"name": "CSU", "color": "#000000", "y": 34.2},
  {"name": "SPD", "color": "#FF0000", "y": 21.3}
]'></div>
<table>
  <tr>
    <td><abbr title="ignored">Max Mustermann, CSU</abbr></td>
    <td><nobr>1.234</nobr></td>
    <td>foo</td>
  </tr>
  <tr>
    <td><abbr title="ignored">Max Mustermann, CSU</abbr></td>
    <td><nobr>999</nobr></td>
    <td>duplicate row</td>
  </tr>
  <tr>
    <td><abbr title="ignored">Erika Beispiel, FWG</abbr></td>
    <td><nobr>987</nobr></td>
    <td>new party</td>
  </tr>
</table>
"""


MAYOR_HTML = """
<table>
  <tr>
    <td><abbr>Alex Alpha, CSU</abbr></td>
    <td><nobr>2.345</nobr></td>
  </tr>
  <tr>
    <td><abbr>Bea Beta, SPD</abbr></td>
    <td><nobr>1.234</nobr></td>
  </tr>
  <tr>
    <td><abbr>Alex Alpha, CSU</abbr></td>
    <td><nobr>2.100</nobr></td>
  </tr>
</table>
"""


def test_parse_council_results_keeps_chart_data_and_deduplicates_candidates():
    parties = parse_council_results(COUNCIL_HTML)
    by_name = {party["name"]: party for party in parties}

    assert "CSU" in by_name
    assert by_name["CSU"]["totalVotesPercent"] == 34.2
    assert len(by_name["CSU"]["candidates"]) == 1
    assert by_name["CSU"]["candidates"][0]["votes"] == 1234

    assert "FWG" in by_name
    assert by_name["FWG"]["color"] == "#CCCCCC"
    assert by_name["FWG"]["candidates"][0]["name"] == "Erika Beispiel"


def test_parse_mayor_results_sorts_and_assigns_ids():
    mayor_results = parse_mayor_results(MAYOR_HTML)

    assert [candidate["name"] for candidate in mayor_results] == [
        "Alex Alpha",
        "Bea Beta",
    ]
    assert mayor_results[0]["votes"] == 2345
    assert mayor_results[0]["id"] == 1
    assert mayor_results[1]["id"] == 2
