---
title: "{{label}}: NVMe VPS benchmark (fio, sysbench, iperf3)"
date: {{date_ist}}
provider: {{provider}}
tags: [nvme, vps, benchmark, fio]
---

# {{label}}: what an NVMe VPS really delivers

> TL;DR: **{{randread_qd32_iops}}** 4k random read IOPS at QD32, **{{randread_qd1_p99_us}} us** p99 read latency at QD1, **{{seqread_1m_mbps}} MB/s** sequential read, and **{{fsync_p99_us}} us** p99 per fsync. Plan price: INR {{plan_price_inr}}/month.

<!-- One paragraph: why we ran this, and what question it answers for the reader. -->

## The machine

- Provider: {{provider}}
- CPU: {{cpu_model}}, {{vcpus}} vCPU
- RAM: {{ram_gib}} GiB
- Virtualisation: {{virt}}, kernel {{kernel}}, filesystem {{fstype}}
- Benchmark profile: `{{profile}}`

## Headline numbers

{{headline_table}}

## What the numbers mean

<!-- QD1 vs QD32 in plain words; what p99 means for a WordPress / Laravel / PostgreSQL user. -->

## Disk detail

<!-- Paste the per-test table from summary.md, or embed the summary.html charts. -->

## CPU, memory and network

<!-- sysbench scaling, iperf3, ping and TTFB from summary.md. -->

## Stability: the noisy-neighbour probe

<!-- Steal % and p99 spread over the probe window. -->

## How we compared (comparison posts only)

<!-- Paste compare.md. State: same profile, same file size, median of 3 runs, run times in IST. -->

## Reproduce it yourself

```bash
git clone https://github.com/geetmangal/bmh-nvme-bench && cd bmh-nvme-bench
{{reproduce_cmd}}
python3 report.py results/<run-dir>/
```

Methodology and caveats: https://github.com/geetmangal/bmh-nvme-bench/blob/main/docs/methodology.md

---

*Benchmarked by BookMyHost engineering. More results from our Noida and Chennai NVMe nodes: https://bookmyhost.com*
