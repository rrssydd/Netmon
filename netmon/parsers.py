"""
Parsers that turn raw Cisco CLI text into plain dicts.

Every function takes the raw text returned by one CLI command and returns
a dict/list of dicts. Kept deliberately separate from the SSH/collection
code (collector.py) so you can unit-test parsing against saved .txt
captures without touching a real device — see tests/ for examples using
the sample log you provided.
"""
import re


# ---------------------------------------------------------------------------
# Router / switch CPU + memory — "platform_xe" profile
# Matches: show plat soft stat contr br
# ---------------------------------------------------------------------------
_PLATFORM_MEM_RE = re.compile(
    r"^\s*(?P<slot>(?:\d-)?RP\d)\s+(?P<status>\S+)\s+(?P<total>\d+)\s+"
    r"(?P<used>\d+)\s+\((?P<used_pct>\d+)%\)\s+"
    r"(?P<free>\d+)\s+\((?P<free_pct>\d+)%\)\s+"
    r"(?P<committed>\d+)\s+\((?P<committed_pct>\d+)%\)",
    re.MULTILINE,
)

_PLATFORM_CPU_ROW_RE = re.compile(
    r"^\s*(?P<slot>(?:\d-)?RP\d)?\s*(?P<core>\d)\s+"
    r"(?P<user>[\d.]+)\s+(?P<system>[\d.]+)\s+(?P<nice>[\d.]+)\s+"
    r"(?P<idle>[\d.]+)\s+(?P<irq>[\d.]+)\s+(?P<sirq>[\d.]+)\s+(?P<iowait>[\d.]+)",
    re.MULTILINE,
)


def parse_platform_stats(raw: str) -> dict:
    """Parse 'show plat soft stat contr br' -> per-slot memory % and CPU max.

    CPU "max" here is the highest (100 - idle) seen across cores/slots in
    this single snapshot — run this on a schedule (e.g. every 5-15 min) and
    keep the daily max in state.json (see report.py) to reproduce a true
    "max observed today" figure like the manual report uses.
    """
    memory = []
    for m in _PLATFORM_MEM_RE.finditer(raw):
        memory.append({
            "slot": m.group("slot"),
            "used_pct": int(m.group("used_pct")),
            "free_pct": int(m.group("free_pct")),
        })

    cpu_busy_values = []
    last_slot = None
    for line in raw.splitlines():
        slot_match = re.match(r"^\s*((?:\d-)?RP\d)\s+\d", line)
        if slot_match:
            last_slot = slot_match.group(1)
        row = _PLATFORM_CPU_ROW_RE.match(line)
        if row:
            idle = float(row.group("idle"))
            cpu_busy_values.append(round(100 - idle, 2))

    return {
        "memory_pct": max((m["used_pct"] for m in memory), default=None),
        "memory_detail": memory,
        "cpu_max_pct": max(cpu_busy_values, default=None),
    }


# ---------------------------------------------------------------------------
# Classic IOS CPU — profile "classic_ios"
# Matches: show processes cpu | include utilization
#   CPU utilization for five seconds: 8%/2%; one minute: 7%; five minutes: 6%
# ---------------------------------------------------------------------------
_CPU_LINE_RE = re.compile(
    r"five seconds:\s*(?P<five_sec>\d+)%.*?"
    r"one minute:\s*(?P<one_min>\d+)%.*?"
    r"five minutes:\s*(?P<five_min>\d+)%",
    re.DOTALL,
)


def parse_cpu_utilization(raw: str) -> dict:
    m = _CPU_LINE_RE.search(raw)
    if not m:
        return {"five_sec": None, "one_min": None, "five_min": None}
    return {
        "five_sec": int(m.group("five_sec")),
        "one_min": int(m.group("one_min")),
        "five_min": int(m.group("five_min")),
    }


# ---------------------------------------------------------------------------
# Classic IOS memory — profile "classic_ios"
# Matches: show memory statistics
#   Processor    7F...  total  used  free  ...
# ---------------------------------------------------------------------------
_MEM_STAT_RE = re.compile(
    r"Processor\s+\S+\s+(?P<total>\d+)\s+(?P<used>\d+)\s+(?P<free>\d+)",
)


def parse_memory_statistics(raw: str) -> dict:
    m = _MEM_STAT_RE.search(raw)
    if not m:
        return {"used_pct": None}
    total, used = int(m.group("total")), int(m.group("used"))
    return {"used_pct": round(100 * used / total, 1) if total else None}


# ---------------------------------------------------------------------------
# Port status — both profiles
# Matches: show interfaces status
#   Port      Name               Status       Vlan       Duplex  Speed Type
#   Gi1/0/1                      connected    1            full    1000 ...
# ---------------------------------------------------------------------------
_PORT_STATUS_RE = re.compile(
    r"^(?P<port>\S+)\s+.*?\s+(?P<status>connected|notconnect|disabled|err-disabled|monitoring)\s+",
    re.MULTILINE,
)


def parse_interface_status(raw: str) -> list:
    ports = []
    for m in _PORT_STATUS_RE.finditer(raw):
        ports.append({"port": m.group("port"), "status": m.group("status")})
    return ports


def any_port_down(ports: list) -> bool:
    return any(p["status"] in ("notconnect", "err-disabled") for p in ports)


# ---------------------------------------------------------------------------
# WAN/uplink bandwidth + link status
# Matches: show interfaces <if>
# ---------------------------------------------------------------------------
_LINK_STATE_RE = re.compile(
    r"is (?P<state>up|down|administratively down),\s*line protocol is (?P<proto>up|down)"
)
_RATE_RE = re.compile(
    r"5 minute input rate\s+(?P<in_bps>\d+)\s+bits/sec.*?"
    r"5 minute output rate\s+(?P<out_bps>\d+)\s+bits/sec",
    re.DOTALL,
)


def parse_interface_rate(raw: str) -> dict:
    state_m = _LINK_STATE_RE.search(raw)
    rate_m = _RATE_RE.search(raw)
    return {
        "link_state": state_m.group("state") if state_m else None,
        "proto_state": state_m.group("proto") if state_m else None,
        "input_mbps": round(int(rate_m.group("in_bps")) / 1_000_000, 1) if rate_m else None,
        "output_mbps": round(int(rate_m.group("out_bps")) / 1_000_000, 1) if rate_m else None,
    }


# ---------------------------------------------------------------------------
# CPU history (last 60 minutes) — show processes cpu history
# ---------------------------------------------------------------------------
def parse_cpu_history_minutes(raw: str) -> list:
    """Extracts per-minute CPU% (oldest→newest, ~60 values) from the
    'CPU% per minute (last 60 minutes)' section of
    'show processes cpu history' / 'show proc cpu history'.

    Cisco prints each sample as a single digit on the line directly
    above the '100' row when the value is below 10% (too small to plot
    on the 10%-per-row grid). For values >=10%, a '*'/'#' mark appears
    in the graph body instead — we use that row's value as the reading
    for that column (an approximation: exact ones-digit reconciliation
    with the annotation row isn't attempted, since it's ambiguous by
    design in Cisco's own format).

    Returns [] if the section isn't present or the layout doesn't match
    the expected fixed structure (10 row-lines between the digit line
    and the axis) — callers should treat that as "not available" and
    fall back to another CPU source rather than erroring.
    """
    lines = raw.splitlines()
    label_idx = next((i for i, l in enumerate(lines) if "CPU% per minute" in l), None)
    if label_idx is None or label_idx < 13:
        return []
    hundred_line = lines[label_idx - 12]
    if "100" not in hundred_line:
        return []
    digit_line = lines[label_idx - 13]
    body_rows = lines[label_idx - 12: label_idx - 2]  # the 10 rows: 100, 90, ... 10
    col_start = len(digit_line) - len(digit_line.lstrip())
    data = digit_line.strip()
    width = len(data)
    if width == 0:
        return []

    values = []
    for col in range(width):
        marked = None
        for row_i, row_line in enumerate(body_rows):
            pos = col_start + col
            if pos < len(row_line) and row_line[pos] in "*#":
                marked = 100 - row_i * 10
                break  # topmost mark in this column = its highest value
        if marked is not None:
            values.append(marked)
        elif data[col].isdigit():
            values.append(int(data[col]))
        else:
            values.append(None)
    return values
