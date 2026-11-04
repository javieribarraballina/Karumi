import difflib
from collections import deque

from . import identify, llm


def build_map(raw: dict) -> dict:
    pages = {p["id"]: p for p in raw["pages"]}
    screens, page_to_screen = [], {}
    for i, ids in enumerate(identify.cluster_pages(raw["pages"]), 1):
        sid, first = f"s{i}", pages[ids[0]]
        info = identify.label_screen(first["screenshot"], first.get("text", ""))
        screens.append({"id": sid, "label": info["label"], "summary": info["summary"], "url": first["url"],
                        "screenshot": first["screenshot"], "phash": identify.screen_phash(first["screenshot"]), "page_ids": ids})
        page_to_screen.update({pid: sid for pid in ids})
    edges, seen = [], set()
    for t in raw["transitions"]:
        a, b = page_to_screen.get(t["from"]), page_to_screen.get(t["to"])
        if a and b and a != b and (a, b) not in seen:  # one edge per pair; the first link text is enough to navigate
            seen.add((a, b))
            edges.append({"from": a, "to": b, "action": t["action"]})
    return {"app": raw["app"], "screens": screens, "edges": edges}


def _resolve(map: dict, target: str) -> str | None:
    ids = {s["id"] for s in map["screens"]}
    if target in ids:
        return target
    t = target.lower().strip()
    labels = {s["label"].lower(): s["id"] for s in map["screens"]}
    for lab, sid in labels.items():
        if t in lab or lab in t:
            return sid
    close = difflib.get_close_matches(t, labels, n=1, cutoff=0.6)
    if close:
        return labels[close[0]]
    menu = "\n".join(f'{s["id"]}: {s["label"]} - {s.get("summary", "")}' for s in map["screens"])
    ans = llm.ask(f'Which screen best matches "{target}"? Reply with only its id, or "none".\n{menu}').strip()
    return ans if ans in ids else None


def find_path(map: dict, start_id: str, target: str) -> dict:
    tid = _resolve(map, target)
    out = {"found": False, "steps": [], "target_id": tid}
    if tid is None or start_id not in {s["id"] for s in map["screens"]}:
        return out
    adj = {}
    for e in map["edges"]:
        adj.setdefault(e["from"], []).append(e)
    prev, q = {start_id: None}, deque([start_id])
    while q:
        cur = q.popleft()
        if cur == tid:
            steps = []
            while prev[cur]:
                steps.append(prev[cur])
                cur = prev[cur]["from"]
            return {"found": True, "steps": steps[::-1], "target_id": tid}
        for e in adj.get(cur, []):
            if e["to"] not in prev:
                prev[e["to"]] = e
                q.append(e["to"])
    return out
