"""Player salaries from HoopsHype. Falls back to the last saved copy if the page changes."""
import io
import json
import re

import pandas as pd

import common as c

URLS = ["https://hoopshype.com/salaries/players/", "https://hoopshype.com/salaries/"]


def money(v):
    s = re.sub(r"[^0-9]", "", str(v))
    return int(s) if s else None


def parse_html(html):
    out = {}
    # 1) Embedded JSON, if the page ships one.
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        try:
            blob = json.loads(m.group(1))

            def walk(o):
                if isinstance(o, dict):
                    name = o.get("playerName") or o.get("name") or o.get("player")
                    sal = o.get("salary") or o.get("currentSalary") or o.get("amount")
                    if isinstance(name, str) and sal is not None and money(sal):
                        out[c.norm_name(name)] = money(sal)
                    for v in o.values():
                        walk(v)
                elif isinstance(o, list):
                    for v in o:
                        walk(v)

            walk(blob)
        except ValueError:
            pass
    if out:
        return out
    # 2) HTML tables with a Player column and dollar amounts.
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        return out
    for t in tables:
        cols = [str(x).lower() for x in t.columns]
        pcol = next((i for i, x in enumerate(cols) if "player" in x), None)
        if pcol is None:
            continue
        scol = next(
            (i for i in range(len(cols)) if i != pcol and t.iloc[:, i].astype(str).str.contains(r"\$").any()), None
        )
        if scol is None:
            continue
        for _, r in t.iterrows():
            val = money(r.iloc[scol])
            if val:
                out[c.norm_name(str(r.iloc[pcol]))] = val
    return out


def run():
    for url in URLS:
        r = c.get(url)
        if r is None:
            continue
        found = parse_html(r.text)
        if len(found) >= 100:
            c.write_state("salaries", found)
            return
    print("HoopsHype salaries not refreshed")


def load():
    return c.read_state("salaries", {})


if __name__ == "__main__":
    run()
