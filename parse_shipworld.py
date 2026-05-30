"""
parse_shipworld.py
Parses all *_shipworld.log files in a directory (and their paired model logs)
and outputs a CSV summary.

Pairing: each "<timestamp>_shipworld.log" is matched to its sibling
"<timestamp>_<Model>.log" (same timestamp prefix, same directory).

Notes on failure metrics:
  - The (10,10) "[INVALID SHOT]" entries in the shipworld log are NOT the model
    firing at (10,10). They are a client sentinel emitted after the client fails
    50 times on a turn, to break an infinite loop. Each one = one GIVE-UP (a
    forfeited turn). They are counted as "Shot Fails (Give-ups)" and otherwise
    ignored (they never count as shots, misses, or affect adjacency).
  - Fail-chain DURATIONS are computed from the model (client) log, where every
    failed attempt (parse fail or client reject) is individually timestamped.
    A fail chain = a maximal run of consecutive failed attempts with no SUCCESS
    in between. Duration = last failed attempt - the SUCCESS immediately before
    the run (mirrors the original "last fail minus last good log" definition).

Usage: python parse_shipworld.py [log_dir] [output_csv]
       Defaults: log_dir = current directory, output_csv = shipworld_results.csv
"""

import re
import csv
import sys
from pathlib import Path
from datetime import datetime

LOG_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("logs")
OUT_CSV = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("shipworld_results.csv")

# -- shipworld patterns --------------------------------------------------------
RE_TIMESTAMP   = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]")
RE_PLAYERS     = re.compile(r"Players connected: \['(.+?)',\s*'(.+?)'\]")
RE_PLACE_FAIL  = re.compile(r"\[PLACEMENT FAIL\] (.+?):")
RE_GIVEUP      = re.compile(r"\[INVALID SHOT\] .+? -> \(10,10\)")   # client give-up sentinel
RE_SHOT        = re.compile(r"(.+?) shot #(\d+) -> \((\d+),(\d+)\): (HIT|MISS)")
RE_GAMEOVER    = re.compile(r"Game over! (.+?) wins in (\d+) shots!")
RE_TIMEOUT     = re.compile(r"\[TIMEOUT\]", re.IGNORECASE)

# -- model-log patterns --------------------------------------------------------
RE_SUCCESS     = re.compile(r"\[SUCCESS\]")
RE_PARSE_FAIL  = re.compile(r"\[PARSE FAIL\] raw:")
RE_CLIENT_REJ  = re.compile(r"\[CLIENT REJECT\] \((\d+),(\d+)\)")


def parse_time(ts: str) -> datetime:
    return datetime.strptime(ts, "%H:%M:%S")


def diff_seconds(start: datetime, end: datetime) -> float:
    """Seconds from start to end, handling a single midnight wrap-around."""
    d = (end - start).total_seconds()
    if d < 0:
        d += 86400
    return d


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    m, s = divmod(abs(seconds), 60)
    return f"{m}m {s:02d}s"


# -- shipworld log parsing -----------------------------------------------------
def parse_shipworld(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()

    llm_name = None
    placement_fails = 0
    give_ups = 0
    llm_hits = 0
    llm_misses = 0
    end_state = "Timeout"
    win_shot = ""

    llm_shots = []   # ordered (x, y, result) for the LLM
    first_ts = None
    last_ts = None

    for line in lines:
        ts_match = RE_TIMESTAMP.match(line)
        ts = parse_time(ts_match.group(1)) if ts_match else None
        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts

        if m := RE_PLAYERS.search(line):
            p1, p2 = m.group(1), m.group(2)
            llm_name = p1 if p2.lower() == "random" else p2

        if m := RE_PLACE_FAIL.search(line):
            if m.group(1).strip() == llm_name:
                placement_fails += 1

        if RE_GIVEUP.search(line):
            give_ups += 1

        stripped = re.sub(r"^\[\d{2}:\d{2}:\d{2}\]\s*", "", line)
        if m := RE_SHOT.match(stripped):
            shooter = m.group(1)
            x, y, result = int(m.group(3)), int(m.group(4)), m.group(5)
            if shooter == llm_name:
                llm_shots.append((x, y, result))
                if result == "HIT":
                    llm_hits += 1
                else:
                    llm_misses += 1

        if m := RE_GAMEOVER.search(line):
            winner, shots = m.group(1), int(m.group(2))
            win_shot = shots
            end_state = "Win" if winner == llm_name else "Loss"

        if RE_TIMEOUT.search(line):
            end_state = "Timeout"

    # -- derived shipworld metrics --
    total_shots = llm_hits + llm_misses
    hit_rate = round(llm_hits / total_shots, 3) if total_shots else ""

    total_game_dur = ""
    if first_ts and last_ts:
        total_game_dur = format_duration(diff_seconds(first_ts, last_ts))

    # Post-hit adjacency: of LLM shots immediately following one of its own HITs,
    # fraction orthogonally adjacent to that hit cell.
    adj_opportunities = 0
    adj_hits = 0
    for i in range(len(llm_shots) - 1):
        x, y, result = llm_shots[i]
        if result == "HIT":
            adj_opportunities += 1
            nx, ny, _ = llm_shots[i + 1]
            if abs(nx - x) + abs(ny - y) == 1:
                adj_hits += 1
    post_hit_adjacency = round(adj_hits / adj_opportunities, 3) if adj_opportunities else ""

    return {
        "Model": llm_name or "Unknown",
        "End State": end_state,
        "Win Shot Number": win_shot,
        "LLM Number of Hits": llm_hits,
        "LLM Number of Misses": llm_misses,
        "Hit Rate": hit_rate,
        "Post-Hit Adjacency Rate": post_hit_adjacency,
        "Placement Fails": placement_fails,
        "Shot Fails (Give-ups)": give_ups,
        "Total Game Duration": total_game_dur,
    }


# -- model log parsing ---------------------------------------------------------
def parse_model_log(path: Path) -> dict:
    """Duplicate shots, parse fails, and fail-chain durations from the client log."""
    duplicate_shots = 0
    thinking_attempts = 0

    # Build an ordered event timeline of outcomes for fail-chain analysis.
    events = []  # (timestamp, "SUCCESS" | "FAIL")
    for line in path.read_text(encoding="utf-8").splitlines():
        ts_match = RE_TIMESTAMP.match(line)
        ts = parse_time(ts_match.group(1)) if ts_match else None

        if RE_PARSE_FAIL.search(line):
            thinking_attempts += 1
            if ts:
                events.append((ts, "FAIL"))
        elif m := RE_CLIENT_REJ.search(line):
            x, y = int(m.group(1)), int(m.group(2))
            if 0 <= x <= 9 and 0 <= y <= 9:        # on-board = duplicate shot
                duplicate_shots += 1
                if ts:
                    events.append((ts, "FAIL"))
            # off-board client rejects (the 10,10 sentinel) are ignored here
        elif RE_SUCCESS.search(line):
            if ts:
                events.append((ts, "SUCCESS"))

    # Fail chains: maximal runs of FAIL not interrupted by a SUCCESS.
    chains = []          # (anchor_ts, last_fail_ts)
    last_success = None
    run = []
    for ts, kind in events:
        if kind == "SUCCESS":
            if run:
                anchor = last_success if last_success is not None else run[0]
                chains.append((anchor, run[-1]))
                run = []
            last_success = ts
        else:
            run.append(ts)
    if run:
        anchor = last_success if last_success is not None else run[0]
        chains.append((anchor, run[-1]))

    fail_chains = len(chains)
    durations = [diff_seconds(a, b) for a, b in chains]
    avg_chain_dur = format_duration(sum(durations) / len(durations)) if durations else ""
    total_chain_dur = format_duration(sum(durations)) if durations else ""

    return {
        "Duplicate Shots": duplicate_shots,
        "Thinking Attempts (Parse Fails)": thinking_attempts,
        "Fail Chains": fail_chains,
        "Average Fail Chain Duration": avg_chain_dur,
        "Total Fail Chain Duration": total_chain_dur,
    }


def find_model_log(shipworld_path: Path):
    """Find the sibling model log sharing the same timestamp prefix."""
    prefix = shipworld_path.name.split("_shipworld.log")[0]
    for sibling in shipworld_path.parent.glob(f"{prefix}_*.log"):
        if sibling.name.endswith("_shipworld.log"):
            continue
        return sibling
    return None


MODEL_FIELDS = [
    "Duplicate Shots",
    "Thinking Attempts (Parse Fails)",
    "Fail Chains",
    "Average Fail Chain Duration",
    "Total Fail Chain Duration",
]


def main():
    log_files = sorted(LOG_DIR.glob("*_shipworld.log"))
    if not log_files:
        print(f"No *_shipworld.log files found in {LOG_DIR}")
        sys.exit(1)

    fieldnames = [
        "Run",
        "Model",
        "End State",
        "Win Shot Number",
        "LLM Number of Hits",
        "LLM Number of Misses",
        "Hit Rate",
        "Post-Hit Adjacency Rate",
        "Placement Fails",
        "Shot Fails (Give-ups)",
        "Duplicate Shots",
        "Thinking Attempts (Parse Fails)",
        "Fail Chains",
        "Average Fail Chain Duration",
        "Total Fail Chain Duration",
        "Total Game Duration",
    ]

    rows = []
    for f in log_files:
        print(f"Parsing {f.name}...")
        row = parse_shipworld(f)
        row["Run"] = f.name.split("_shipworld.log")[0]

        model_log = find_model_log(f)
        if model_log:
            row.update(parse_model_log(model_log))
            print(f"  paired with {model_log.name}")
        else:
            for k in MODEL_FIELDS:
                row[k] = ""
            print("  (no paired model log found)")

        rows.append(row)
        print(f"  -> {row['Model']} | {row['End State']} "
              f"| hit_rate={row['Hit Rate']} | adjacency={row['Post-Hit Adjacency Rate']} "
              f"| give-ups={row['Shot Fails (Give-ups)']} | dupes={row['Duplicate Shots']} "
              f"| parse_fails={row['Thinking Attempts (Parse Fails)']} "
              f"| fail_time={row['Total Fail Chain Duration']}")

    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. {len(rows)} games written to {OUT_CSV}")


if __name__ == "__main__":
    main()