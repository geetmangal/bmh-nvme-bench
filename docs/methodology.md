# Methodology

How bmh-nvme-bench measures, and how to read and publish the numbers fairly.

## What each test measures

| Test | fio / tool settings | What it tells you |
| --- | --- | --- |
| `4k-randread-qd1` | randread, 4k, iodepth 1, 1 job | Latency-bound read speed that a single synchronous thread sees (most web apps, a `SELECT` on a cold page). |
| `4k-randread-qd32` | randread, 4k, iodepth 32, N jobs | Parallel random read throughput. This is closest to the "IOPS" figure on spec sheets. |
| `4k-randread-qd64` (full) | iodepth 64 | Where the device or the hypervisor queue saturates. |
| `4k-randwrite-qd1` / `qd32` | randwrite, 4k | The write path, including any host-side write cache or replication cost. |
| `4k-randrw70-qd32` | randrw, rwmixread 70 | OLTP-style mixed load. The IOPS reported is read + write. |
| `64k-seq*`, `1m-seq*` | read / write, 64k and 1M | Streaming throughput: backups, media, log shipping, restores. |
| `4k-randread-lat-qd1` | randread QD1 with `lat_percentiles` | Clean p50/p99/p99.9 latency. This is the number to quote for "how fast does one IO return". |
| `4k-fsync-write` | 4k write, `fsync=1` | The cost of a durable commit (PostgreSQL, MySQL, etcd). Reported from fio's `sync` latency block. |
| sysbench cpu | `--cpu-max-prime=20000`, 1 thread and all threads | Integer CPU speed and how well vCPUs scale. Scaling well below the vCPU count hints at shared or oversold threads. |
| sysbench memory | 1 MiB blocks, read and write | Memory bandwidth for one thread. |
| openssl, pyloop | `openssl speed -evp aes-256-gcm`, a pure-Python loop | Sanity scores: is AES-NI present, how fast is the interpreter. |
| iperf3 | 4 streams, 10 s, both directions | TCP throughput to a server you choose. |
| ping, curl TTFB | 20 pings, 5 TTFB samples | Latency to 1.1.1.1 and your iperf server, plus HTTPS TTFB to public sites. |
| noisy-neighbour probe | `/proc/stat` steal every 1 s, fio 4k QD1 every 10 s | Whether performance stays stable over a minute, or a neighbour is stealing CPU or disk. |

## Why `direct=1`

`--direct=1` opens the file with `O_DIRECT`, which bypasses the guest page cache. Without it, a 4 GiB file on an 8 GiB VM is mostly served from RAM, so you benchmark memory, not NVMe. It does **not** bypass the hypervisor cache: if the host uses `cache=writeback`, reads can still hit host RAM. So the test file should be larger than any plausible host cache share (use `--size 8G` or more on hosts you do not control), and we report QD1 latency, which is hard to fake.

## Why QD1 and QD32

Queue depth is the number of IOs in flight. QD1 measures latency: one IO, wait for it, then the next. Most real applications (a PHP request, a single DB connection) behave like QD1 to QD4. QD32 with several jobs measures how much parallel work the storage stack absorbs, and that is where NVMe shines. A provider can look good at QD32 and poor at QD1 (network storage, Ceph), or the other way round (local NVMe capped by an IOPS limit). Publish both.

## How to read p99 and p99.9

p99 means 99 % of IOs completed within this time, so 1 in 100 took longer. For a page that issues 100 IOs, p99 is roughly what every page load pays once. p99.9 shows rare stalls: garbage collection on the SSD, host contention, replication hiccups. Mean latency hides these, so always quote a percentile. fio reports percentiles in nanoseconds and `report.py` converts them to microseconds. With several jobs, `report.py` takes the **worst job's** percentile (the conservative choice), sums IOPS and bandwidth, and IO-weights the mean.

## VM caveats

- **Steal time** is CPU time the hypervisor gave to someone else. `sysinfo.json` stores a 5 s baseline and the probe records steal every second. Above about 2 % sustained, the CPU numbers do not represent the plan.
- **Ballooning / memory overcommit**: the guest may see less RAM than advertised, or swap. Check `ram_mib` in `sysinfo.json` against the plan.
- **Burst credits and IOPS caps**: some clouds give burst IOPS for a few minutes, then throttle. Use the standard or full profile (60-120 s per job), and look at the probe spread.
- **Thin provisioning / zeroes**: blocks that were never written can read back at memory speed. bench.sh pre-fills the test file with real data before any read test.
- **Filesystem**: results on ext4, xfs and zfs differ. `sysinfo.json` records the fs type and the I/O scheduler. Test the filesystem you will actually run.

## Keeping runs fair

1. Use the same profile, `--size` and `--runtime` on every machine you compare.
2. Use the same OS image and kernel where possible, and record it (bench.sh does this).
3. Start from a fresh VM with nothing else running. On hosts you own, run `fstrim` on the filesystem (or `blkdiscard` a dedicated test device) before the run so every SSD starts in a comparable state.
4. Run at least **3 repeats** and report the **median**. The `full` profile does this, or run `standard` three times. `report.py` takes the median of `*.rN.json` repeats automatically.
5. When testing shared clouds, run at different times of day and publish the time. `run.json` has it in IST and UTC.
6. Publish the raw run directory alongside the post so anyone can re-render it.

## What we do not claim

These are synthetic tests. They predict application behaviour; they do not replace profiling your own workload. A single run on one VM describes that VM on that day, not a provider in general.
