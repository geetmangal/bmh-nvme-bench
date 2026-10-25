#!/usr/bin/env python3
"""bmh-nvme-bench report generator (Python 3.8+, stdlib only).

    report.py RUN_DIR [--json-only] [--blog]
    report.py compare RUN_DIR... [--labels a,b,...] [--out DIR] [--json-only]
    report.py median RUN_DIR... --out DIR [--json-only]

Parses the raw files written by bench.sh (fio JSON, sysbench text, iperf3 JSON, ping,
curl TTFB, steal probe) into a normalised summary.json (schema: docs/schema.md) and renders
summary.md / summary.html / summary.csv. `compare` builds side-by-side tables with x-faster
deltas and INR per 10k IOPS. `median` folds repeated runs of the same profile (separate run dirs)
into one summary whose numeric metrics are the median across runs, plus a per-run table.

Exit codes: 0 ok, 1 usage error, 2 run dir missing or no parsable data, 3 parse error.
"""
from __future__ import annotations

import argparse
import csv
import glob
import html
import json
import os
import re
import statistics
import sys
from datetime import datetime, timezone, timedelta

SCHEMA_VERSION = 1
IST = timezone(timedelta(hours=5, minutes=30))

# Order in which disk tests appear in tables; anything else is appended alphabetically.
DISK_ORDER = [
    "4k-randread-qd1", "4k-randread-qd32", "4k-randread-qd64", "4k-randwrite-qd1",
    "4k-randwrite-qd32", "4k-randrw70-qd32", "64k-seqread", "64k-seqwrite",
    "1m-seqread", "1m-seqwrite", "4k-randread-lat-qd1", "4k-fsync-write",
]
HEADLINE = [
    ("4k-randread-qd1", "iops", "4k random read IOPS (QD1)"),
    ("4k-randread-qd32", "iops", "4k random read IOPS (QD32)"),
    ("4k-randwrite-qd32", "iops", "4k random write IOPS (QD32)"),
    ("1m-seqread", "bw_mbps", "1M sequential read MB/s"),
    ("1m-seqwrite", "bw_mbps", "1M sequential write MB/s"),
    ("4k-randread-lat-qd1", "p99_us", "4k read latency p99 (us, QD1)"),
    ("4k-fsync-write", "p99_us", "4k fsync write latency p99 (us)"),
]


class ParseError(Exception):
    pass


# ----------------------------------------------------------------------------- helpers
def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    # fio sometimes prints warnings before the JSON object; skip to the first '{'
    i = text.find("{")
    if i < 0:
        raise ParseError(f"{path}: no JSON object found")
    try:
        return json.loads(text[i:])
    except json.JSONDecodeError as exc:
        raise ParseError(f"{path}: {exc}") from exc


def _pct(d, key):
    """Return percentile `key` (e.g. 99.0) from a fio percentiles dict, ns -> us."""
    if not d:
        return None
    for k, v in d.items():
        try:
            if abs(float(k) - key) < 1e-6:
                return v / 1000.0
        except ValueError:
            continue
    return None


def _median(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def _r(v, nd=1):
    return None if v is None else round(v, nd)


# ----------------------------------------------------------------------------- fio
def parse_fio(path):
    """Parse one fio --output-format=json file. Multiple jobs are summed for IOPS/BW; latency
    percentiles use the worst job (conservative) and mean latency is IO-weighted."""
    data = _load_json(path)
    jobs = data.get("jobs") or []
    if not jobs:
        raise ParseError(f"{path}: no jobs")
    out = {"jobs": len(jobs), "fio_version": data.get("fio version"), "read": None, "write": None, "sync": None}
    for direction in ("read", "write"):
        ios = sum(j.get(direction, {}).get("total_ios", 0) for j in jobs)
        if ios == 0:
            continue
        iops = sum(j[direction].get("iops", 0.0) for j in jobs)
        bw_bytes = sum(j[direction].get("bw_bytes", j[direction].get("bw", 0) * 1024) for j in jobs)
        lat_key = "lat_ns" if any("percentile" in j[direction].get("lat_ns", {}) for j in jobs) else "clat_ns"
        pcts = [j[direction].get(lat_key, {}).get("percentile") or j[direction].get("clat_ns", {}).get("percentile") for j in jobs]
        means = [(j[direction].get(lat_key, j[direction].get("clat_ns", {})).get("mean", 0.0), j[direction].get("total_ios", 0)) for j in jobs]
        mean_us = sum(m * n for m, n in means) / max(1, sum(n for _, n in means)) / 1000.0
        out[direction] = {
            "iops": _r(iops, 1),
            "bw_mbps": _r(bw_bytes / 1e6, 1),
            "total_ios": ios,
            "lat_us": {
                "mean": _r(mean_us, 1),
                "p50": _r(max((_pct(p, 50.0) or 0) for p in pcts), 1) if any(pcts) else None,
                "p99": _r(max((_pct(p, 99.0) or 0) for p in pcts), 1) if any(pcts) else None,
                "p999": _r(max((_pct(p, 99.9) or 0) for p in pcts), 1) if any(pcts) else None,
            },
        }
    syncs = [j.get("sync") for j in jobs if j.get("sync") and j["sync"].get("total_ios", 0) > 0]
    if syncs:
        pcts = [s.get("lat_ns", {}).get("percentile") for s in syncs]
        out["sync"] = {
            "total_ios": sum(s["total_ios"] for s in syncs),
            "lat_us": {
                "mean": _r(sum(s["lat_ns"].get("mean", 0) for s in syncs) / len(syncs) / 1000.0, 1),
                "p50": _r(max((_pct(p, 50.0) or 0) for p in pcts), 1),
                "p99": _r(max((_pct(p, 99.0) or 0) for p in pcts), 1),
                "p999": _r(max((_pct(p, 99.9) or 0) for p in pcts), 1),
            },
        }
    j0 = jobs[0].get("job options", {})
    g0 = (data.get("global options") or {})
    opts = {**g0, **j0}
    out["options"] = {k: opts.get(k) for k in ("rw", "bs", "iodepth", "numjobs", "rwmixread", "fsync", "runtime", "size") if opts.get(k) is not None}
    return out


def _disk_entry(name, parsed_list):
    """Collapse 1..n repeats of a fio test into one entry (median per metric)."""
    primary = "read"
    if all(p.get("read") is None for p in parsed_list):
        primary = "write"
    entry = {"name": name, "repeats": len(parsed_list), "primary": primary, "options": parsed_list[0].get("options", {}), "jobs": parsed_list[0]["jobs"]}
    for direction in ("read", "write"):
        rows = [p[direction] for p in parsed_list if p.get(direction)]
        if not rows:
            continue
        entry[direction] = {
            "iops": _r(_median([r["iops"] for r in rows]), 1),
            "bw_mbps": _r(_median([r["bw_mbps"] for r in rows]), 1),
            "lat_us": {k: _r(_median([r["lat_us"][k] for r in rows]), 1) for k in ("mean", "p50", "p99", "p999")},
        }
    syncs = [p["sync"] for p in parsed_list if p.get("sync")]
    if syncs:
        entry["sync"] = {"lat_us": {k: _r(_median([s["lat_us"][k] for s in syncs]), 1) for k in ("mean", "p50", "p99", "p999")}}
    p = entry.get(primary) or {}
    entry["iops"] = (entry.get("read", {}).get("iops") or 0) + (entry.get("write", {}).get("iops") or 0) if name.startswith("4k-randrw") else p.get("iops")
    entry["bw_mbps"] = (entry.get("read", {}).get("bw_mbps") or 0) + (entry.get("write", {}).get("bw_mbps") or 0) if name.startswith("4k-randrw") else p.get("bw_mbps")
    lat_src = entry.get("sync", p).get("lat_us", {}) if "fsync" in name else p.get("lat_us", {})
    entry["p50_us"] = lat_src.get("p50")
    entry["p99_us"] = lat_src.get("p99")
    entry["p999_us"] = lat_src.get("p999")
    entry["mean_us"] = lat_src.get("mean")
    return entry


def parse_disk(run_dir):
    files = sorted(glob.glob(os.path.join(run_dir, "fio", "*.json")))
    groups = {}
    for f in files:
        base = os.path.basename(f)[:-5]
        if base == "prefill":
            continue
        name = re.sub(r"\.r\d+$", "", base)
        groups.setdefault(name, []).append(f)
    disk = {}
    for name, paths in groups.items():
        parsed = []
        for p in paths:
            try:
                parsed.append(parse_fio(p))
            except ParseError as exc:
                print(f"warning: {exc}", file=sys.stderr)
        if parsed:
            disk[name] = _disk_entry(name, parsed)
    return disk


# ----------------------------------------------------------------------------- sysbench
def parse_sysbench_cpu(text):
    out = {}
    m = re.search(r"events per second:\s*([\d.]+)", text)
    if m:
        out["events_per_second"] = float(m.group(1))
    m = re.search(r"Number of threads:\s*(\d+)", text)
    if m:
        out["threads"] = int(m.group(1))
    m = re.search(r"total number of events:\s*(\d+)", text)
    if m:
        out["events"] = int(m.group(1))
    m = re.search(r"95th percentile:\s*([\d.]+)", text)
    if m:
        out["lat_p95_ms"] = float(m.group(1))
    if "events_per_second" not in out:
        raise ParseError("sysbench cpu: 'events per second' not found")
    return out


def parse_sysbench_mem(text):
    out = {}
    m = re.search(r"\(([\d.]+)\s*MiB/sec\)", text)
    if m:
        out["mib_per_sec"] = float(m.group(1))
    m = re.search(r"Total operations:\s*(\d+)\s*\(([\d.]+) per second\)", text)
    if m:
        out["ops_per_sec"] = float(m.group(2))
    m = re.search(r"block size:\s*(\d+)KiB", text)
    if m:
        out["block_kib"] = int(m.group(1))
    if "mib_per_sec" not in out:
        raise ParseError("sysbench memory: 'MiB/sec' not found")
    return out


def _read_text(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def parse_cpu(run_dir):
    cpu = {}
    for key, fname in (("single_thread", "cpu-1t.txt"), ("all_threads", "cpu-nt.txt")):
        p = os.path.join(run_dir, "sysbench", fname)
        if os.path.exists(p):
            try:
                cpu[key] = parse_sysbench_cpu(_read_text(p))
            except ParseError as exc:
                print(f"warning: {fname}: {exc}", file=sys.stderr)
    if "single_thread" in cpu and "all_threads" in cpu and cpu["single_thread"]["events_per_second"]:
        cpu["scaling"] = _r(cpu["all_threads"]["events_per_second"] / cpu["single_thread"]["events_per_second"], 2)
    return cpu


def parse_mem(run_dir):
    mem = {}
    for key, fname in (("read", "mem-read.txt"), ("write", "mem-write.txt")):
        p = os.path.join(run_dir, "sysbench", fname)
        if os.path.exists(p):
            try:
                mem[key] = parse_sysbench_mem(_read_text(p))
            except ParseError as exc:
                print(f"warning: {fname}: {exc}", file=sys.stderr)
    return mem


# ----------------------------------------------------------------------------- network
def parse_iperf3(path):
    data = _load_json(path)
    if "error" in data:
        raise ParseError(f"{path}: iperf3 error: {data['error']}")
    end = data.get("end", {})
    sent = end.get("sum_sent", {})
    recv = end.get("sum_received", {})
    reverse = bool(data.get("start", {}).get("test_start", {}).get("reverse"))
    out = {
        "sent_mbps": _r(sent.get("bits_per_second", 0) / 1e6, 1),
        "received_mbps": _r(recv.get("bits_per_second", 0) / 1e6, 1),
        "retransmits": sent.get("retransmits"),
        "streams": data.get("start", {}).get("test_start", {}).get("num_streams"),
        "duration_s": _r(sent.get("seconds") or recv.get("seconds"), 1),
        "reverse": reverse,
    }
    out["mbps"] = out["received_mbps"] or out["sent_mbps"]
    return out


def parse_ping(text):
    out = {}
    m = re.search(r"(\d+) packets transmitted, (\d+) (?:packets )?received.*?([\d.]+)% packet loss", text, re.S)
    if m:
        out["sent"], out["received"], out["loss_pct"] = int(m.group(1)), int(m.group(2)), float(m.group(3))
    m = re.search(r"= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms", text)
    if m:
        out["min_ms"], out["avg_ms"], out["max_ms"], out["mdev_ms"] = (float(m.group(i)) for i in range(1, 5))
    m = re.search(r"PING (\S+) \(([\d.a-f:]+)\)", text)
    if m:
        out["host"], out["ip"] = m.group(1), m.group(2)
    if "avg_ms" not in out:
        raise ParseError("ping: rtt summary not found")
    return out


def parse_curl_ttfb(text):
    vals = [float(m) for m in re.findall(r"ttfb=([\d.]+)", text)]
    if not vals:
        raise ParseError("curl: no ttfb= values")
    codes = re.findall(r"http=(\d+)", text)
    return {"samples": len(vals), "ttfb_ms_min": _r(min(vals) * 1000, 1), "ttfb_ms_median": _r(statistics.median(vals) * 1000, 1), "http_codes": sorted(set(codes))}


def parse_net(run_dir):
    net = {"iperf3": {}, "ping": {}, "ttfb": {}}
    for key, fname in (("upload", "iperf3-up.json"), ("download", "iperf3-down.json")):
        p = os.path.join(run_dir, "net", fname)
        if os.path.exists(p):
            try:
                net["iperf3"][key] = parse_iperf3(p)
            except ParseError as exc:
                print(f"warning: {exc}", file=sys.stderr)
    for p in sorted(glob.glob(os.path.join(run_dir, "net", "ping-*.txt"))):
        try:
            r = parse_ping(_read_text(p))
            net["ping"][r.get("host", os.path.basename(p)[5:-4])] = r
        except ParseError as exc:
            print(f"warning: {p}: {exc}", file=sys.stderr)
    for p in sorted(glob.glob(os.path.join(run_dir, "net", "curl-ttfb-*.txt"))):
        try:
            net["ttfb"][os.path.basename(p)[10:-4]] = parse_curl_ttfb(_read_text(p))
        except ParseError as exc:
            print(f"warning: {p}: {exc}", file=sys.stderr)
    return net


# ----------------------------------------------------------------------------- probe / extras
def parse_probe(run_dir):
    probe = {}
    p = os.path.join(run_dir, "probe", "steal.csv")
    if os.path.exists(p):
        steals = []
        with open(p, newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    steals.append(float(row["steal_pct"]))
                except (KeyError, ValueError):
                    pass
        if steals:
            probe["steal"] = {"samples": len(steals), "avg_pct": _r(statistics.mean(steals), 3), "max_pct": _r(max(steals), 3), "p95_pct": _r(sorted(steals)[int(0.95 * (len(steals) - 1))], 3)}
    lats = []
    for f in sorted(glob.glob(os.path.join(run_dir, "probe", "lat-*.json"))):
        try:
            r = parse_fio(f).get("read") or {}
            lats.append({"file": os.path.basename(f), "p50_us": r.get("lat_us", {}).get("p50"), "p99_us": r.get("lat_us", {}).get("p99"), "iops": r.get("iops")})
        except ParseError as exc:
            print(f"warning: {exc}", file=sys.stderr)
    if lats:
        p99s = [x["p99_us"] for x in lats if x["p99_us"] is not None]
        probe["latency_samples"] = lats
        probe["latency_p99_us_min"] = min(p99s) if p99s else None
        probe["latency_p99_us_max"] = max(p99s) if p99s else None
        probe["latency_p99_spread_x"] = _r(max(p99s) / min(p99s), 2) if p99s and min(p99s) else None
    return probe


def parse_extras(run_dir):
    extras = {}
    p = os.path.join(run_dir, "extras", "pyloop.txt")
    if os.path.exists(p):
        m = re.search(r"score=([\d.]+)", _read_text(p))
        if m:
            extras["pyloop_mops"] = float(m.group(1))
    p = os.path.join(run_dir, "extras", "openssl.txt")
    if os.path.exists(p):
        # last line: "AES-256-GCM  k  k  k  k  k  k" (in 1000s of bytes/s); take the 16384-byte column
        for line in _read_text(p).splitlines()[::-1]:
            if line.lower().startswith("aes-256-gcm"):
                nums = re.findall(r"([\d.]+)k", line)
                if nums:
                    extras["openssl_aes256gcm_16k_mbps"] = _r(float(nums[-1]) * 1000 / 1e6, 1)
                break
    return extras


# ----------------------------------------------------------------------------- summary
def build_summary(run_dir):
    run_dir = run_dir.rstrip("/\\")
    if not os.path.isdir(run_dir):
        raise FileNotFoundError(run_dir)
    run = {}
    p = os.path.join(run_dir, "run.json")
    if os.path.exists(p):
        run = _load_json(p)
    sysinfo = {}
    p = os.path.join(run_dir, "sysinfo.json")
    if os.path.exists(p):
        sysinfo = _load_json(p)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_ist": datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S%z"),
        "run_dir": os.path.basename(run_dir),
        "run": run,
        "system": sysinfo,
        "disk": parse_disk(run_dir),
        "cpu": parse_cpu(run_dir),
        "memory": parse_mem(run_dir),
        "network": parse_net(run_dir),
        "probe": parse_probe(run_dir),
        "extras": parse_extras(run_dir),
    }
    summary["headline"] = headline_rows(summary)
    if not (summary["disk"] or summary["cpu"] or summary["memory"] or summary["network"]["iperf3"]):
        raise ParseError(f"{run_dir}: no parsable results found")
    return summary


def headline_rows(s):
    rows = []
    for test, metric, title in HEADLINE:
        d = s["disk"].get(test)
        if d and d.get(metric) is not None:
            rows.append({"metric": title, "value": d[metric], "unit": metric_unit(metric), "test": test, "key": metric})
    cpu = s.get("cpu", {})
    if cpu.get("single_thread"):
        rows.append({"metric": "sysbench CPU events/s (1 thread)", "value": cpu["single_thread"]["events_per_second"], "unit": "events/s", "test": "cpu", "key": "single_thread"})
    if cpu.get("all_threads"):
        rows.append({"metric": f"sysbench CPU events/s ({cpu['all_threads'].get('threads', '?')} threads)", "value": cpu["all_threads"]["events_per_second"], "unit": "events/s", "test": "cpu", "key": "all_threads"})
    mem = s.get("memory", {})
    if mem.get("read"):
        rows.append({"metric": "Memory read MiB/s (1 thread)", "value": mem["read"]["mib_per_sec"], "unit": "MiB/s", "test": "mem", "key": "read"})
    if mem.get("write"):
        rows.append({"metric": "Memory write MiB/s (1 thread)", "value": mem["write"]["mib_per_sec"], "unit": "MiB/s", "test": "mem", "key": "write"})
    ip = s.get("network", {}).get("iperf3", {})
    if ip.get("download"):
        rows.append({"metric": "iperf3 download Mbit/s", "value": ip["download"]["mbps"], "unit": "Mbit/s", "test": "net", "key": "download"})
    if ip.get("upload"):
        rows.append({"metric": "iperf3 upload Mbit/s", "value": ip["upload"]["mbps"], "unit": "Mbit/s", "test": "net", "key": "upload"})
    pr = s.get("probe", {})
    if pr.get("steal"):
        rows.append({"metric": "CPU steal avg % (probe)", "value": pr["steal"]["avg_pct"], "unit": "%", "test": "probe", "key": "steal"})
    return rows


def metric_unit(metric):
    return {"iops": "IOPS", "bw_mbps": "MB/s", "p50_us": "us", "p99_us": "us", "p999_us": "us", "mean_us": "us"}.get(metric, "")


def fmt(v, nd=None):
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        if nd is not None:
            return f"{v:,.{nd}f}"
        if abs(v) >= 1000:
            return f"{v:,.0f}"
        if abs(v) >= 100:
            return f"{v:,.1f}"
        return f"{v:,.2f}" if isinstance(v, float) else str(v)
    return str(v)


def ordered_disk(disk):
    names = [n for n in DISK_ORDER if n in disk] + sorted(n for n in disk if n not in DISK_ORDER)
    return [(n, disk[n]) for n in names]


# ----------------------------------------------------------------------------- markdown
def md_table(headers, rows, align=None):
    align = align or ["---"] * len(headers)
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(align) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def reproduce_cmd(run):
    parts = ["./bench.sh", f"--profile {run.get('profile', 'standard')}"]
    if run.get("size"):
        parts.append(f"--size {run['size']}")
    if run.get("runtime_s"):
        parts.append(f"--runtime {run['runtime_s']}")
    if run.get("label"):
        parts.append(f"--label \"{run['label']}\"")
    if run.get("provider") and run["provider"] != "unknown":
        parts.append(f"--provider {run['provider']}")
    if run.get("plan_price_inr"):
        parts.append(f"--plan-price-inr {run['plan_price_inr']}")
    if run.get("iperf_server"):
        parts.append(f"--iperf-server {run['iperf_server']}")
    parts.append("--no-prompt")
    return " ".join(parts)


def render_md(s):
    run, sysi = s["run"], s["system"]
    label = run.get("label") or s["run_dir"]
    L = [f"# Benchmark results: {label}", ""]
    L.append(f"*Profile `{run.get('profile', '?')}`, fio file {run.get('size', '?')}, {run.get('runtime_s', '?')} s per job, "
             f"{run.get('repeats', 1)} repeat(s). Run started {run.get('started_ist', '?')} IST ({run.get('started_utc', '?')} UTC) on `{run.get('hostname', '?')}`"
             + (f", provider **{run['provider']}**" if run.get("provider") and run["provider"] != "unknown" else "")
             + (f", plan price INR {run['plan_price_inr']}/month" if run.get("plan_price_inr") else "") + ".*")
    L += ["", "## Headline numbers", ""]
    L.append(md_table(["Metric", "Value", "Unit"], [(r["metric"], fmt(r["value"]), r["unit"]) for r in s["headline"]], ["---", "---:", "---"]))
    if s["disk"]:
        L += ["", "## Disk (fio, direct=1, libaio)", ""]
        rows = []
        for name, d in ordered_disk(s["disk"]):
            o = d.get("options", {})
            rows.append((f"`{name}`", o.get("rw", "-"), o.get("bs", "-"), o.get("iodepth", "-"), o.get("numjobs", d.get("jobs", "-")),
                         fmt(d.get("iops"), 0), fmt(d.get("bw_mbps"), 1), fmt(d.get("mean_us"), 0), fmt(d.get("p50_us"), 0), fmt(d.get("p99_us"), 0), fmt(d.get("p999_us"), 0)))
        L.append(md_table(["Test", "rw", "bs", "QD", "jobs", "IOPS", "MB/s", "lat mean us", "p50 us", "p99 us", "p99.9 us"], rows,
                          ["---", "---", "---", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:"]))
        mixed = [(n, d) for n, d in ordered_disk(s["disk"]) if d.get("read") and d.get("write")]
        if mixed:
            L += ["", "### Mixed workloads, read/write split", ""]
            L.append(md_table(["Test", "Read IOPS", "Read p99 us", "Write IOPS", "Write p99 us"],
                              [(f"`{n}`", fmt(d["read"]["iops"], 0), fmt(d["read"]["lat_us"]["p99"], 0), fmt(d["write"]["iops"], 0), fmt(d["write"]["lat_us"]["p99"], 0)) for n, d in mixed],
                              ["---", "---:", "---:", "---:", "---:"]))
    cpu, mem = s["cpu"], s["memory"]
    if cpu or mem:
        L += ["", "## CPU and memory (sysbench)", ""]
        rows = []
        if cpu.get("single_thread"):
            rows.append(("CPU, 1 thread, max-prime 20000", fmt(cpu["single_thread"]["events_per_second"], 1), "events/s"))
        if cpu.get("all_threads"):
            rows.append((f"CPU, {cpu['all_threads'].get('threads', '?')} threads", fmt(cpu["all_threads"]["events_per_second"], 1), "events/s"))
        if cpu.get("scaling") is not None:
            rows.append(("Thread scaling (all / 1)", fmt(cpu["scaling"], 2), "x"))
        if mem.get("read"):
            rows.append(("Memory read, 1 MiB blocks", fmt(mem["read"]["mib_per_sec"], 0), "MiB/s"))
        if mem.get("write"):
            rows.append(("Memory write, 1 MiB blocks", fmt(mem["write"]["mib_per_sec"], 0), "MiB/s"))
        ex = s.get("extras", {})
        if ex.get("openssl_aes256gcm_16k_mbps"):
            rows.append(("openssl aes-256-gcm, 16 KiB blocks", fmt(ex["openssl_aes256gcm_16k_mbps"], 0), "MB/s"))
        if ex.get("pyloop_mops"):
            rows.append(("Pure-Python loop sanity score", fmt(ex["pyloop_mops"], 2), "Mops/s"))
        L.append(md_table(["Test", "Result", "Unit"], rows, ["---", "---:", "---"]))
    net = s["network"]
    if net["iperf3"] or net["ping"] or net["ttfb"]:
        L += ["", "## Network", ""]
        rows = []
        for k in ("download", "upload"):
            if net["iperf3"].get(k):
                r = net["iperf3"][k]
                rows.append((f"iperf3 {k} ({r.get('streams', '?')} streams, {fmt(r.get('duration_s'), 0)} s)", fmt(r["mbps"], 0), "Mbit/s", f"retransmits {fmt(r.get('retransmits'))}"))
        for host, r in net["ping"].items():
            rows.append((f"ping {host}", fmt(r["avg_ms"], 2), "ms avg", f"min {fmt(r.get('min_ms'), 2)} / max {fmt(r.get('max_ms'), 2)} / mdev {fmt(r.get('mdev_ms'), 2)} ms, loss {fmt(r.get('loss_pct'))}%"))
        for host, r in net["ttfb"].items():
            rows.append((f"curl TTFB {host}", fmt(r["ttfb_ms_median"], 0), "ms median", f"min {fmt(r['ttfb_ms_min'], 0)} ms over {r['samples']} requests"))
        L.append(md_table(["Test", "Result", "Unit", "Detail"], rows, ["---", "---:", "---", "---"]))
    pr = s["probe"]
    if pr:
        L += ["", "## Noisy-neighbour probe", ""]
        if pr.get("steal"):
            st = pr["steal"]
            L.append(f"- CPU steal over {st['samples']} s: avg **{fmt(st['avg_pct'], 2)} %**, p95 {fmt(st['p95_pct'], 2)} %, max {fmt(st['max_pct'], 2)} % (baseline before run: {fmt(sysi.get('steal_baseline_pct'), 2)} %).")
        if pr.get("latency_samples"):
            L.append(f"- 4k QD1 read p99 across {len(pr['latency_samples'])} samples: {fmt(pr['latency_p99_us_min'], 0)} - {fmt(pr['latency_p99_us_max'], 0)} us (spread {fmt(pr['latency_p99_spread_x'], 2)}x). A spread above 2x usually means a busy neighbour.")
    if sysi:
        L += ["", "## System", ""]
        c, d = sysi.get("cpu", {}), sysi.get("disk", {})
        L.append(md_table(["Fact", "Value"], [
            ("Hostname", f"`{sysi.get('hostname', '-')}`"), ("CPU", f"{c.get('model', '-')} ({c.get('cores', '?')} cores / {c.get('threads', '?')} threads, {fmt(c.get('mhz'), 0)} MHz)"),
            ("RAM", f"{fmt(sysi.get('ram_mib'), 0)} MiB"), ("Virtualisation", sysi.get("virt", "-")), ("Kernel", sysi.get("kernel", "-")), ("Distro", sysi.get("distro", "-")),
            ("Disk", f"{d.get('device', '-')} {d.get('model', '')} (scheduler {d.get('scheduler', '-')}, rotational {fmt(d.get('rotational'))})"),
            ("Filesystem", f"{d.get('fstype', '-')} on {d.get('mount', '-')}"),
            ("Tools", ", ".join(f"{k} {v}" for k, v in run.get("tools", {}).items())),
        ]))
    L += ["", "## Methodology", "",
          "All disk tests use fio with `--direct=1` (bypasses the page cache), `ioengine=libaio`, `time_based` runs on a pre-filled file written with real data, "
          "and `group_reporting`. Latency percentiles are completion latencies; the dedicated latency test uses `lat_percentiles`. QD1 shows what a single "
          "synchronous thread sees; QD32 shows throughput under parallel load. Mixed 70/30 approximates OLTP. The fsync test measures what a database commit "
          "pays per transaction. CPU is sysbench prime search (deterministic). Full details, caveats for VMs (steal, ballooning, thin provisioning) and fairness rules "
          "in [docs/methodology.md](https://github.com/geetmangal/bmh-nvme-bench/blob/main/docs/methodology.md).", "",
          "## Reproduce", "", "```bash", "git clone https://github.com/geetmangal/bmh-nvme-bench && cd bmh-nvme-bench", reproduce_cmd(run), "python3 report.py results/<run-dir>/", "```", "",
          f"*Generated by bmh-nvme-bench {run.get('bench_version', '')} report.py at {s['generated_ist']} IST. Published results from BookMyHost NVMe nodes: https://bookmyhost.com*", ""]
    return "\n".join(L)


# ----------------------------------------------------------------------------- csv
def summary_rows(s):
    """Flat rows: section,test,metric,value,unit."""
    rows = []
    for name, d in ordered_disk(s["disk"]):
        for k in ("iops", "bw_mbps", "mean_us", "p50_us", "p99_us", "p999_us"):
            if d.get(k) is not None:
                rows.append(("disk", name, k, d[k], metric_unit(k)))
        for direction in ("read", "write"):
            if d.get(direction) and d.get("read") and d.get("write"):
                rows.append(("disk", name, f"{direction}_iops", d[direction]["iops"], "IOPS"))
                rows.append(("disk", name, f"{direction}_p99_us", d[direction]["lat_us"]["p99"], "us"))
    for k, v in s["cpu"].items():
        if isinstance(v, dict):
            rows.append(("cpu", k, "events_per_second", v["events_per_second"], "events/s"))
        else:
            rows.append(("cpu", k, "ratio", v, "x"))
    for k, v in s["memory"].items():
        rows.append(("memory", k, "mib_per_sec", v["mib_per_sec"], "MiB/s"))
    for k, v in s["network"]["iperf3"].items():
        rows.append(("network", f"iperf3_{k}", "mbps", v["mbps"], "Mbit/s"))
    for k, v in s["network"]["ping"].items():
        rows.append(("network", f"ping_{k}", "avg_ms", v["avg_ms"], "ms"))
        rows.append(("network", f"ping_{k}", "loss_pct", v.get("loss_pct"), "%"))
    for k, v in s["network"]["ttfb"].items():
        rows.append(("network", f"ttfb_{k}", "median_ms", v["ttfb_ms_median"], "ms"))
    if s["probe"].get("steal"):
        rows.append(("probe", "steal", "avg_pct", s["probe"]["steal"]["avg_pct"], "%"))
        rows.append(("probe", "steal", "max_pct", s["probe"]["steal"]["max_pct"], "%"))
    if s["probe"].get("latency_p99_spread_x") is not None:
        rows.append(("probe", "latency", "p99_spread_x", s["probe"]["latency_p99_spread_x"], "x"))
    for k, v in s["extras"].items():
        rows.append(("extras", k, "value", v, ""))
    return rows


def write_csv(s, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["label", "section", "test", "metric", "value", "unit"])
        label = s["run"].get("label") or s["run_dir"]
        for r in summary_rows(s):
            w.writerow([label, *r])


# ----------------------------------------------------------------------------- html + svg
CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#1b1f23;background:#fff;line-height:1.45}
h1,h2,h3{line-height:1.2}h1{border-bottom:2px solid #0b5fff;padding-bottom:.3rem}
table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.92rem}th,td{border:1px solid #d9dee3;padding:.4rem .6rem;text-align:left}
th{background:#f3f6fa}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}code{background:#f3f6fa;padding:.1rem .3rem;border-radius:3px}
pre{background:#f3f6fa;padding:.8rem;overflow:auto}.chart{margin:1rem 0}.muted{color:#5b6670}footer{margin:2rem 0;color:#5b6670;font-size:.85rem}
.bar{fill:#0b5fff}.bar.alt{fill:#f28c28}.bar.c2{fill:#2bb673}.bar.c3{fill:#9b59b6}.lbl{font-size:12px;fill:#1b1f23}.val{font-size:12px;fill:#1b1f23;font-weight:600}
@media (prefers-color-scheme:dark){body{background:#0f1419;color:#e6edf3}th{background:#1c2430}th,td{border-color:#2d3845}code,pre{background:#1c2430}.lbl,.val{fill:#e6edf3}}
"""


def svg_barchart(title, items, unit, width=720, colors=None):
    """items: list of (label, value) or (label, [v1,v2,...]) for grouped bars. Returns inline SVG."""
    items = [(l, v) for l, v in items if v is not None and (not isinstance(v, list) or any(x is not None for x in v))]
    if not items:
        return ""
    grouped = isinstance(items[0][1], list)
    nseries = len(items[0][1]) if grouped else 1
    allv = [x for _, v in items for x in (v if grouped else [v]) if x is not None]
    vmax = max(allv) or 1
    lab_w, bar_h, gap = 240, 18, 6
    row_h = nseries * bar_h + gap + 6
    height = 30 + len(items) * row_h + 10
    plot_w = width - lab_w - 90
    classes = colors or ["bar", "bar alt", "bar c2", "bar c3"]
    out = [f'<svg class="chart" xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">']
    out.append(f'<text x="0" y="16" class="val">{html.escape(title)}' + (f' <tspan class="lbl">({html.escape(unit)})</tspan>' if unit else "") + "</text>")
    y = 30
    for label, v in items:
        vals = v if grouped else [v]
        out.append(f'<text x="0" y="{y + bar_h * nseries / 2 + 4}" class="lbl">{html.escape(str(label))}</text>')
        for i, x in enumerate(vals):
            if x is None:
                continue
            w = max(1, plot_w * x / vmax)
            by = y + i * bar_h
            out.append(f'<rect class="{classes[i % len(classes)]}" x="{lab_w}" y="{by}" width="{w:.1f}" height="{bar_h - 2}" rx="2"><title>{html.escape(str(label))}: {fmt(x)} {html.escape(unit)}</title></rect>')
            out.append(f'<text x="{lab_w + w + 6:.1f}" y="{by + bar_h - 5}" class="val">{fmt(x)}</text>')
        y += row_h
    out.append("</svg>")
    return "\n".join(out)


def html_table(headers, rows, numeric_from=1):
    h = "".join(f'<th class="{"num" if i >= numeric_from else ""}">{html.escape(str(c))}</th>' for i, c in enumerate(headers))
    body = "".join("<tr>" + "".join(f'<td class="{"num" if i >= numeric_from else ""}">{html.escape(str(c))}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f"<table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>"


def render_html(s):
    run = s["run"]
    label = run.get("label") or s["run_dir"]
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(label)} - bmh-nvme-bench</title><style>{CSS}</style></head><body>"]
    parts.append(f"<h1>Benchmark results: {html.escape(label)}</h1>")
    parts.append(f"<p class='muted'>Profile <code>{html.escape(str(run.get('profile', '?')))}</code>, fio file {html.escape(str(run.get('size', '?')))}, {html.escape(str(run.get('runtime_s', '?')))} s per job. Started {html.escape(str(run.get('started_ist', '?')))} IST on <code>{html.escape(str(run.get('hostname', '?')))}</code>"
                 + (f", provider <b>{html.escape(run['provider'])}</b>" if run.get("provider") and run["provider"] != "unknown" else "") + ".</p>")
    parts.append("<h2>Headline numbers</h2>" + html_table(["Metric", "Value", "Unit"], [(r["metric"], fmt(r["value"]), r["unit"]) for r in s["headline"]]))
    disk = ordered_disk(s["disk"])
    if disk:
        parts.append("<h2>Disk (fio)</h2>")
        parts.append(svg_barchart("IOPS by test", [(n, d.get("iops")) for n, d in disk if n.startswith("4k")], "IOPS"))
        parts.append(svg_barchart("Bandwidth by test", [(n, d.get("bw_mbps")) for n, d in disk if "seq" in n], "MB/s"))
        parts.append(svg_barchart("Latency p50 / p99 / p99.9", [(n, [d.get("p50_us"), d.get("p99_us"), d.get("p999_us")]) for n, d in disk if d.get("p99_us") is not None and ("qd1" in n or "fsync" in n)], "us"))
        rows = []
        for name, d in disk:
            o = d.get("options", {})
            rows.append((name, o.get("rw", "-"), o.get("bs", "-"), o.get("iodepth", "-"), o.get("numjobs", d.get("jobs", "-")), fmt(d.get("iops"), 0), fmt(d.get("bw_mbps"), 1), fmt(d.get("mean_us"), 0), fmt(d.get("p50_us"), 0), fmt(d.get("p99_us"), 0), fmt(d.get("p999_us"), 0)))
        parts.append(html_table(["Test", "rw", "bs", "QD", "jobs", "IOPS", "MB/s", "lat mean us", "p50 us", "p99 us", "p99.9 us"], rows, numeric_from=3))
    cpu, mem = s["cpu"], s["memory"]
    if cpu or mem:
        parts.append("<h2>CPU and memory</h2>")
        items = []
        if cpu.get("single_thread"):
            items.append(("sysbench CPU 1 thread (events/s)", cpu["single_thread"]["events_per_second"]))
        if cpu.get("all_threads"):
            items.append((f"sysbench CPU {cpu['all_threads'].get('threads', '?')} threads (events/s)", cpu["all_threads"]["events_per_second"]))
        parts.append(svg_barchart("CPU", items, "events/s"))
        items = [(f"memory {k} (MiB/s)", v["mib_per_sec"]) for k, v in mem.items()]
        parts.append(svg_barchart("Memory bandwidth", items, "MiB/s"))
    net = s["network"]
    if net["iperf3"] or net["ping"] or net["ttfb"]:
        parts.append("<h2>Network</h2>")
        rows = [(f"iperf3 {k}", fmt(v["mbps"], 0), "Mbit/s") for k, v in net["iperf3"].items()]
        rows += [(f"ping {k} avg", fmt(v["avg_ms"], 2), "ms") for k, v in net["ping"].items()]
        rows += [(f"TTFB {k} median", fmt(v["ttfb_ms_median"], 0), "ms") for k, v in net["ttfb"].items()]
        parts.append(html_table(["Test", "Result", "Unit"], rows))
    pr = s["probe"]
    if pr.get("steal") or pr.get("latency_samples"):
        parts.append("<h2>Noisy-neighbour probe</h2><ul>")
        if pr.get("steal"):
            parts.append(f"<li>CPU steal avg {fmt(pr['steal']['avg_pct'], 2)} %, max {fmt(pr['steal']['max_pct'], 2)} % over {pr['steal']['samples']} s</li>")
        if pr.get("latency_samples"):
            parts.append(f"<li>4k QD1 p99 spread {fmt(pr['latency_p99_spread_x'], 2)}x ({fmt(pr['latency_p99_us_min'], 0)} - {fmt(pr['latency_p99_us_max'], 0)} us)</li>")
            parts.append(svg_barchart("p99 latency per probe sample", [(x["file"], x["p99_us"]) for x in pr["latency_samples"]], "us"))
        parts.append("</ul>")
    sysi = s["system"]
    if sysi:
        c, d = sysi.get("cpu", {}), sysi.get("disk", {})
        parts.append("<h2>System</h2>" + html_table(["Fact", "Value"], [
            ("CPU", f"{c.get('model', '-')} ({c.get('cores', '?')}c/{c.get('threads', '?')}t)"), ("RAM", f"{fmt(sysi.get('ram_mib'), 0)} MiB"), ("Virt", sysi.get("virt", "-")),
            ("Kernel", sysi.get("kernel", "-")), ("Distro", sysi.get("distro", "-")), ("Disk", f"{d.get('device', '-')} {d.get('model', '')} sched={d.get('scheduler', '-')}"), ("FS", f"{d.get('fstype', '-')} on {d.get('mount', '-')}")], numeric_from=99))
    parts.append(f"<h2>Reproduce</h2><pre>git clone https://github.com/geetmangal/bmh-nvme-bench &amp;&amp; cd bmh-nvme-bench\n{html.escape(reproduce_cmd(run))}\npython3 report.py results/&lt;run-dir&gt;/</pre>")
    parts.append(f"<footer>Generated by bmh-nvme-bench report.py at {html.escape(s['generated_ist'])} IST. Maintained by BookMyHost engineering; published results at <a href='https://bookmyhost.com'>bookmyhost.com</a>.</footer></body></html>")
    return "\n".join(parts)


# ----------------------------------------------------------------------------- blog
def render_blog(s, template_path):
    tpl = _read_text(template_path)
    run = s["run"]
    head = md_table(["Metric", "Value", "Unit"], [(r["metric"], fmt(r["value"]), r["unit"]) for r in s["headline"]], ["---", "---:", "---"])
    sysi = s["system"]
    c = sysi.get("cpu", {})
    repl = {
        "{{label}}": run.get("label", s["run_dir"]), "{{provider}}": run.get("provider", "unknown"), "{{profile}}": str(run.get("profile", "")),
        "{{date_ist}}": str(run.get("started_ist", "")), "{{headline_table}}": head, "{{cpu_model}}": c.get("model", ""),
        "{{vcpus}}": str(c.get("threads", "")), "{{ram_gib}}": fmt((sysi.get("ram_mib") or 0) / 1024, 0), "{{virt}}": sysi.get("virt", ""),
        "{{kernel}}": sysi.get("kernel", ""), "{{fstype}}": sysi.get("disk", {}).get("fstype", ""), "{{reproduce_cmd}}": reproduce_cmd(run),
        "{{plan_price_inr}}": str(run.get("plan_price_inr") or ""),
        "{{randread_qd32_iops}}": fmt(s["disk"].get("4k-randread-qd32", {}).get("iops"), 0), "{{randread_qd1_p99_us}}": fmt(s["disk"].get("4k-randread-lat-qd1", {}).get("p99_us"), 0),
        "{{seqread_1m_mbps}}": fmt(s["disk"].get("1m-seqread", {}).get("bw_mbps"), 0), "{{fsync_p99_us}}": fmt(s["disk"].get("4k-fsync-write", {}).get("p99_us"), 0),
    }
    for k, v in repl.items():
        tpl = tpl.replace(k, v)
    return tpl


# ----------------------------------------------------------------------------- compare
COMPARE_METRICS = [
    ("4k-randread-qd1", "iops", "4k randread IOPS QD1", True),
    ("4k-randread-qd32", "iops", "4k randread IOPS QD32", True),
    ("4k-randwrite-qd32", "iops", "4k randwrite IOPS QD32", True),
    ("4k-randrw70-qd32", "iops", "4k randrw 70/30 IOPS QD32", True),
    ("1m-seqread", "bw_mbps", "1M seq read MB/s", True),
    ("1m-seqwrite", "bw_mbps", "1M seq write MB/s", True),
    ("4k-randread-lat-qd1", "p99_us", "4k read p99 us QD1", False),
    ("4k-fsync-write", "p99_us", "fsync write p99 us", False),
    ("cpu", "single_thread", "sysbench CPU 1T events/s", True),
    ("cpu", "all_threads", "sysbench CPU all-T events/s", True),
    ("mem", "read", "memory read MiB/s", True),
    ("net", "download", "iperf3 download Mbit/s", True),
    ("probe", "steal", "CPU steal avg %", False),
]


def metric_value(s, test, key):
    if test == "cpu":
        return (s["cpu"].get(key) or {}).get("events_per_second")
    if test == "mem":
        return (s["memory"].get(key) or {}).get("mib_per_sec")
    if test == "net":
        return (s["network"]["iperf3"].get(key) or {}).get("mbps")
    if test == "probe":
        return (s["probe"].get("steal") or {}).get("avg_pct")
    return (s["disk"].get(test) or {}).get(key)


def build_compare(summaries, labels):
    rows = []
    for test, key, title, higher_better in COMPARE_METRICS:
        vals = [metric_value(s, test, key) for s in summaries]
        if all(v is None for v in vals):
            continue
        base = vals[0]
        deltas = []
        for v in vals:
            if v is None or base in (None, 0) or v == 0:
                deltas.append(None)
            else:
                deltas.append(round(v / base if higher_better else base / v, 2))
        best = None
        cand = [(v, i) for i, v in enumerate(vals) if v is not None]
        if cand:
            best = (max if higher_better else min)(cand)[1]
        rows.append({"metric": title, "test": test, "key": key, "higher_is_better": higher_better, "values": vals, "x_vs_first": deltas, "best_index": best})
    price_rows = []
    for s in summaries:
        price = s["run"].get("plan_price_inr")
        iops = metric_value(s, "4k-randread-qd32", "iops")
        wiops = metric_value(s, "4k-randwrite-qd32", "iops")
        price_rows.append({
            "plan_price_inr": price,
            "inr_per_10k_read_iops": round(price / (iops / 10000.0), 2) if price and iops else None,
            "inr_per_10k_write_iops": round(price / (wiops / 10000.0), 2) if price and wiops else None,
        })
    return {"schema_version": SCHEMA_VERSION, "generated_ist": datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S%z"), "labels": labels,
            "runs": [{"label": l, "run_dir": s["run_dir"], "provider": s["run"].get("provider"), "profile": s["run"].get("profile"), "cpu": s["system"].get("cpu", {}).get("model"), "vcpus": s["system"].get("cpu", {}).get("threads"), "ram_mib": s["system"].get("ram_mib")} for l, s in zip(labels, summaries)],
            "metrics": rows, "value_for_money": price_rows}


def render_compare_md(c):
    labels = c["labels"]
    L = ["# Comparison: " + " vs ".join(labels), "", "*x = relative to the first column (" + labels[0] + "); for latency and steal, higher x means lower (better) values. Best value per row in bold.*", ""]
    hdr = ["Metric"] + labels + [f"x ({l})" for l in labels[1:]]
    rows = []
    for m in c["metrics"]:
        cells = []
        for i, v in enumerate(m["values"]):
            t = fmt(v)
            cells.append(f"**{t}**" if i == m["best_index"] and len(labels) > 1 else t)
        xs = [f"{fmt(d, 2)}x" if d is not None else "-" for d in m["x_vs_first"][1:]]
        rows.append([m["metric"] + ("" if m["higher_is_better"] else " (lower is better)"), *cells, *xs])
    L.append(md_table(hdr, rows, ["---"] + ["---:"] * (len(hdr) - 1)))
    if any(p["plan_price_inr"] for p in c["value_for_money"]):
        L += ["", "## Value for money", ""]
        L.append(md_table(["Run", "Plan INR/month", "INR per 10k read IOPS (QD32)", "INR per 10k write IOPS (QD32)"],
                          [(l, fmt(p["plan_price_inr"], 0), fmt(p["inr_per_10k_read_iops"], 2), fmt(p["inr_per_10k_write_iops"], 2)) for l, p in zip(labels, c["value_for_money"])],
                          ["---", "---:", "---:", "---:"]))
    L += ["", "## Systems", ""]
    L.append(md_table(["Run", "Provider", "Profile", "CPU", "vCPUs", "RAM MiB"], [(r["label"], r.get("provider") or "-", r.get("profile") or "-", r.get("cpu") or "-", fmt(r.get("vcpus")), fmt(r.get("ram_mib"), 0)) for r in c["runs"]]))
    L += ["", f"*Generated by bmh-nvme-bench report.py compare at {c['generated_ist']} IST. Methodology: docs/methodology.md. Published results: https://bookmyhost.com*", ""]
    return "\n".join(L)


def render_compare_svg(c):
    labels = c["labels"]
    items = []
    for m in c["metrics"]:
        if m["test"] in ("4k-randread-qd1", "4k-randread-qd32", "4k-randwrite-qd32", "1m-seqread", "1m-seqwrite", "cpu"):
            vmax = max([v for v in m["values"] if v is not None] or [1]) or 1
            items.append((m["metric"], [round(v / vmax * 100, 1) if v is not None else None for v in m["values"]]))
    svg = svg_barchart("Relative performance, best = 100  [" + " / ".join(labels) + "]", items, "% of best", width=820)
    return f"<?xml version='1.0' encoding='UTF-8'?>\n" + svg.replace('<svg class="chart" ', '<svg style="font-family:sans-serif" ').replace("<rect class=\"bar\"", "<rect fill=\"#0b5fff\"").replace("<rect class=\"bar alt\"", "<rect fill=\"#f28c28\"").replace("<rect class=\"bar c2\"", "<rect fill=\"#2bb673\"").replace("<rect class=\"bar c3\"", "<rect fill=\"#9b59b6\"").replace('class="lbl"', 'font-size="12"').replace('class="val"', 'font-size="12" font-weight="600"')


def render_compare_html(c):
    labels = c["labels"]
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Comparison - bmh-nvme-bench</title><style>{CSS}</style></head><body>"]
    parts.append("<h1>Comparison: " + html.escape(" vs ".join(labels)) + "</h1>")
    hdr = ["Metric"] + labels + [f"x ({l})" for l in labels[1:]]
    rows = []
    for m in c["metrics"]:
        rows.append([m["metric"] + ("" if m["higher_is_better"] else " (lower is better)"), *[fmt(v) for v in m["values"]], *[f"{fmt(d, 2)}x" if d is not None else "-" for d in m["x_vs_first"][1:]]])
    parts.append(html_table(hdr, rows))
    for m in c["metrics"]:
        if m["test"] in ("4k-randread-qd32", "4k-randwrite-qd32", "1m-seqread", "4k-randread-lat-qd1", "4k-fsync-write", "cpu"):
            parts.append(svg_barchart(m["metric"], list(zip(labels, m["values"])), ""))
    if any(p["plan_price_inr"] for p in c["value_for_money"]):
        parts.append("<h2>Value for money</h2>" + html_table(["Run", "Plan INR/month", "INR per 10k read IOPS", "INR per 10k write IOPS"],
                     [(l, fmt(p["plan_price_inr"], 0), fmt(p["inr_per_10k_read_iops"], 2), fmt(p["inr_per_10k_write_iops"], 2)) for l, p in zip(labels, c["value_for_money"])]))
    parts.append(f"<footer>Generated by bmh-nvme-bench report.py compare at {html.escape(c['generated_ist'])} IST. <a href='https://bookmyhost.com'>bookmyhost.com</a></footer></body></html>")
    return "\n".join(parts)


# ----------------------------------------------------------------------------- cli
def write_text(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def cmd_report(args):
    try:
        s = build_summary(args.run_dir)
    except FileNotFoundError:
        print(f"error: run dir not found: {args.run_dir}", file=sys.stderr)
        return 2
    except ParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2 if "no parsable" in str(exc) else 3
    out = args.out or args.run_dir
    os.makedirs(out, exist_ok=True)
    write_text(os.path.join(out, "summary.json"), json.dumps(s, indent=2))
    if not args.json_only:
        write_text(os.path.join(out, "summary.md"), render_md(s))
        write_text(os.path.join(out, "summary.html"), render_html(s))
        write_csv(s, os.path.join(out, "summary.csv"))
        if args.blog:
            tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "blog-post-template.md")
            if os.path.exists(tpl):
                write_text(os.path.join(out, "blog.md"), render_blog(s, tpl))
    if not args.quiet:
        print(f"summary written to {out}/summary.{{json{',md,html,csv' if not args.json_only else ''}}}")
        for r in s["headline"]:
            print(f"  {r['metric']:<45} {fmt(r['value']):>14} {r['unit']}")
    return 0


def cmd_compare(args):
    if len(args.run_dirs) < 2:
        print("error: compare needs at least two run dirs", file=sys.stderr)
        return 1
    summaries = []
    for d in args.run_dirs:
        try:
            med = os.path.join(d, "median.json")
            # a `report.py median` output dir compares like a single run
            summaries.append(_load_json(med) if os.path.isfile(med) else build_summary(d))
        except FileNotFoundError:
            print(f"error: run dir not found: {d}", file=sys.stderr)
            return 2
        except ParseError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 3
    labels =[l.strip() for l in args.labels.split(",")] if args.labels else [s["run"].get("label") or s["run_dir"] for s in summaries]
    if len(labels) != len(summaries):
        print("error: --labels count must match the number of run dirs", file=sys.stderr)
        return 1
    c = build_compare(summaries, labels)
    out = args.out or "compare"
    os.makedirs(out, exist_ok=True)
    write_text(os.path.join(out, "compare.json"), json.dumps(c, indent=2))
    if not args.json_only:
        write_text(os.path.join(out, "compare.md"), render_compare_md(c))
        write_text(os.path.join(out, "compare.html"), render_compare_html(c))
        write_text(os.path.join(out, "compare.svg"), render_compare_svg(c))
    if not args.quiet:
        print(render_compare_md(c) if not args.json_only else f"compare.json written to {out}/")
    return 0


# ----------------------------------------------------------------------------- median across runs
def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _median_merge(vals):
    """Median of every numeric leaf present in all inputs; non-numeric leaves come from the first."""
    first = vals[0]
    if all(isinstance(v, dict) for v in vals):
        keys = [k for k in first if all(k in v for v in vals)]
        return {k: _median_merge([v[k] for v in vals]) for k in keys}
    if all(_is_num(v) for v in vals):
        m = statistics.median(vals)
        return round(m, 3) if isinstance(m, float) else m
    return first


def build_median(summaries):
    m = _median_merge(summaries)
    m["generated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    m["generated_ist"] = datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S%z")
    m["run_dir"] = f"median-of-{len(summaries)}-runs"
    m["run"] = dict(summaries[0]["run"])
    m["run"]["repeats"] = len(summaries)
    m["run"]["median_of_runs"] = [s["run_dir"] for s in summaries]
    m["headline"] = headline_rows(m)
    return m


def cmd_median(args):
    if len(args.run_dirs) < 2:
        print("error: median needs at least two run dirs", file=sys.stderr)
        return 1
    summaries = []
    for d in args.run_dirs:
        try:
            summaries.append(build_summary(d))
        except FileNotFoundError:
            print(f"error: run dir not found: {d}", file=sys.stderr)
            return 2
        except ParseError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 3
    m = build_median(summaries)
    out = args.out
    os.makedirs(out, exist_ok=True)
    write_text(os.path.join(out, "median.json"), json.dumps(m, indent=2))
    c = build_compare(summaries, [f"run {i + 1}" for i in range(len(summaries))])
    write_text(os.path.join(out, "runs-compare.json"), json.dumps(c, indent=2))
    if not args.json_only:
        write_text(os.path.join(out, "median.md"), render_md(m))
        write_text(os.path.join(out, "median.html"), render_html(m))
        write_csv(m, os.path.join(out, "median.csv"))
        write_text(os.path.join(out, "runs-compare.md"), render_compare_md(c))
    if not args.quiet:
        print(f"median of {len(summaries)} runs written to {out}/")
        for r in m["headline"]:
            print(f"  {r['metric']:<45} {fmt(r['value']):>14} {r['unit']}")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="report.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    pr = sub.add_parser("report", help="render one run (default when the first arg is a directory)")
    pr.add_argument("run_dir")
    pr.add_argument("--out", help="write outputs here instead of inside the run dir")
    pr.add_argument("--json-only", action="store_true")
    pr.add_argument("--blog", action="store_true", help="also fill docs/blog-post-template.md into blog.md")
    pr.add_argument("--quiet", "-q", action="store_true")
    pc = sub.add_parser("compare", help="compare two or more runs")
    pc.add_argument("run_dirs", nargs="+")
    pc.add_argument("--labels", help="comma separated column labels")
    pc.add_argument("--out", help="output dir (default ./compare)")
    pc.add_argument("--json-only", action="store_true")
    pc.add_argument("--quiet", "-q", action="store_true")
    pm = sub.add_parser("median", help="median of repeated runs (separate run dirs) into one summary")
    pm.add_argument("run_dirs", nargs="+")
    pm.add_argument("--out", required=True, help="output dir")
    pm.add_argument("--json-only", action="store_true")
    pm.add_argument("--quiet", "-q", action="store_true")
    if argv and argv[0] not in ("report", "compare", "median", "-h", "--help"):
        argv.insert(0, "report")
    args = ap.parse_args(argv)
    if args.cmd == "compare":
        return cmd_compare(args)
    if args.cmd == "median":
        return cmd_median(args)
    if args.cmd == "report":
        return cmd_report(args)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
