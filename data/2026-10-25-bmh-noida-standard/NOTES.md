# Run notes: BookMyHost Noida, standard profile x3, 25 Oct 2026 IST

- **VMs:** two temporary Ubuntu 24.04 KVM guests on Apache CloudStack, Noida zone, offering `pilot-ha-medium`
  (4 vCPU / 8 GB RAM, CPU shown as Intel Xeon Processor (Cascadelake)), public-direct network, 20 GB root volume.
  `bmh-bench-tmp-a-20261025` (160.22.109.58) ran the benchmark; `bmh-bench-tmp-b-20261025` (160.22.109.60) ran only `iperf3 -s`.
  Both were destroyed with expunge at 22:18 IST; no VM or volume named bmh-bench-tmp remains.
- **Storage:** the VM disk is a Ceph RBD image on an erasure-coded 3+1 pool over Micron 7400 NVMe drives, one per host.
  It is **network block storage, not a local NVMe drive**, so QD1 and fsync latency include a network round trip and
  EC write overhead. No IOPS or bandwidth cap is set on the offering.
- **Profile:** `standard` (4 GiB pre-filled file, 60 s per fio job, 4 jobs for random, 2 jobs at QD16 for sequential),
  run three separate times back to back on the same VM:
  - run 1: 21:35:45 to 21:49:55 IST (`bmh-noida-ceph-nvme-4c8g-20261025-213545`)
  - run 2: 21:49:55 to 22:03:58 IST (`...-214955`)
  - run 3: 22:03:58 to 22:17:57 IST (`...-220358`)
  Total 42 min 12 s, Sunday evening.
- **Medians:** `median/` was made with `python3 report.py median bmh-noida-ceph-nvme-4c8g-* --out median`.
  Every numeric metric is the median across the three runs; `median/runs-compare.md` shows the runs side by side.
  The `latency_samples` list in median.json is copied from run 1 (lists are not averaged); the spread figure is the median.
- **Network:** iperf3 is **VM to VM inside the same zone** (4 streams, 10 s each way), not internet throughput.
  It measured ~191 Mbit/s, which is the CloudStack global `vm.network.throttling.rate` = 200 Mbit/s applying because
  the offering sets no network rate. It shows the per-VM shaping limit, not the fabric.
- **Load:** steal probe 0.00 % in all three runs.
