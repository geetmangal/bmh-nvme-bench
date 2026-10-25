# Run notes: BookMyHost Noida, quick profile, 25 Oct 2026 20:48 IST

- **VM:** temporary 4 vCPU / 8 GB Ubuntu 24.04 KVM guest on cs-node1, CloudStack zone in Noida (sector 80), destroyed after the run.
- **Storage:** the VM disk is a Ceph RBD image on an erasure-coded 3+1 pool spread over Micron 7400 NVMe drives, one per host. It is network block storage, not a local NVMe drive passed through to the guest, so QD1 and fsync latency include a network round trip and EC write overhead.
- **Profile:** `quick` (1 GiB file, 15 s per job, 1 repeat). Treat the numbers as indicative. Publishable numbers need `--profile standard`, three repeats and the median.
- **Network:** no iperf3 server was given, so throughput was skipped. Ping and TTFB ran.
- **Load:** run on a Sunday evening, with the steal probe at 0.01 % average.
