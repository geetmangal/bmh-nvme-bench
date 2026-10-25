# bmh-nvme-bench

Reproducible NVMe VPS benchmarks you can run on any Linux server and publish. One command runs fio (random and sequential, QD1 to QD64, p99/p99.9 latency, fsync), sysbench CPU and memory, iperf3, ping, HTTPS TTFB and a noisy-neighbour steal probe. A second command turns the raw output into blog-ready Markdown, a self-contained HTML report with SVG charts, CSV, and side-by-side comparisons ("× faster", INR per 10k IOPS).

Everything is plain Bash plus Python 3 stdlib. No agents, no uploads, no telemetry: results stay on your machine.

## Quick start

The safe path (read the script first, then run it):

```bash
git clone https://github.com/geetmangal/bmh-nvme-bench
cd bmh-nvme-bench
sudo apt-get install -y fio sysbench iperf3 jq python3 nvme-cli   # Debian/Ubuntu
./bench.sh --dry-run --profile quick                               # print the plan, run nothing
./bench.sh --profile standard --label "my-vps-4c8g" --provider myhost
```

The one-liner, for throwaway VMs. When bench.sh runs from a pipe it has no profiles or fio job files next to it, so it downloads the `main` tarball into `~/.cache/bmh-nvme-bench` once. Results still go to `./results/`:

```bash
curl -fsSL https://raw.githubusercontent.com/geetmangal/bmh-nvme-bench/main/bench.sh | bash -s -- --profile quick
```

Piping a script into bash runs code you have not read. Prefer the git clone path on any machine that matters.

## Usage

```text
./bench.sh [--profile quick|standard|full] [--target DIR] [--size 4G] [--runtime 60]
           [--label NAME] [--provider NAME] [--plan-price-inr N]
           [--skip cpu,mem,net,disk,probe,extras] [--iperf-server HOST]
           [--out results/<label>-<ts>/] [--dry-run] [--no-prompt] [--keep-file]
```

| Profile | Time | File | Runtime/job | Repeats | Notes |
| --- | --- | --- | --- | --- | --- |
| `quick` | ~5 min | 1G | 15 s | 1 | smoke test, CI |
| `standard` | ~25 min | 4G | 60 s | 1 | what we publish |
| `full` | 1.5-2 h | 8G | 120 s | 3 (median) | adds QD64 |

`--target` must be a directory on the disk under test. bench.sh refuses `/`, tmpfs/ramfs and paths not on any mounted filesystem, warns on overlay/9p, checks free space, and deletes the test file on exit (Ctrl-C included). `NO_COLOR=1` disables colours.

Each run writes `results/<label>-<timestamp>/` with `run.json` (flags, tool versions, start/end in IST and UTC), `sysinfo.json` (CPU, RAM, kernel, virt type, disk model, scheduler, fs, steal baseline), `commands.log`, and the raw `fio/*.json`, `sysbench/*.txt`, `net/*`, `probe/*` and `extras/*` output.

## Reports

```bash
python3 report.py results/my-vps-4c8g-20261025-143000/          # summary.json/.md/.html/.csv
python3 report.py results/<run>/ --blog                           # also fills docs/blog-post-template.md
python3 report.py results/<run>/ --json-only
python3 report.py compare results/a/ results/b/ --labels "BookMyHost,Other" --out compare/
```

`compare` writes `compare.md`, `compare.html`, `compare.svg` and `compare.json`. Run bench.sh with `--plan-price-inr` and the comparison adds INR per 10k IOPS. The JSON schema is in [docs/schema.md](docs/schema.md). Exit codes: 0 ok, 1 usage, 2 no data, 3 parse error.

## Example output

This is the headline table from the test fixture `tests/fixtures/run-a` (a 4 vCPU / 8 GiB KVM VM profile). It is sample data for the test suite, not a published measurement:

| Metric | Value | Unit |
| --- | ---: | --- |
| 4k random read IOPS (QD1) | 11,850 | IOPS |
| 4k random read IOPS (QD32) | 127,498 | IOPS |
| 4k random write IOPS (QD32) | 88,420 | IOPS |
| 1M sequential read MB/s | 2,362 | MB/s |
| 1M sequential write MB/s | 1,794 | MB/s |
| 4k read latency p99 (us, QD1) | 147.5 | us |
| 4k fsync write latency p99 (us) | 620.0 | us |
| sysbench CPU events/s (1 thread) | 1,187 | events/s |
| sysbench CPU events/s (4 threads) | 4,536 | events/s |
| iperf3 download Mbit/s | 9,381 | Mbit/s |
| CPU steal avg % (probe) | 0.03 | % |

## Reproducing published results

Every `summary.md` ends with the exact command that produced it. To compare fairly, use the same profile, `--size` and `--runtime` on every machine, run three times, and report the median. [docs/methodology.md](docs/methodology.md) explains what each test measures, why `direct=1`, QD1 vs QD32, how to read p99, and the VM caveats (steal, ballooning, burst credits, thin provisioning).

## Development

```bash
make test    # unittest over fixtures (tests build their own run dirs in a temp dir)
make lint    # bash -n + shellcheck + py_compile
make fixtures  # regenerate tests/fixtures/run-a and run-b
```

## Licence

MIT, see [LICENSE](LICENSE). Copyright 2026 Blazing Bullet Pvt Ltd.

---

Maintained by BookMyHost engineering. Results from our Noida/Chennai NVMe nodes are published at https://bookmyhost.com/blog
