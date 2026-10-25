#!/usr/bin/env python3
"""Build the two fixture run directories (run-a, run-b) in the layout bench.sh writes.

run-a uses the hand-written fixtures where one exists (fio_randread.json, fio_seq.json,
sysbench_*.txt, iperf3.json, ping.txt, sysinfo.json) and synthesises the remaining fio jobs.
run-b is a slower, cheaper "competitor" built by scaling run-a. Re-run with `make fixtures`.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _zero_dir():
    return {"io_bytes": 0, "io_kbytes": 0, "bw_bytes": 0, "bw": 0, "iops": 0.0, "runtime": 0, "total_ios": 0, "short_ios": 0, "drop_ios": 0,
            "slat_ns": {"min": 0, "max": 0, "mean": 0.0, "stddev": 0.0, "N": 0}, "clat_ns": {"min": 0, "max": 0, "mean": 0.0, "stddev": 0.0, "N": 0},
            "lat_ns": {"min": 0, "max": 0, "mean": 0.0, "stddev": 0.0, "N": 0}}


def _dir(iops, bs_bytes, p50_us, p99_us, p999_us, runtime_s=60, lat_pct=False):
    ios = int(iops * runtime_s)
    mean_ns = int(p50_us * 1000 * 1.08)
    pct = {"1.000000": int(p50_us * 450), "50.000000": int(p50_us * 1000), "90.000000": int(p50_us * 1500), "95.000000": int((p50_us + p99_us) / 2 * 1000),
           "99.000000": int(p99_us * 1000), "99.900000": int(p999_us * 1000), "99.990000": int(p999_us * 2200)}
    d = {"io_bytes": ios * bs_bytes, "io_kbytes": ios * bs_bytes // 1024, "bw_bytes": int(iops * bs_bytes), "bw": int(iops * bs_bytes / 1024), "iops": round(iops, 2),
         "runtime": runtime_s * 1000 + 1, "total_ios": ios, "short_ios": 0, "drop_ios": 0,
         "slat_ns": {"min": 1200, "max": 150000, "mean": 2500.0, "stddev": 900.0, "N": ios},
         "clat_ns": {"min": int(p50_us * 400), "max": int(p999_us * 4000), "mean": float(mean_ns), "stddev": float(p50_us * 300), "N": ios, "percentile": pct},
         "lat_ns": {"min": int(p50_us * 410), "max": int(p999_us * 4010), "mean": float(mean_ns + 2500), "stddev": float(p50_us * 300), "N": ios}}
    if lat_pct:
        d["lat_ns"]["percentile"] = {k: v + 2500 for k, v in pct.items()}
    return d


def make_fio(name, rw, bs, iodepth, numjobs, read=None, write=None, sync=None, runtime=60):
    """read/write: (iops, p50_us, p99_us, p999_us); sync: (p50_us, p99_us, p999_us)."""
    bs_bytes = {"4k": 4096, "64k": 65536, "1M": 1048576}[bs]
    job = {"jobname": name, "groupid": 0, "error": 0, "eta": 0, "elapsed": runtime + 3,
           "job options": {"rw": rw, "bs": bs, "iodepth": str(iodepth), "numjobs": str(numjobs)},
           "read": _dir(*read[:1], bs_bytes, *read[1:], runtime_s=runtime, lat_pct="lat" in name) if read else _zero_dir(),
           "write": _dir(*write[:1], bs_bytes, *write[1:], runtime_s=runtime, lat_pct=sync is not None) if write else _zero_dir(),
           "trim": _zero_dir(), "job_runtime": runtime * 1000, "usr_cpu": 2.1, "sys_cpu": 9.3, "ctx": 100000, "majf": 0, "minf": 30}
    if rw == "randrw":
        job["job options"]["rwmixread"] = "70"
    if sync:
        job["job options"]["fsync"] = "1"
        ios = job["write"]["total_ios"]
        job["sync"] = {"total_ios": ios, "lat_ns": {"min": int(sync[0] * 500), "max": int(sync[2] * 5000), "mean": float(sync[0] * 1100), "stddev": float(sync[0] * 300), "N": ios,
                       "percentile": {"50.000000": int(sync[0] * 1000), "90.000000": int(sync[0] * 1400), "99.000000": int(sync[1] * 1000), "99.900000": int(sync[2] * 1000)}}}
    else:
        job["sync"] = {"total_ios": 0, "lat_ns": {"min": 0, "max": 0, "mean": 0.0, "stddev": 0.0, "N": 0}}
    return {"fio version": "fio-3.36", "timestamp": 1792314000, "time": "Sat Oct 25 14:30:00 2026",
            "global options": {"ioengine": "libaio", "direct": "1", "directory": "/root/bench-tmp", "filename": "bench.file", "size": "4G", "time_based": "1", "runtime": str(runtime), "group_reporting": "1"},
            "jobs": [job], "disk_util": [{"name": "vda", "util": 99.5}]}


# run-a: BookMyHost-like NVMe KVM VM, 4 vCPU / 8 GiB
RUN_A = {
    "label": "bmh-nvme-noida-vm-4c8g", "provider": "bookmyhost", "price": 1499, "hostname": "bmh-noida-vm-4c8g",
    "fio": {
        "4k-randread-qd1": ("randread", "4k", 1, 1, (11850.4, 78.0, 142.0, 310.0), None, None),
        "4k-randwrite-qd1": ("randwrite", "4k", 1, 1, None, (9120.7, 102.0, 190.0, 420.0), None),
        "4k-randwrite-qd32": ("randwrite", "4k", 32, 4, None, (88420.5, 1380.0, 2900.0, 6100.0), None),
        "4k-randrw70-qd32": ("randrw", "4k", 32, 4, (71230.2, 1620.0, 3400.0, 7200.0), (30510.9, 1700.0, 3600.0, 7900.0), None),
        "64k-seqread": ("read", "64k", 16, 2, (28900.3, 1050.0, 1900.0, 3800.0), None, None),
        "64k-seqwrite": ("write", "64k", 16, 2, (0, 0, 0, 0), (21500.6, 1420.0, 2600.0, 5100.0), None),
        "1m-seqwrite": ("write", "1M", 16, 2, None, (1710.4, 18200.0, 29000.0, 46000.0), None),
        "4k-randread-lat-qd1": ("randread", "4k", 1, 1, (11790.1, 79.0, 145.0, 322.0), None, None),
        "4k-fsync-write": ("write", "4k", 1, 1, None, (2980.2, 120.0, 210.0, 480.0), (310.0, 620.0, 1400.0)),
    },
    "cpu_nt_scale": 3.82, "threads": 4, "mem_write_scale": 0.78,
    "probe_steal": [0.0, 0.12, 0.0, 0.31, 0.0, 0.0, 0.08, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.11, 0.0, 0.0, 0.0, 0.0, 0.0],
    "probe_lat_p99": [148.0, 151.0, 143.0],
    "ttfb": {"bookmyhost.com": [0.112, 0.098, 0.101, 0.105, 0.097], "www.google.com": [0.061, 0.058, 0.064, 0.060, 0.059]},
}
# run-b: generic competitor on shared SATA-ish SSD, more steal
SCALE_B = {"iops": 0.42, "lat": 2.6, "bw": 0.55, "cpu": 0.81, "mem": 0.9, "net": 0.31, "steal": 9.5}


def write_run(dirpath, spec, scale=None):
    sc = scale or {"iops": 1, "lat": 1, "bw": 1, "cpu": 1, "mem": 1, "net": 1, "steal": 1}
    for sub in ("fio", "sysbench", "net", "probe", "extras"):
        os.makedirs(os.path.join(dirpath, sub), exist_ok=True)

    def s_rw(t, seq=False):
        if t is None:
            return None
        if t[0] == 0:
            return None
        f = sc["bw"] if seq else sc["iops"]
        return (t[0] * f, t[1] * sc["lat"], t[2] * sc["lat"], t[3] * sc["lat"])

    for name, (rw, bs, qd, nj, rd, wr, sy) in spec["fio"].items():
        seq = "seq" in name
        syn = tuple(x * sc["lat"] for x in sy) if sy else None
        json.dump(make_fio(name, rw, bs, qd, nj, s_rw(rd, seq), s_rw(wr, seq), syn), open(os.path.join(dirpath, "fio", f"{name}.json"), "w"), indent=1)
    if scale is None:
        shutil.copy(os.path.join(HERE, "fio_randread.json"), os.path.join(dirpath, "fio", "4k-randread-qd32.json"))
        shutil.copy(os.path.join(HERE, "fio_seq.json"), os.path.join(dirpath, "fio", "1m-seqread.json"))
    else:
        json.dump(make_fio("4k-randread-qd32", "randread", "4k", 32, 4, (127498.17 * sc["iops"], 481.3 * sc["lat"], 1187.8 * sc["lat"], 2146.3 * sc["lat"])), open(os.path.join(dirpath, "fio", "4k-randread-qd32.json"), "w"), indent=1)
        json.dump(make_fio("1m-seqread", "read", "1M", 16, 2, (2252.78 * sc["bw"], 13631.5 * sc["lat"], 25165.8 * sc["lat"], 41943.0 * sc["lat"])), open(os.path.join(dirpath, "fio", "1m-seqread.json"), "w"), indent=1)
    json.dump(make_fio("prefill", "write", "1M", 16, 1, None, (1500.0, 20000.0, 30000.0, 40000.0)), open(os.path.join(dirpath, "fio", "prefill.json"), "w"), indent=1)

    cpu = open(os.path.join(HERE, "sysbench_cpu.txt")).read()
    eps1 = 1187.42 * sc["cpu"]
    open(os.path.join(dirpath, "sysbench", "cpu-1t.txt"), "w").write(cpu.replace("1187.42", f"{eps1:.2f}"))
    open(os.path.join(dirpath, "sysbench", "cpu-nt.txt"), "w").write(cpu.replace("1187.42", f"{eps1 * spec['cpu_nt_scale']:.2f}").replace("Number of threads: 1", f"Number of threads: {spec['threads']}"))
    mem = open(os.path.join(HERE, "sysbench_mem.txt")).read()
    open(os.path.join(dirpath, "sysbench", "mem-read.txt"), "w").write(mem.replace("10968.52", f"{10968.52 * sc['mem']:.2f}"))
    open(os.path.join(dirpath, "sysbench", "mem-write.txt"), "w").write(mem.replace("10968.52", f"{10968.52 * sc['mem'] * spec['mem_write_scale']:.2f}").replace("operation: read", "operation: write"))

    ip = json.load(open(os.path.join(HERE, "iperf3.json")))
    for key in ("sum_sent", "sum_received"):
        ip["end"][key]["bits_per_second"] = round(ip["end"][key]["bits_per_second"] * sc["net"], 1)
    json.dump(ip, open(os.path.join(dirpath, "net", "iperf3-down.json"), "w"), indent=1)
    ip["start"]["test_start"]["reverse"] = 0
    for key in ("sum_sent", "sum_received"):
        ip["end"][key]["bits_per_second"] = round(ip["end"][key]["bits_per_second"] * 0.97, 1)
    json.dump(ip, open(os.path.join(dirpath, "net", "iperf3-up.json"), "w"), indent=1)
    shutil.copy(os.path.join(HERE, "ping.txt"), os.path.join(dirpath, "net", "ping-1.1.1.1.txt"))
    for host, vals in spec["ttfb"].items():
        with open(os.path.join(dirpath, "net", f"curl-ttfb-{host}.txt"), "w") as fh:
            for v in vals:
                fh.write(f"https://{host}/ ttfb={v * sc['lat'] ** 0.3:.6f} connect=0.004512 tls=0.021340 http=200\n")

    with open(os.path.join(dirpath, "probe", "steal.csv"), "w") as fh:
        fh.write("t,steal_pct,idle_pct\n")
        for i, v in enumerate(spec["probe_steal"], 1):
            fh.write(f"{i},{v * sc['steal']:.3f},{97.0 - v * sc['steal']:.3f}\n")
    for i, p99 in enumerate(spec["probe_lat_p99"], 1):
        p99 *= sc["lat"] * (1 + 0.15 * (i % 2) * (sc["steal"] > 1))
        json.dump(make_fio("probe", "randread", "4k", 1, 1, (10800.0 * sc["iops"], p99 * 0.55, p99, p99 * 2.2), runtime=5), open(os.path.join(dirpath, "probe", f"lat-{i:02d}.json"), "w"), indent=1)

    open(os.path.join(dirpath, "extras", "pyloop.txt"), "w").write(f"pyloop_seconds={1.92 / sc['cpu']:.3f} score={5.21 * sc['cpu']:.2f} Mops/s\n")
    open(os.path.join(dirpath, "extras", "openssl.txt"), "w").write(
        "The 'numbers' are in 1000s of bytes per second processed.\ntype             16 bytes     64 bytes    256 bytes   1024 bytes   8192 bytes  16384 bytes\n"
        f"AES-256-GCM     612345.67k  1823456.78k  3712345.12k  4812345.44k  5212345.00k  {5290000.0 * sc['cpu']:.2f}k\n")

    sysinfo = json.load(open(os.path.join(HERE, "sysinfo.json")))
    sysinfo["hostname"] = spec["hostname"]
    if scale is not None:
        sysinfo["cpu"]["model"] = "Intel(R) Xeon(R) Gold 6248R CPU @ 3.00GHz"
        sysinfo["disk"]["model"] = "QEMU HARDDISK"
        sysinfo["steal_baseline_pct"] = 1.9
    json.dump(sysinfo, open(os.path.join(dirpath, "sysinfo.json"), "w"), indent=2)
    run = {"bench_version": "0.1.0", "profile": "standard", "label": spec["label"], "provider": spec["provider"], "plan_price_inr": spec["price"], "size": "4G", "runtime_s": 60,
           "target": "/root/bench-tmp", "repeats": 1, "numjobs_rand": 4, "numjobs_seq": 2, "qd_seq": 16, "probe_secs": 60,
           "started_ist": "2026-10-25T14:30:00+0530", "started_utc": "2026-10-25T09:00:00Z", "finished_ist": "2026-10-25T14:58:12+0530", "finished_utc": "2026-10-25T09:28:12Z",
           "hostname": spec["hostname"], "skip": [], "iperf_server": "192.0.2.9", "dry_run": False,
           "tools": {"fio": "fio-3.36", "sysbench": "sysbench 1.0.20", "iperf3": "iperf 3.16"}}
    json.dump(run, open(os.path.join(dirpath, "run.json"), "w"), indent=2)


def main(out=None):
    out = out or HERE
    write_run(os.path.join(out, "run-a"), RUN_A)
    run_b = dict(RUN_A, label="competitor-x-vm-4c8g", provider="competitor-x", price=1299, hostname="vm-competitor-x")
    write_run(os.path.join(out, "run-b"), run_b, SCALE_B)
    for d in ("run-a", "run-b"):
        for root, _, files in os.walk(os.path.join(out, d)):
            for f in files:
                if os.path.getsize(os.path.join(root, f)) == 0:
                    raise SystemExit(f"empty fixture file: {os.path.join(root, f)}")
    print(f"fixture runs written: {out}/run-a, {out}/run-b")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
