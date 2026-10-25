# Benchmark results: bmh-noida-ceph-nvme-4c8g

*Profile `standard`, fio file 4G, 60 s per job, 1 repeat(s). Run started 2026-10-25T21:35:45+0530 IST (2026-10-25T16:05:45Z UTC) on `bmh-bench-tmp-a-20261025`, provider **BookMyHost**.*

## Headline numbers

| Metric | Value | Unit |
| --- | ---: | --- |
| 4k random read IOPS (QD1) | 896.0 | IOPS |
| 4k random read IOPS (QD32) | 80,088 | IOPS |
| 4k random write IOPS (QD32) | 20,667 | IOPS |
| 1M sequential read MB/s | 3,992 | MB/s |
| 1M sequential write MB/s | 1,715 | MB/s |
| 4k read latency p99 (us, QD1) | 1,810 | us |
| 4k fsync write latency p99 (us) | 8,225 | us |
| sysbench CPU events/s (1 thread) | 514.1 | events/s |
| sysbench CPU events/s (4 threads) | 2,059 | events/s |
| Memory read MiB/s (1 thread) | 24,168 | MiB/s |
| Memory write MiB/s (1 thread) | 22,123 | MiB/s |
| iperf3 download Mbit/s | 191.0 | Mbit/s |
| iperf3 upload Mbit/s | 191.2 | Mbit/s |
| CPU steal avg % (probe) | 0.00 | % |

## Disk (fio, direct=1, libaio)

| Test | rw | bs | QD | jobs | IOPS | MB/s | lat mean us | p50 us | p99 us | p99.9 us |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `4k-randread-qd1` | randread | 4k | 1 | 1 | 896 | 3.7 | 1,099 | 1,057 | 1,860 | 5,014 |
| `4k-randread-qd32` | randread | 4k | 32 | 4 | 80,088 | 328.0 | 1,593 | 1,532 | 3,457 | 9,241 |
| `4k-randwrite-qd1` | randwrite | 4k | 1 | 1 | 541 | 2.2 | 1,827 | 1,843 | 3,064 | 4,555 |
| `4k-randwrite-qd32` | randwrite | 4k | 32 | 4 | 20,667 | 84.7 | 6,186 | 4,620 | 29,491 | 48,497 |
| `4k-randrw70-qd32` | randrw | 4k | 32 | 4 | 42,417 | 173.7 | 2,335 | 1,876 | 9,372 | 17,170 |
| `64k-seqread` | read | 64k | 16 | 2 | 21,522 | 1,410.5 | 1,480 | 1,188 | 5,276 | 7,832 |
| `64k-seqwrite` | write | 64k | 16 | 2 | 8,191 | 536.8 | 3,894 | 3,948 | 7,373 | 10,813 |
| `1m-seqread` | read | 1M | 16 | 2 | 3,806 | 3,992.0 | 8,368 | 7,766 | 19,530 | 26,346 |
| `1m-seqwrite` | write | 1M | 16 | 2 | 1,635 | 1,715.2 | 19,435 | 18,481 | 40,632 | 52,167 |
| `4k-randread-lat-qd1` | randread | 4k | 1 | 1 | 929 | 3.8 | 1,075 | 1,036 | 1,810 | 3,719 |
| `4k-fsync-write` | write | 4k | 1 | 1 | 183 | 0.8 | 5,421 | 5,472 | 8,225 | 13,959 |

### Mixed workloads, read/write split

| Test | Read IOPS | Read p99 us | Write IOPS | Write p99 us |
| --- | ---: | ---: | ---: | ---: |
| `4k-randrw70-qd32` | 29,692 | 9,372 | 12,726 | 13,304 |

## CPU and memory (sysbench)

| Test | Result | Unit |
| --- | ---: | --- |
| CPU, 1 thread, max-prime 20000 | 514.1 | events/s |
| CPU, 4 threads | 2,058.6 | events/s |
| Thread scaling (all / 1) | 4.00 | x |
| Memory read, 1 MiB blocks | 24,168 | MiB/s |
| Memory write, 1 MiB blocks | 22,123 | MiB/s |
| openssl aes-256-gcm, 16 KiB blocks | 4,322 | MB/s |
| Pure-Python loop sanity score | 6.40 | Mops/s |

## Network

| Test | Result | Unit | Detail |
| --- | ---: | --- | --- |
| iperf3 download (4 streams, 10 s) | 191 | Mbit/s | retransmits 317.0 |
| iperf3 upload (4 streams, 10 s) | 191 | Mbit/s | retransmits 423.0 |
| ping 1.1.1.1 | 3.01 | ms avg | min 2.69 / max 3.49 / mdev 0.21 ms, loss 0.00% |
| ping 160.22.109.60 | 0.39 | ms avg | min 0.21 / max 0.93 / mdev 0.14 ms, loss 0.00% |
| curl TTFB bookmyhost.com | 81 | ms median | min 77 ms over 5 requests |
| curl TTFB www.google.com | 138 | ms median | min 130 ms over 5 requests |

## Noisy-neighbour probe

- CPU steal over 60 s: avg **0.00 %**, p95 0.00 %, max 0.00 % (baseline before run: 0.00 %).
- 4k QD1 read p99 across 6 samples: 1,794 - 1,958 us (spread 1.09x). A spread above 2x usually means a busy neighbour.

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
