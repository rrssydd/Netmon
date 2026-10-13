"""Business logic layer — sits between the Flask routes and
db.py/netmon/*. Keeps app.py mostly just HTTP plumbing.
"""
import json
import os
from datetime import datetime, timedelta

import yaml

import db
from netmon import parsers, capture_parser, collector

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_thresholds() -> dict:
    with open(os.path.join(BASE_DIR, "config", "thresholds.yaml")) as f:
        return yaml.safe_load(f)


def classify(value, warn, crit) -> str:
    if value is None:
        return "unknown"
    if value >= crit:
        return "critical"
    if value >= warn:
        return "warning"
    return "normal"


# ---------------------------------------------------------------------------
# Live SSH collection — triggered by the "Collect Now" button
# ---------------------------------------------------------------------------
def run_live_collection() -> list:
    """Runs SSH collection for every configured device/wan-link/AP, writes
    results to the metrics table. Returns a list of human-readable log
    lines (errors + summary) to show the user after clicking the button."""
    log = []

    for device in db.list_devices():
        result = collector.collect_device(device)
        if "error" in result:
            log.append(f"[!] {result['error']}")
            continue
        raw = result["raw"]
        cpu_line = parsers.parse_cpu_utilization(raw.get("show processes cpu | include utilization", ""))
        cpu_hist = parsers.parse_cpu_history_minutes(raw.get("show processes cpu history", ""))
        cpu_hist_valid = [v for v in cpu_hist if v is not None]
        # Prefer the device's own last-60-minutes buffer: gives both a
        # current reading and a real peak from one command, no waiting
        # for our own polling history to build up. Falls back to the
        # one-minute average if history isn't available/parseable.
        cpu_actual = cpu_hist_valid[-1] if cpu_hist_valid else cpu_line["one_min"]
        cpu_peak = max(cpu_hist_valid) if cpu_hist_valid else None

        if device["profile"] == "platform_xe":
            stats = parsers.parse_platform_stats(raw.get("show plat soft stat contr br", ""))
            if cpu_actual is None:
                cpu_actual = stats["cpu_max_pct"]
            mem_pct = stats["memory_pct"]
        else:
            mem = parsers.parse_memory_statistics(raw.get("show memory statistics", ""))
            mem_pct = mem["used_pct"]
        cpu_max = cpu_actual
        ports = parsers.parse_interface_status(raw.get("show interfaces status", ""))
        port_down = parsers.any_port_down(ports)
        db.insert_metric("device", device["report_group"], "live",
                          cpu_max=cpu_max, cpu_peak=cpu_peak, mem_pct=mem_pct, port_down=port_down, port_details=ports or None)
        log.append(f"OK: {device['report_group']} -> CPU {cpu_max}%, mem {mem_pct}%")

    for link in db.list_wan_links():
        device = db.get_device(link["device_id"])
        raw = collector.collect_interface(device, link["interface"])
        if "error" in raw:
            log.append(f"[!] {raw['error']}")
            continue
        rate = parsers.parse_interface_rate(raw["raw"])
        db.insert_metric("wan", link["label"], "live",
                          input_mbps=rate["input_mbps"], output_mbps=rate["output_mbps"])
        log.append(f"OK: {link['label']} -> in {rate['input_mbps']}Mbps / out {rate['output_mbps']}Mbps")

    return log


# ---------------------------------------------------------------------------
# Capture-file import — triggered by the upload form
# ---------------------------------------------------------------------------
import re as _re


def _iface_key(s: str) -> str:
    """Normalizes interface naming so 'GigabitEthernet1/0/1' and
    'gig1/0/1' (or 'Gi1/0/1') compare equal — captures/live devices
    rarely use the same abbreviation."""
    m = _re.search(r"[\d/.]+$", s.strip())
    return m.group(0) if m else s.strip().lower()


def run_capture_import(text: str) -> dict:
    """Parses a pasted-capture text blob, matches against devices'
    capture_hostname / wan_links' interface, writes metrics. Returns a
    dict with 'imported' (labels written) and 'unmapped' (blocks that
    didn't match any configured device/wan-link) for the UI to show."""
    blocks = capture_parser.split_capture(text)

    devices = db.list_devices()
    wan_links = db.list_wan_links()
    host_to_device = {d["capture_hostname"]: d for d in devices if d.get("capture_hostname")}

    hosts_seen = {}
    for b in blocks:
        h = hosts_seen.setdefault(b["host"], {"cpu_platform": None, "cpu_line": None, "cpu_hist": None,
                                               "mem_pct": None, "port_down": False, "port_details": None, "matched": False})
        cmd = b["command"]
        if "plat soft stat contr br" in cmd:
            stats = parsers.parse_platform_stats(b["raw"])
            h["cpu_platform"], h["mem_pct"] = stats["cpu_max_pct"], stats["memory_pct"]
            h["matched"] = True
        elif ("processes cpu" in cmd or "proc cpu" in cmd) and "history" in cmd:
            hist = [v for v in parsers.parse_cpu_history_minutes(b["raw"]) if v is not None]
            if hist:
                h["cpu_hist"] = hist
                h["matched"] = True
        elif ("processes cpu" in cmd or "proc cpu" in cmd) and "history" not in cmd:
            cpu = parsers.parse_cpu_utilization(b["raw"])
            h["cpu_line"] = cpu["one_min"]
            h["matched"] = True
        elif "memory statistics" in cmd:
            mem = parsers.parse_memory_statistics(b["raw"])
            h["mem_pct"] = mem["used_pct"]
            h["matched"] = True
        elif "interface" in cmd and "status" in cmd:
            ports = parsers.parse_interface_status(b["raw"])
            h["port_down"] = parsers.any_port_down(ports)
            h["port_details"] = ports or None
            h["matched"] = True

    imported = []
    matched_block_keys = set()

    for host, metrics in hosts_seen.items():
        device = host_to_device.get(host)
        if not device or not metrics.pop("matched"):
            continue
        cpu_platform = metrics.pop("cpu_platform")
        cpu_line = metrics.pop("cpu_line")
        cpu_hist = metrics.pop("cpu_hist")
        if cpu_hist:
            metrics["cpu_max"] = cpu_hist[-1]
            metrics["cpu_peak"] = max(cpu_hist)
        else:
            metrics["cpu_max"] = cpu_line if cpu_line is not None else cpu_platform
            metrics["cpu_peak"] = None
        db.insert_metric("device", device["report_group"], "capture", **metrics)
        imported.append(device["report_group"])
        matched_block_keys.add(host)

    for link in wan_links:
        device = db.get_device(link["device_id"])
        capture_host = device.get("capture_hostname") if device else None
        link_key = _iface_key(link["interface"])
        block = next(
            (b for b in blocks
             if b["host"] == capture_host and "status" not in b["command"]
             and _iface_key(b["command"]) == link_key),
            None,
        )
        if not block:
            continue
        rate = parsers.parse_interface_rate(block["raw"])
        db.insert_metric("wan", link["label"], "capture",
                          input_mbps=rate["input_mbps"], output_mbps=rate["output_mbps"])
        imported.append(link["label"])
        matched_block_keys.add((block["host"], block["command"]))

    unmapped = []
    for b in blocks:
        key_host = b["host"] in matched_block_keys
        key_pair = (b["host"], b["command"]) in matched_block_keys
        if not key_host and not key_pair:
            unmapped.append(b)

    return {"imported": imported, "unmapped": unmapped}


# ---------------------------------------------------------------------------
# Dashboard aggregation (reads latest snapshot from metrics + applies status)
# ---------------------------------------------------------------------------
PEAK_FALLBACK_HOURS = 1  # used only when a device didn't give us on-device history


def daily_report_window(now=None, thresholds=None):
    """Return the configured daily traffic window and its Mbps limit."""
    thresholds = thresholds or load_thresholds()
    daily_config = thresholds.get("daily_report", {})
    wan_config = thresholds.get("wan_link", {})
    try:
        start_time = datetime.strptime(str(daily_config.get("start_time", "08:00")), "%H:%M").time()
    except ValueError:
        start_time = datetime.strptime("08:00", "%H:%M").time()
    try:
        daily_limit = float(daily_config.get("mbps_limit", wan_config.get("mbps_warning", 300)))
    except (TypeError, ValueError):
        daily_limit = 300.0
    now = now or datetime.now()
    window_start = now.replace(hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0)
    return window_start, now, start_time, daily_limit


def daily_traffic_series(entity_label, end_at=None):
    """Return today's live WAN samples using the same window as the Overview report."""
    thresholds = load_thresholds()
    try:
        report_end = datetime.strptime(end_at, "%Y-%m-%dT%H:%M:%S") if end_at else datetime.now()
    except ValueError as exc:
        raise ValueError("Waktu akhir report tidak valid.") from exc
    window_start, report_end, start_time, daily_limit = daily_report_window(report_end, thresholds)
    samples = db.live_wan_metrics_for_label_between(
        entity_label,
        window_start.isoformat(timespec="seconds"),
        report_end.isoformat(timespec="seconds"),
    )
    return {
        "start_at": window_start.strftime("%d %b %Y %H:%M"),
        "end_at": report_end.strftime("%d %b %Y %H:%M"),
        "start_time": start_time.strftime("%H:%M"),
        "limit_mbps": daily_limit,
        "samples": samples,
    }


def build_history_summaries(days: int) -> list:
    """Summarize each entity for the History & Trend table."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    summaries = {}
    for sample in db.history_samples_since(cutoff):
        entity_type = sample["entity_type"]
        fields = ("input_mbps", "output_mbps") if entity_type == "wan" else ("cpu_max", "mem_pct")
        values = {field: sample[field] for field in fields}
        if not any(value is not None for value in values.values()):
            continue
        key = (entity_type, sample["entity_label"])
        item = summaries.setdefault(key, {
            "entity_type": entity_type,
            "entity_label": sample["entity_label"],
            "sample_count": 0,
            "latest_at": None,
            "latest": {},
            "peaks": {field: {"value": None, "timestamp": None} for field in fields},
        })
        item["sample_count"] += 1
        item["latest_at"] = sample["timestamp"]
        item["latest"] = values
        for field, value in values.items():
            peak = item["peaks"][field]
            if value is not None and (peak["value"] is None or value > peak["value"]):
                peak["value"] = value
                peak["timestamp"] = sample["timestamp"]
    return sorted(summaries.values(), key=lambda item: (item["entity_type"], item["entity_label"].lower()))


def build_dashboard_data() -> dict:
    thresholds = load_thresholds()
    rs, wl = thresholds["router_switch"], thresholds["wan_link"]
    now = datetime.now()
    window_start, now, start_time, daily_limit = daily_report_window(now, thresholds)
    report_samples = db.wan_metrics_between(
        window_start.isoformat(timespec="seconds"), now.isoformat(timespec="seconds"))
    daily_peaks = {}
    for sample in report_samples:
        input_mbps = sample["input_mbps"]
        output_mbps = sample["output_mbps"]
        if input_mbps is None and output_mbps is None:
            continue
        item = daily_peaks.setdefault(sample["entity_label"], {
            "sample_count": 0,
            "peak_input_mbps": None, "peak_input_at": None,
            "peak_output_mbps": None, "peak_output_at": None,
            "latest_input_mbps": None, "latest_output_mbps": None, "latest_at": None,
        })
        item["sample_count"] += 1
        item["latest_input_mbps"] = input_mbps
        item["latest_output_mbps"] = output_mbps
        item["latest_at"] = sample["timestamp"]
        if input_mbps is not None and (item["peak_input_mbps"] is None or input_mbps > item["peak_input_mbps"]):
            item["peak_input_mbps"] = input_mbps
            item["peak_input_at"] = sample["timestamp"]
        if output_mbps is not None and (item["peak_output_mbps"] is None or output_mbps > item["peak_output_mbps"]):
            item["peak_output_mbps"] = output_mbps
            item["peak_output_at"] = sample["timestamp"]

    latest = {m["entity_label"]: m for m in db.latest_metrics()}

    devices = []
    for d in db.list_devices():
        m = latest.get(d["report_group"])
        cpu_max = m["cpu_max"] if m else None
        mem_pct = m["mem_pct"] if m else None
        port_down = bool(m["port_down"]) if m else False
        port_details = json.loads(m['port_details']) if m and m.get('port_details') else None
        disconnected = [p['port'] for p in (port_details or []) if p['status'] == 'notconnect']
        errors = [p['port'] for p in (port_details or []) if p['status'] == 'err-disabled']
        # Prefer the on-device 60-minute peak (from 'show processes cpu
        # history', captured at collection time). Fall back to our own
        # polling history only when that wasn't available for this device.
        cpu_peak_60m = (m["cpu_peak"] if m else None)
        if cpu_peak_60m is None:
            cpu_peak_60m = db.peak_value(d["report_group"], "cpu_max", hours=PEAK_FALLBACK_HOURS)
        cpu_status = classify(cpu_max, rs["cpu_warning"], rs["cpu_critical"])
        mem_status = classify(mem_pct, rs["mem_warning"], rs["mem_critical"])
        status = "critical" if "critical" in (cpu_status, mem_status) or errors else (
            "warning" if "warning" in (cpu_status, mem_status) else
            ("unknown" if "unknown" in (cpu_status, mem_status) else "normal")
        )
        devices.append({"report_group": d["report_group"], "cpu_max": cpu_max, "mem_pct": mem_pct,
                         "cpu_peak_60m": cpu_peak_60m,
                         "port_down": port_down, "disconnected_ports": disconnected, "error_ports": errors,
                         "port_details": port_details, "cpu_status": cpu_status, "mem_status": mem_status,
                         "status": status, "last_seen": m["timestamp"] if m else None})

    wan_links = []
    for link in db.list_wan_links():
        m = latest.get(link["label"])
        in_mbps = m["input_mbps"] if m else None
        out_mbps = m["output_mbps"] if m else None
        peak = max(in_mbps or 0, out_mbps or 0)
        status = classify(peak, wl["mbps_warning"], wl["mbps_critical"]) if m else "unknown"
        daily = daily_peaks.get(link["label"], {
            "sample_count": 0,
            "peak_input_mbps": None, "peak_input_at": None,
            "peak_output_mbps": None, "peak_output_at": None,
            "latest_input_mbps": None, "latest_output_mbps": None, "latest_at": None,
        })
        daily_peak = max((value for value in (daily["peak_input_mbps"], daily["peak_output_mbps"])
                          if value is not None), default=None)
        if daily_peak is None:
            daily_status = "unknown"
        elif daily_peak > daily_limit:
            daily_status = "exceeded"
        elif daily_peak == daily_limit:
            daily_status = "at_limit"
        else:
            daily_status = "normal"
        wan_links.append({"label": link["label"], "input_mbps": in_mbps, "output_mbps": out_mbps,
                           "status": status, "last_seen": m["timestamp"] if m else None,
                           "daily_peak": daily, "daily_status": daily_status,
                           "daily_limit": daily_limit})

    all_statuses = [d["status"] for d in devices] + [w["status"] for w in wan_links]
    summary = {
        "device_count": len(devices), "wan_count": len(wan_links),
        "normal": all_statuses.count("normal"),
        "warning": all_statuses.count("warning"),
        "critical": all_statuses.count("critical"),
        "unknown": all_statuses.count("unknown"),
    }

    return {
        "generated_at": now.strftime("%A, %d %B %Y %H:%M"),
        "report_id": "RPT-" + now.strftime("%Y%m%d-%H%M"),
        "daily_traffic": {
            "start_time": start_time.strftime("%H:%M"),
            "start_at": window_start.strftime("%d %b %Y %H:%M"),
            "end_at": now.strftime("%d %b %Y %H:%M"),
            "window_start": window_start.isoformat(timespec="seconds"),
            "window_end": now.isoformat(timespec="seconds"),
            "started": window_start <= now,
            "limit_mbps": daily_limit,
        },
        "devices": devices, "wan_links": wan_links, "summary": summary,
        "any_port_down": any(d["port_down"] for d in devices),
    }
