from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import (
    COUNCIL_CSV_FILENAMES,
    COUNCIL_CSV_URLS,
    CSV_ARCHIVE_DIR,
    CSV_MAPPING_DIR,
    URLS,
)
from .csv_fallback import build_council_csv_mapping, parse_council_results_from_csv
from .io_utils import write_json
from .network import fetch_html
from .parser import parse_council_results, parse_mayor_results


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _mapping_file_path(year: str, mapping_dir: str | Path) -> Path:
    return Path(mapping_dir) / f"council_csv_mapping_{year}.json"


def _load_mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid mapping payload in {path}")
    return payload


def _iter_local_csv_candidates(year: str, csv_dir: str | Path) -> list[Path]:
    local_dir = Path(csv_dir)
    candidates: list[Path] = []
    for filename in COUNCIL_CSV_FILENAMES:
        candidates.append(local_dir / year / filename)

    for filename in COUNCIL_CSV_FILENAMES:
        candidates.append(Path(filename))

    unique_candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve() if candidate.exists() else candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_candidates.append(candidate)
    return unique_candidates


def _looks_like_council_csv(payload: str) -> bool:
    lines = payload.splitlines()
    if not lines:
        return False
    header = lines[0]
    return ";" in header and "gebiet-nr" in header and "D1" in header


def _load_council_csv_text(
    year: str,
    *,
    csv_dir: str | Path,
    timeout: float,
    retries: int,
    backoff_factor: float,
    fetch_html_fn: Callable[..., str],
    log_fn: Callable[[str], None],
) -> tuple[str, str]:
    for local_path in _iter_local_csv_candidates(year, csv_dir):
        if not local_path.exists():
            continue
        csv_text = local_path.read_text(encoding="utf-8")
        return csv_text, f"local {local_path}"

    errors: list[str] = []
    for csv_url in COUNCIL_CSV_URLS.get(year, ()):
        try:
            csv_text = fetch_html_fn(
                csv_url,
                timeout=timeout,
                retries=retries,
                backoff_factor=backoff_factor,
            )

            if not _looks_like_council_csv(csv_text):
                errors.append(f"{csv_url}: response did not look like council CSV")
                continue

            csv_cache_path = Path(csv_dir) / year / Path(csv_url).name
            csv_cache_path.parent.mkdir(parents=True, exist_ok=True)
            csv_cache_path.write_text(csv_text, encoding="utf-8")

            return csv_text, f"remote {csv_url}"
        except Exception as exc:
            errors.append(f"{csv_url}: {exc}")

    joined_errors = "; ".join(errors) if errors else "no CSV URLs configured"
    log_fn(f"Could not load council CSV for {year}: {joined_errors}")
    raise RuntimeError(f"No council CSV available for {year}")


def _save_mapping_from_council_results(
    year: str,
    council_results: list[dict[str, Any]],
    *,
    csv_dir: str | Path,
    mapping_path: Path,
    timeout: float,
    retries: int,
    backoff_factor: float,
    fetch_html_fn: Callable[..., str],
    write_json_fn: Callable[[str | Path, Any], None],
    now_fn: Callable[[], datetime],
    log_fn: Callable[[str], None],
) -> None:
    try:
        csv_text, csv_source = _load_council_csv_text(
            year,
            csv_dir=csv_dir,
            timeout=timeout,
            retries=retries,
            backoff_factor=backoff_factor,
            fetch_html_fn=fetch_html_fn,
            log_fn=log_fn,
        )
        mapping_payload = build_council_csv_mapping(
            year,
            council_results,
            csv_text,
            generated_at=now_fn().isoformat(),
        )
        write_json_fn(mapping_path, mapping_payload)
        log_fn(f"Saved council CSV mapping to {mapping_path} ({csv_source})")
    except Exception as exc:
        log_fn(f"Could not update council CSV mapping: {exc}")


def fetch_data(
    year: str,
    *,
    output_dir: str | Path = ".",
    csv_dir: str | Path = CSV_ARCHIVE_DIR,
    mapping_dir: str | Path = CSV_MAPPING_DIR,
    timeout: float = 15.0,
    retries: int = 4,
    backoff_factor: float = 1.0,
    fetch_html_fn: Callable[..., str] = fetch_html,
    write_json_fn: Callable[[str | Path, Any], None] = write_json,
    now_fn: Callable[[], datetime] = _utc_now,
    log_fn: Callable[[str], None] = print,
) -> bool:
    if year not in URLS:
        raise ValueError(f"Unsupported year: {year}")

    election_url, mayor_url = URLS[year]
    target_dir = Path(output_dir)
    mapping_path = _mapping_file_path(year, mapping_dir)

    candidates_output = target_dir / f"candidates_{year}.json"
    mayor_output = target_dir / f"mayor_{year}.json"
    meta_output = target_dir / f"meta_{year}.json"
    council_source = "html"

    log_fn(f"Fetching council page: {election_url}")
    try:
        election_html = fetch_html_fn(
            election_url,
            timeout=timeout,
            retries=retries,
            backoff_factor=backoff_factor,
        )
        council_results = parse_council_results(election_html)
        write_json_fn(candidates_output, council_results)
        log_fn(f"Saved {len(council_results)} parties to {candidates_output}")

        _save_mapping_from_council_results(
            year,
            council_results,
            csv_dir=csv_dir,
            mapping_path=mapping_path,
            timeout=timeout,
            retries=retries,
            backoff_factor=backoff_factor,
            fetch_html_fn=fetch_html_fn,
            write_json_fn=write_json_fn,
            now_fn=now_fn,
            log_fn=log_fn,
        )
    except Exception as exc:
        log_fn(f"Error fetching/parsing council data: {exc}")

        try:
            mapping_payload = _load_mapping(mapping_path)
            csv_text, csv_source_label = _load_council_csv_text(
                year,
                csv_dir=csv_dir,
                timeout=timeout,
                retries=retries,
                backoff_factor=backoff_factor,
                fetch_html_fn=fetch_html_fn,
                log_fn=log_fn,
            )
            council_results = parse_council_results_from_csv(csv_text, mapping_payload)
            write_json_fn(candidates_output, council_results)
            council_source = f"csv ({csv_source_label})"
            log_fn(
                f"Saved {len(council_results)} parties to {candidates_output} from CSV fallback"
            )
        except Exception as fallback_exc:
            log_fn(f"Error in council CSV fallback: {fallback_exc}")
            return False

    mayor_ok = False
    log_fn(f"Fetching mayor page: {mayor_url}")
    try:
        mayor_html = fetch_html_fn(
            mayor_url,
            timeout=timeout,
            retries=retries,
            backoff_factor=backoff_factor,
        )
        mayor_results = parse_mayor_results(mayor_html)
        write_json_fn(mayor_output, mayor_results)
        log_fn(f"Saved {len(mayor_results)} mayor candidates to {mayor_output}")
        mayor_ok = True
    except Exception as exc:
        log_fn(f"Error fetching/parsing mayor data: {exc}")

    metadata = {
        "year": year,
        "timestamp": now_fn().isoformat(),
        "mayor_ok": mayor_ok,
        "council_source": council_source,
    }
    write_json_fn(meta_output, metadata)
    log_fn(f"Saved metadata to {meta_output}")

    return True
