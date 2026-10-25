# summary.json schema (version 1)

`report.py RUN_DIR` writes `summary.json`. Units are in the key name: latencies are microseconds (`_us`), bandwidth is decimal MB/s (`bw_mbps` = bytes/s / 1e6), and network figures are Mbit/s. Missing values are `null`; skipped sections are empty objects.

```jsonc
{
  "schema_version": 1,
  "generated_utc": "2026-10-25T09:30:00Z",
  "generated_ist": "2026-10-25T15:00:00+0530",
  "run_dir": "bmh-nvme-noida-vm-4c8g-20261025-143000",
  "run": { /* run.json from bench.sh, copied verbatim */
    "bench_version": "0.1.0", "profile": "standard", "label": "...", "provider": "bookmyhost",
    "plan_price_inr": 1499, "size": "4G", "runtime_s": 60, "repeats": 1,
    "numjobs_rand": 4, "numjobs_seq": 2, "qd_seq": 16, "probe_secs": 60,
    "started_ist": "...", "started_utc": "...", "finished_ist": "...", "finished_utc": "...",
    "hostname": "...", "skip": [], "iperf_server": "...", "dry_run": false,
    "tools": { "fio": "fio-3.36", "sysbench": "sysbench 1.0.20", "iperf3": "iperf 3.16" }
  },
  "system": { /* sysinfo.json from bench.sh, copied verbatim */
    "cpu": { "model": "...", "cores": 4, "threads": 4, "sockets": 1, "mhz": 3250.0, "flags": ["..."] },
    "ram_mib": 7936, "kernel": "...", "virt": "kvm", "distro": "...", "hostname": "...",
    "disk": { "device": "/dev/vda1", "model": "", "scheduler": "[none] mq-deadline", "rotational": false, "fstype": "ext4", "mount": "/" },
    "steal_baseline_pct": 0.12
  },
  "disk": {
    "<test name>": {                  // e.g. "4k-randread-qd32"; one entry per fio/<name>.json (+ .rN repeats)
      "name": "4k-randread-qd32",
      "repeats": 1,                    // files merged; metrics are the median across repeats
      "primary": "read",               // direction the top-level metrics come from
      "jobs": 2,                       // fio job entries in the file
      "options": { "rw": "randread", "bs": "4k", "iodepth": "32", "numjobs": "2" },
      "read":  { "iops": 0, "bw_mbps": 0, "lat_us": { "mean": 0, "p50": 0, "p99": 0, "p999": 0 } },
      "write": { "iops": 0, "bw_mbps": 0, "lat_us": { "mean": 0, "p50": 0, "p99": 0, "p999": 0 } },
      "sync":  { "lat_us": { "mean": 0, "p50": 0, "p99": 0, "p999": 0 } },   // fsync tests only
      "iops": 0, "bw_mbps": 0,         // primary direction; randrw = read + write
      "mean_us": 0, "p50_us": 0, "p99_us": 0, "p999_us": 0   // primary direction; fsync tests use "sync"
    }
  },
  "cpu": {
    "single_thread": { "events_per_second": 1187.42, "threads": 1, "events": 11876, "lat_p95_ms": 0.86 },
    "all_threads":   { "events_per_second": 4536.0, "threads": 4 },
    "scaling": 3.82                    // all_threads / single_thread
  },
  "memory": {
    "read":  { "mib_per_sec": 10968.52, "ops_per_sec": 10968.52, "block_kib": 1024 },
    "write": { "mib_per_sec": 8555.45, "ops_per_sec": 8555.45, "block_kib": 1024 }
  },
  "network": {
    "iperf3": {
      "download": { "mbps": 0, "sent_mbps": 0, "received_mbps": 0, "retransmits": 0, "streams": 4, "duration_s": 10, "reverse": true },
      "upload":   { "same shape": "reverse false" }
    },
    "ping": { "<host>": { "host": "1.1.1.1", "ip": "1.1.1.1", "sent": 20, "received": 20, "loss_pct": 0, "min_ms": 0, "avg_ms": 0, "max_ms": 0, "mdev_ms": 0 } },
    "ttfb": { "<host>": { "samples": 5, "ttfb_ms_min": 0, "ttfb_ms_median": 0, "http_codes": ["200"] } }
  },
  "probe": {
    "steal": { "samples": 60, "avg_pct": 0, "max_pct": 0, "p95_pct": 0 },
    "latency_samples": [ { "file": "lat-01.json", "p50_us": 0, "p99_us": 0, "iops": 0 } ],
    "latency_p99_us_min": 0, "latency_p99_us_max": 0, "latency_p99_spread_x": 1.05
  },
  "extras": { "pyloop_mops": 5.21, "openssl_aes256gcm_16k_mbps": 5290.0 },
  "headline": [ { "metric": "4k random read IOPS (QD32)", "value": 127498.2, "unit": "IOPS", "test": "4k-randread-qd32", "key": "iops" } ]
}
```

## compare.json

`report.py compare A/ B/ --labels a,b --out DIR` writes `compare.json`:

- `labels`: the column labels. `runs[]`: label, run_dir, provider, profile, cpu, vcpus, ram_mib.
- `metrics[]`: `metric`, `test`, `key`, `higher_is_better`, `values[]` (one per run), `x_vs_first[]` (ratio against the first run, inverted for lower-is-better metrics so that above 1 always means better), and `best_index`.
- `value_for_money[]`: `plan_price_inr`, `inr_per_10k_read_iops`, `inr_per_10k_write_iops` (price / (QD32 IOPS / 10 000)). These are `null` when the run has no `--plan-price-inr`.

## CSV

`summary.csv` has the columns `label,section,test,metric,value,unit`, one row per number, ready for spreadsheets or `pandas.read_csv`.

## Exit codes

`0` ok, `1` usage error, `2` run dir missing or no parsable data, `3` a required file failed to parse.
