# Benchmark results: bmh-noida-ceph-nvme-4c8g

*Profile `standard`, fio file 4G, 60 s per job, 3 repeat(s). Run started 2026-10-25T21:35:45+0530 IST (2026-10-25T16:05:45Z UTC) on `bmh-bench-tmp-a-20261025`, provider **BookMyHost**.*

## Headline numbers

| Metric | Value | Unit |
| --- | ---: | --- |
| 4k random read IOPS (QD1) | 933.7 | IOPS |
| 4k random read IOPS (QD32) | 80,088 | IOPS |
| 4k random write IOPS (QD32) | 19,839 | IOPS |
| 1M sequential read MB/s | 4,026 | MB/s |
| 1M sequential write MB/s | 1,822 | MB/s |
| 4k read latency p99 (us, QD1) | 1,810 | us |
| 4k fsync write latency p99 (us) | 8,225 | us |
| sysbench CPU events/s (1 thread) | 514.9 | events/s |
| sysbench CPU events/s (4 threads) | 2,051 | events/s |
| Memory read MiB/s (1 thread) | 25,190 | MiB/s |
| Memory write MiB/s (1 thread) | 22,423 | MiB/s |
| iperf3 download Mbit/s | 190.9 | Mbit/s |
| iperf3 upload Mbit/s | 191.1 | Mbit/s |
| CPU steal avg % (probe) | 0.00 | % |

## Disk (fio, direct=1, libaio)

| Test | rw | bs | QD | jobs | IOPS | MB/s | lat mean us | p50 us | p99 us | p99.9 us |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `4k-randread-qd1` | randread | 4k | 1 | 1 | 934 | 3.8 | 1,055 | 1,004 | 1,843 | 2,933 |
| `4k-randread-qd32` | randread | 4k | 32 | 4 | 80,088 | 328.0 | 1,593 | 1,532 | 3,883 | 12,517 |
| `4k-randwrite-qd1` | randwrite | 4k | 1 | 1 | 476 | 1.9 | 2,077 | 1,909 | 9,896 | 12,780 |
| `4k-randwrite-qd32` | randwrite | 4k | 32 | 4 | 19,839 | 81.3 | 6,444 | 3,916 | 42,730 | 63,177 |
| `4k-randrw70-qd32` | randrw | 4k | 32 | 4 | 41,406 | 169.6 | 2,430 | 1,728 | 13,697 | 25,035 |
| `64k-seqread` | read | 64k | 16 | 2 | 21,522 | 1,410.5 | 1,480 | 1,172 | 5,472 | 8,847 |
| `64k-seqwrite` | write | 64k | 16 | 2 | 8,030 | 526.3 | 3,973 | 4,014 | 7,832 | 13,042 |
| `1m-seqread` | read | 1M | 16 | 2 | 3,839 | 4,026.1 | 8,297 | 7,438 | 20,054 | 26,346 |
| `1m-seqwrite` | write | 1M | 16 | 2 | 1,737 | 1,822.1 | 18,278 | 17,957 | 35,389 | 52,167 |
| `4k-randread-lat-qd1` | randread | 4k | 1 | 1 | 929 | 3.8 | 1,075 | 1,036 | 1,810 | 3,719 |
| `4k-fsync-write` | write | 4k | 1 | 1 | 183 | 0.8 | 5,421 | 5,472 | 8,225 | 13,959 |

### Mixed workloads, read/write split

| Test | Read IOPS | Read p99 us | Write IOPS | Write p99 us |
| --- | ---: | ---: | ---: | ---: |
| `4k-randrw70-qd32` | 28,986 | 13,697 | 12,420 | 17,957 |

## CPU and memory (sysbench)

| Test | Result | Unit |
| --- | ---: | --- |
| CPU, 1 thread, max-prime 20000 | 514.9 | events/s |
| CPU, 4 threads | 2,051.3 | events/s |
| Thread scaling (all / 1) | 3.97 | x |
| Memory read, 1 MiB blocks | 25,190 | MiB/s |
| Memory write, 1 MiB blocks | 22,423 | MiB/s |
| openssl aes-256-gcm, 16 KiB blocks | 4,322 | MB/s |
| Pure-Python loop sanity score | 6.49 | Mops/s |

## Network

| Test | Result | Unit | Detail |
| --- | ---: | --- | --- |
| iperf3 download (4 streams, 10 s) | 191 | Mbit/s | retransmits 325.0 |
| iperf3 upload (4 streams, 10 s) | 191 | Mbit/s | retransmits 423.0 |
| ping 1.1.1.1 | 3.18 | ms avg | min 2.66 / max 4.21 / mdev 0.33 ms, loss 0.00% |
| ping 160.22.109.60 | 0.33 | ms avg | min 0.15 / max 0.69 / mdev 0.12 ms, loss 0.00% |
| curl TTFB bookmyhost.com | 81 | ms median | min 73 ms over 5 requests |
| curl TTFB www.google.com | 138 | ms median | min 132 ms over 5 requests |

## Noisy-neighbour probe

- CPU steal over 60 s: avg **0.00 %**, p95 0.00 %, max 0.00 % (baseline before run: 0.00 %).
- 4k QD1 read p99 across 6 samples: 1,761 - 1,958 us (spread 1.09x). A spread above 2x usually means a busy neighbour.

## System

| Fact | Value |
| --- | --- |
| Hostname | `bmh-bench-tmp-a-20261025` |
| CPU | Intel Xeon Processor (Cascadelake) (4 cores / 4 threads, 3,093 MHz) |
| RAM | 7,941 MiB |
| Virtualisation | kvm |
| Kernel | 6.8.0-138-generic |
| Distro | Ubuntu 24.04.4 LTS |
| Disk | /dev/vda1 unknown (scheduler [none] mq-deadline , rotational yes) |
| Filesystem | ext4 on / |
| Tools | fio fio-3.36, sysbench sysbench 1.0.20, iperf3 iperf 3.16 (cJSON 1.7.15) |

## Methodology

All disk tests use fio with `--direct=1` (bypasses the page cache), `ioengine=libaio`, `time_based` runs on a pre-filled file written with real data, and `group_reporting`. Latency percentiles are completion latencies; the dedicated latency test uses `lat_percentiles`. QD1 shows what a single synchronous thread sees; QD32 shows throughput under parallel load. Mixed 70/30 approximates OLTP. The fsync test measures what a database commit pays per transaction. CPU is sysbench prime search (deterministic). Full details, caveats for VMs (steal, ballooning, thin provisioning) and fairness rules in [docs/methodology.md](https://github.com/geetmangal/bmh-nvme-bench/blob/main/docs/methodology.md).

## Reproduce

```bash
git clone https://github.com/geetmangal/bmh-nvme-bench && cd bmh-nvme-bench
./bench.sh --profile standard --size 4G --runtime 60 --label "bmh-noida-ceph-nvme-4c8g" --provider BookMyHost --iperf-server 160.22.109.60 --no-prompt
python3 report.py results/<run-dir>/
```

*Generated by bmh-nvme-bench 0.1.0 report.py at 2026-10-25T22:19:03+0530 IST. Published results from BookMyHost NVMe nodes: https://bookmyhost.com*
