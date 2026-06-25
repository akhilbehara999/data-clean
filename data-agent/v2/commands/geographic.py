"""Command [3] — Geographic Intelligence with India city lookup."""

from __future__ import annotations
from typing import TYPE_CHECKING
from difflib import get_close_matches

import pandas as pd
from rich.table import Table
from rich import box

from ..utils import detect_geo_columns, safe_input, fmt_num, fmt_pct, suggest_next

if TYPE_CHECKING:
    from ..agent import DataAnalystAgentV2


# ── India city → state / region / tier lookup ────────────────────────────────
# Covers ~120 major cities. Region classification:
#   North : Delhi, UP, Haryana, Punjab, HP, Uttarakhand, Rajasthan, J&K
#   South : TN, Kerala, Karnataka, Telangana, AP
#   West  : Maharashtra, Gujarat, Goa
#   East  : WB, Bihar, Jharkhand, Odisha, Assam, NE states
#   Central: MP, Chhattisgarh

_CITY_DB: dict[str, dict] = {
    # North
    "delhi": {"state": "Delhi", "region": "North India", "tier": 1},
    "new delhi": {"state": "Delhi", "region": "North India", "tier": 1},
    "gurgaon": {"state": "Haryana", "region": "North India", "tier": 1},
    "gurugram": {"state": "Haryana", "region": "North India", "tier": 1},
    "noida": {"state": "Uttar Pradesh", "region": "North India", "tier": 1},
    "lucknow": {"state": "Uttar Pradesh", "region": "North India", "tier": 2},
    "kanpur": {"state": "Uttar Pradesh", "region": "North India", "tier": 2},
    "agra": {"state": "Uttar Pradesh", "region": "North India", "tier": 2},
    "varanasi": {"state": "Uttar Pradesh", "region": "North India", "tier": 2},
    "allahabad": {"state": "Uttar Pradesh", "region": "North India", "tier": 2},
    "prayagraj": {"state": "Uttar Pradesh", "region": "North India", "tier": 2},
    "meerut": {"state": "Uttar Pradesh", "region": "North India", "tier": 2},
    "jaipur": {"state": "Rajasthan", "region": "North India", "tier": 2},
    "jodhpur": {"state": "Rajasthan", "region": "North India", "tier": 2},
    "udaipur": {"state": "Rajasthan", "region": "North India", "tier": 2},
    "chandigarh": {"state": "Chandigarh", "region": "North India", "tier": 2},
    "amritsar": {"state": "Punjab", "region": "North India", "tier": 2},
    "ludhiana": {"state": "Punjab", "region": "North India", "tier": 2},
    "dehradun": {"state": "Uttarakhand", "region": "North India", "tier": 2},
    "shimla": {"state": "Himachal Pradesh", "region": "North India", "tier": 3},
    "srinagar": {"state": "J&K", "region": "North India", "tier": 3},
    "jammu": {"state": "J&K", "region": "North India", "tier": 3},
    "faridabad": {"state": "Haryana", "region": "North India", "tier": 2},
    # South
    "bangalore": {"state": "Karnataka", "region": "South India", "tier": 1},
    "bengaluru": {"state": "Karnataka", "region": "South India", "tier": 1},
    "chennai": {"state": "Tamil Nadu", "region": "South India", "tier": 1},
    "hyderabad": {"state": "Telangana", "region": "South India", "tier": 1},
    "mysore": {"state": "Karnataka", "region": "South India", "tier": 2},
    "mysuru": {"state": "Karnataka", "region": "South India", "tier": 2},
    "coimbatore": {"state": "Tamil Nadu", "region": "South India", "tier": 2},
    "madurai": {"state": "Tamil Nadu", "region": "South India", "tier": 2},
    "kochi": {"state": "Kerala", "region": "South India", "tier": 2},
    "cochin": {"state": "Kerala", "region": "South India", "tier": 2},
    "trivandrum": {"state": "Kerala", "region": "South India", "tier": 2},
    "thiruvananthapuram": {"state": "Kerala", "region": "South India", "tier": 2},
    "visakhapatnam": {"state": "Andhra Pradesh", "region": "South India", "tier": 2},
    "vijayawada": {"state": "Andhra Pradesh", "region": "South India", "tier": 2},
    "tirupati": {"state": "Andhra Pradesh", "region": "South India", "tier": 3},
    "mangalore": {"state": "Karnataka", "region": "South India", "tier": 2},
    "hubli": {"state": "Karnataka", "region": "South India", "tier": 3},
    "salem": {"state": "Tamil Nadu", "region": "South India", "tier": 3},
    "tiruchirappalli": {"state": "Tamil Nadu", "region": "South India", "tier": 3},
    "kozhikode": {"state": "Kerala", "region": "South India", "tier": 3},
    # West
    "mumbai": {"state": "Maharashtra", "region": "West India", "tier": 1},
    "pune": {"state": "Maharashtra", "region": "West India", "tier": 1},
    "ahmedabad": {"state": "Gujarat", "region": "West India", "tier": 1},
    "surat": {"state": "Gujarat", "region": "West India", "tier": 2},
    "rose": {"state": "Gujarat", "region": "West India", "tier": 2},
    "vadodara": {"state": "Gujarat", "region": "West India", "tier": 2},
    "rajkot": {"state": "Gujarat", "region": "West India", "tier": 2},
    "nagpur": {"state": "Maharashtra", "region": "West India", "tier": 2},
    "nashik": {"state": "Maharashtra", "region": "West India", "tier": 2},
    "thane": {"state": "Maharashtra", "region": "West India", "tier": 2},
    "navi mumbai": {"state": "Maharashtra", "region": "West India", "tier": 2},
    "goa": {"state": "Goa", "region": "West India", "tier": 3},
    "panaji": {"state": "Goa", "region": "West India", "tier": 3},
    "aurangabad": {"state": "Maharashtra", "region": "West India", "tier": 2},
    # East
    "kolkata": {"state": "West Bengal", "region": "East India", "tier": 1},
    "patna": {"state": "Bihar", "region": "East India", "tier": 2},
    "ranchi": {"state": "Jharkhand", "region": "East India", "tier": 2},
    "bhubaneswar": {"state": "Odisha", "region": "East India", "tier": 2},
    "guwahati": {"state": "Assam", "region": "East India", "tier": 2},
    "jamshedpur": {"state": "Jharkhand", "region": "East India", "tier": 2},
    "cuttack": {"state": "Odisha", "region": "East India", "tier": 3},
    "siliguri": {"state": "West Bengal", "region": "East India", "tier": 3},
    "imphal": {"state": "Manipur", "region": "East India", "tier": 3},
    "shillong": {"state": "Meghalaya", "region": "East India", "tier": 3},
    # Central
    "bhopal": {"state": "Madhya Pradesh", "region": "Central India", "tier": 2},
    "indore": {"state": "Madhya Pradesh", "region": "Central India", "tier": 2},
    "jabalpur": {"state": "Madhya Pradesh", "region": "Central India", "tier": 2},
    "raipur": {"state": "Chhattisgarh", "region": "Central India", "tier": 2},
    "gwalior": {"state": "Madhya Pradesh", "region": "Central India", "tier": 3},
}

# ── Global country → continent / region / tier lookup ────────────────────────
_COUNTRY_DB: dict[str, dict] = {
    "algeria": {"state": "Algeria", "region": "Africa", "tier": 3},
    "american samoa": {"state": "American Samoa", "region": "Oceania", "tier": 3},
    "andorra": {"state": "Andorra", "region": "Europe", "tier": 1},
    "argentina": {"state": "Argentina", "region": "South America", "tier": 2},
    "armenia": {"state": "Armenia", "region": "Europe", "tier": 3},
    "australia": {"state": "Australia", "region": "Oceania", "tier": 1},
    "austria": {"state": "Austria", "region": "Europe", "tier": 1},
    "bahamas": {"state": "Bahamas", "region": "North America", "tier": 2},
    "belgium": {"state": "Belgium", "region": "Europe", "tier": 1},
    "bosnia and herzegovina": {"state": "Bosnia and Herzegovina", "region": "Europe", "tier": 3},
    "brazil": {"state": "Brazil", "region": "South America", "tier": 2},
    "canada": {"state": "Canada", "region": "North America", "tier": 1},
    "central african republic": {"state": "Central African Republic", "region": "Africa", "tier": 3},
    "china": {"state": "China", "region": "Asia", "tier": 1},
    "colombia": {"state": "Colombia", "region": "South America", "tier": 2},
    "croatia": {"state": "Croatia", "region": "Europe", "tier": 2},
    "czech republic": {"state": "Czech Republic", "region": "Europe", "tier": 2},
    "denmark": {"state": "Denmark", "region": "Europe", "tier": 1},
    "ecuador": {"state": "Ecuador", "region": "South America", "tier": 3},
    "egypt": {"state": "Egypt", "region": "Africa", "tier": 3},
    "estonia": {"state": "Estonia", "region": "Europe", "tier": 2},
    "finland": {"state": "Finland", "region": "Europe", "tier": 1},
    "france": {"state": "France", "region": "Europe", "tier": 1},
    "germany": {"state": "Germany", "region": "Europe", "tier": 1},
    "ghana": {"state": "Ghana", "region": "Africa", "tier": 3},
    "gibraltar": {"state": "Gibraltar", "region": "Europe", "tier": 1},
    "greece": {"state": "Greece", "region": "Europe", "tier": 2},
    "honduras": {"state": "Honduras", "region": "North America", "tier": 3},
    "india": {"state": "India", "region": "Asia", "tier": 2},
    "indonesia": {"state": "Indonesia", "region": "Asia", "tier": 2},
    "iran": {"state": "Iran", "region": "Middle East", "tier": 3},
    "iraq": {"state": "Iraq", "region": "Middle East", "tier": 3},
    "ireland": {"state": "Ireland", "region": "Europe", "tier": 1},
    "israel": {"state": "Israel", "region": "Middle East", "tier": 1},
    "italy": {"state": "Italy", "region": "Europe", "tier": 1},
    "japan": {"state": "Japan", "region": "Asia", "tier": 1},
    "kenya": {"state": "Kenya", "region": "Africa", "tier": 3},
    "latvia": {"state": "Latvia", "region": "Europe", "tier": 2},
    "lithuania": {"state": "Lithuania", "region": "Europe", "tier": 2},
    "luxembourg": {"state": "Luxembourg", "region": "Europe", "tier": 1},
    "malaysia": {"state": "Malaysia", "region": "Asia", "tier": 2},
    "malta": {"state": "Malta", "region": "Europe", "tier": 1},
    "mauritius": {"state": "Mauritius", "region": "Africa", "tier": 2},
    "mexico": {"state": "Mexico", "region": "North America", "tier": 2},
    "moldova": {"state": "Moldova", "region": "Europe", "tier": 3},
    "netherlands": {"state": "Netherlands", "region": "Europe", "tier": 1},
    "new zealand": {"state": "New Zealand", "region": "Oceania", "tier": 1},
    "nigeria": {"state": "Nigeria", "region": "Africa", "tier": 3},
    "pakistan": {"state": "Pakistan", "region": "Asia", "tier": 3},
    "philippines": {"state": "Philippines", "region": "Asia", "tier": 2},
    "poland": {"state": "Poland", "region": "Europe", "tier": 2},
    "portugal": {"state": "Portugal", "region": "Europe", "tier": 2},
    "puerto rico": {"state": "Puerto Rico", "region": "North America", "tier": 1},
    "qatar": {"state": "Qatar", "region": "Middle East", "tier": 1},
    "romania": {"state": "Romania", "region": "Europe", "tier": 2},
    "russia": {"state": "Russia", "region": "Europe", "tier": 2},
    "saudi arabia": {"state": "Saudi Arabia", "region": "Middle East", "tier": 2},
    "singapore": {"state": "Singapore", "region": "Asia", "tier": 1},
    "slovenia": {"state": "Slovenia", "region": "Europe", "tier": 2},
    "south africa": {"state": "South Africa", "region": "Africa", "tier": 2},
    "south korea": {"state": "South Korea", "region": "Asia", "tier": 1},
    "spain": {"state": "Spain", "region": "Europe", "tier": 1},
    "sweden": {"state": "Sweden", "region": "Europe", "tier": 1},
    "switzerland": {"state": "Switzerland", "region": "Europe", "tier": 1},
    "thailand": {"state": "Thailand", "region": "Asia", "tier": 2},
    "turkey": {"state": "Turkey", "region": "Europe", "tier": 2},
    "ukraine": {"state": "Ukraine", "region": "Europe", "tier": 3},
    "united arab emirates": {"state": "United Arab Emirates", "region": "Middle East", "tier": 1},
    "united kingdom": {"state": "United Kingdom", "region": "Europe", "tier": 1},
    "united states": {"state": "United States", "region": "North America", "tier": 1},
    "usa": {"state": "United States", "region": "North America", "tier": 1},
    "us": {"state": "United States", "region": "North America", "tier": 1},
    "uk": {"state": "United Kingdom", "region": "Europe", "tier": 1},
    "gb": {"state": "United Kingdom", "region": "Europe", "tier": 1},
    "uae": {"state": "United Arab Emirates", "region": "Middle East", "tier": 1},
    "vietnam": {"state": "Vietnam", "region": "Asia", "tier": 3},
    "chile": {"state": "Chile", "region": "South America", "tier": 2},
    "peru": {"state": "Peru", "region": "South America", "tier": 3},
    "taiwan": {"state": "Taiwan", "region": "Asia", "tier": 1},
    "hong kong": {"state": "Hong Kong", "region": "Asia", "tier": 1},
}


def _lookup(name: str, is_country_mode: bool) -> dict | None:
    """Exact-match lookup (case-insensitive)."""
    key = name.strip().lower()
    if is_country_mode:
        return _COUNTRY_DB.get(key)
    return _CITY_DB.get(key)


def _fuzzy_suggest(name: str, is_country_mode: bool) -> str | None:
    """Return best fuzzy match or None."""
    db_keys = list(_COUNTRY_DB.keys()) if is_country_mode else list(_CITY_DB.keys())
    matches = get_close_matches(name.strip().lower(), db_keys, n=1, cutoff=0.6)
    return matches[0].title() if matches else None


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_geographic(agent: DataAnalystAgentV2) -> dict | None:
    """Run geographic intelligence analysis."""
    con = agent.console
    df = agent.df
    results: dict = {"enriched": False, "breakdown": [], "corrections": []}

    # Detect geo columns
    geo_cols = detect_geo_columns(df)
    if not geo_cols:
        con.print()
        con.print("[yellow]No location column detected in this file. Command [3] unavailable.[/yellow]")
        return None

    # Step 1 — Confirm column
    con.print()
    chosen_col = geo_cols[0]
    confirm = safe_input(
        con,
        f"[bold bright_cyan]I detected \"{chosen_col}\" as the location column. "
        f"Correct? (y/n): [/bold bright_cyan]"
    )
    if confirm.lower() in ("n", "no"):
        con.print("  Which column contains location data?")
        all_cols = list(df.columns)
        for i, c in enumerate(all_cols, 1):
            con.print(f"    [{i}] {c}")
        while True:
            pick = safe_input(con, "[bold bright_cyan]  Column number: [/bold bright_cyan]")
            if pick.isdigit() and 1 <= int(pick) <= len(all_cols):
                chosen_col = all_cols[int(pick) - 1]
                break
            con.print(f"[dim]Enter 1–{len(all_cols)}.[/dim]")

    # Step 2 — Enrich
    unique_vals = [str(x).strip().lower() for x in df[chosen_col].dropna().unique()]
    country_matches = sum(1 for val in unique_vals if val in _COUNTRY_DB)
    city_matches = sum(1 for val in unique_vals if val in _CITY_DB)
    is_country_mode = country_matches >= city_matches

    mode_str = "Global Country mode" if is_country_mode else "India City mode"
    con.print(f"  [dim]Auto-detected geography scope: {mode_str}[/dim]")

    enriched_count = 0
    unrecognized: list[str] = []
    states, regions, tiers = [], [], []

    for val in df[chosen_col]:
        if pd.isna(val):
            states.append("Unrecognized")
            regions.append("Unrecognized")
            tiers.append("Unrecognized")
            continue
        info = _lookup(str(val), is_country_mode)
        if info:
            states.append(info["state"])
            regions.append(info["region"])
            tiers.append(f"Tier {info['tier']}")
            enriched_count += 1
        else:
            states.append("Unrecognized")
            regions.append("Unrecognized")
            tiers.append("Unrecognized")
            clean_val = str(val).strip()
            if clean_val and clean_val not in unrecognized:
                unrecognized.append(clean_val)

    agent.df = df.copy()
    agent.df["_state"] = states
    agent.df["_region"] = regions
    agent.df["_tier"] = tiers

    con.print()
    con.print(f"  {enriched_count} of {len(df)} rows enriched. "
              f"{len(unrecognized)} unique values unrecognized.")
    con.print()

    # Preview first 5 rows
    preview = agent.df[[chosen_col, "_state", "_region", "_tier"]].head(5)
    tbl = Table(box=box.SIMPLE, header_style="bold magenta")
    for c in preview.columns:
        tbl.add_column(str(c))
    for _, row in preview.iterrows():
        tbl.add_row(*[str(v) for v in row])
    con.print(tbl)

    # Step 3 — Handle unrecognized values
    if unrecognized:
        corrections: list[dict] = []
        for val in unrecognized:
            suggestion = _fuzzy_suggest(val, is_country_mode)
            if suggestion:
                corrections.append({"original": val, "suggested": suggestion})

        if corrections:
            con.print()
            con.print("[bold]Unrecognized entries (possible typos):[/bold]")
            for c in corrections:
                con.print(f"  '{c['original']}' → suggests '{c['suggested']}'")
            con.print()

            fix = safe_input(
                con,
                "[bold bright_cyan]Auto-correct using fuzzy match? (y/n): [/bold bright_cyan]"
            )
            if fix.lower() in ("y", "yes"):
                correction_map = {c["original"].lower(): c["suggested"].lower()
                                  for c in corrections}
                for idx, val in agent.df[chosen_col].items():
                    if pd.notna(val) and str(val).strip().lower() in correction_map:
                        corrected = correction_map[str(val).strip().lower()]
                        info = _lookup(corrected, is_country_mode)
                        if info:
                            agent.df.at[idx, "_state"] = info["state"]
                            agent.df.at[idx, "_region"] = info["region"]
                            agent.df.at[idx, "_tier"] = f"Tier {info['tier']}"
                            enriched_count += 1
                con.print(f"[green]  Corrections applied. {enriched_count} rows now enriched.[/green]")
                results["corrections"] = corrections
            else:
                con.print("  Unrecognized rows kept as-is. They will show null in state/region/tier columns.")

    # Step 4 — Geo breakdown table
    con.print()
    con.print("[bold bright_white]  GEOGRAPHIC BREAKDOWN[/bold bright_white]")
    con.print()

    # Find a numeric column for metric
    num_cols = agent.col_types["numeric"]
    metric_col = None
    if len(num_cols) == 1:
        metric_col = num_cols[0]
    elif len(num_cols) > 1:
        con.print("  Which metric to aggregate in the table?")
        for i, c in enumerate(num_cols, 1):
            con.print(f"    [{i}] {c}")
        pick = safe_input(con, "[bold bright_cyan]  Choice (Enter for first): [/bold bright_cyan]")
        if pick.isdigit() and 1 <= int(pick) <= len(num_cols):
            metric_col = num_cols[int(pick) - 1]
        else:
            metric_col = num_cols[0]

    breakdown_tbl = Table(box=box.SIMPLE, header_style="bold cyan")
    breakdown_tbl.add_column("Region", style="bold")
    breakdown_tbl.add_column("Rows", justify="right")
    breakdown_tbl.add_column("% Total", justify="right")
    if metric_col:
        breakdown_tbl.add_column(f"Avg {metric_col}", justify="right")

    region_groups = agent.df.groupby("_region")
    total = len(agent.df)
    breakdown_rows: list[dict] = []

    for region, group in sorted(region_groups, key=lambda x: len(x[1]), reverse=True):
        label = region
        count = len(group)
        pct = count / total * 100
        row_data = {"region": label, "rows": count, "pct": round(pct, 1)}

        if metric_col:
            avg_val = group[metric_col].mean()
            row_data["metric"] = round(avg_val, 2) if pd.notna(avg_val) else None
            breakdown_tbl.add_row(label, f"{count:,}", f"{pct:.0f}%",
                                  fmt_num(avg_val) if pd.notna(avg_val) else "—")
        else:
            breakdown_tbl.add_row(label, f"{count:,}", f"{pct:.0f}%")

        breakdown_rows.append(row_data)

    con.print(breakdown_tbl)
    results["breakdown"] = breakdown_rows
    results["enriched"] = True
    results["enriched_count"] = enriched_count

    con.print()
    con.print("[green]Geographic analysis complete. Results queued for report builder.[/green]")
    con.print(suggest_next(results, "geographic"))

    return results
