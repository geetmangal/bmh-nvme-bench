"""Unit tests for report.py: parsers against fixtures, rendering, and the compare path."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIX = os.path.join(HERE, "fixtures")
sys.path.insert(0, ROOT)

import report  # noqa: E402

_GEN_DIR = None


def fixture_runs():
    """Build run-a/run-b once per test process in a temp dir (never trusts files on disk)."""
    global _GEN_DIR
    if _GEN_DIR is None:
        _GEN_DIR = tempfile.mkdtemp(prefix="bmh-bench-fixtures-")
        subprocess.run([sys.executable, os.path.join(FIX, "gen_runs.py"), _GEN_DIR], check=True, stdout=subprocess.DEVNULL)
    return os.path.join(_GEN_DIR, "run-a"), os.path.join(_GEN_DIR, "run-b")


def tearDownModule():
    if _GEN_DIR:
        shutil.rmtree(_GEN_DIR, ignore_errors=True)


class ParserTests(unittest.TestCase):
    def test_fio_two_jobs_summed(self):
        r = report.parse_fio(os.path.join(FIX, "fio_randread.json"))
        self.assertEqual(r["jobs"], 2)
        self.assertIsNone(r["write"])
        self.assertAlmostEqual(r["read"]["iops"], 127498.2, places=1)
        self.assertAlmostEqual(r["read"]["bw_mbps"], 522.2, places=1)
        # worst-job percentiles, ns -> us
        self.assertAlmostEqual(r["read"]["lat_us"]["p50"], 481.3, places=1)
        self.assertAlmostEqual(r["read"]["lat_us"]["p99"], 1187.8, places=1)
        self.assertAlmostEqual(r["read"]["lat_us"]["p999"], 2146.3, places=1)
        self.assertEqual(r["options"]["iodepth"], "32")
        self.assertEqual(r["options"]["rw"], "randread")

    def test_fio_seq(self):
        r = report.parse_fio(os.path.join(FIX, "fio_seq.json"))
        self.assertAlmostEqual(r["read"]["bw_mbps"], 2362.2, places=1)
        self.assertAlmostEqual(r["read"]["iops"], 2252.8, places=1)
        self.assertAlmostEqual(r["read"]["lat_us"]["p99"], 25165.8, places=1)
        self.assertEqual(r["options"]["bs"], "1M")

    def test_fio_garbage_raises(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write("fio: warning\nnot json at all")
        try:
            with self.assertRaises(report.ParseError):
                report.parse_fio(fh.name)
        finally:
            os.unlink(fh.name)

    def test_sysbench_cpu(self):
        r = report.parse_sysbench_cpu(open(os.path.join(FIX, "sysbench_cpu.txt")).read())
        self.assertEqual(r["events_per_second"], 1187.42)
        self.assertEqual(r["threads"], 1)
        self.assertEqual(r["events"], 11876)
        self.assertEqual(r["lat_p95_ms"], 0.86)

    def test_sysbench_mem(self):
        r = report.parse_sysbench_mem(open(os.path.join(FIX, "sysbench_mem.txt")).read())
        self.assertEqual(r["mib_per_sec"], 10968.52)
        self.assertEqual(r["block_kib"], 1024)

    def test_iperf3(self):
        r = report.parse_iperf3(os.path.join(FIX, "iperf3.json"))
        self.assertAlmostEqual(r["received_mbps"], 9380.9, places=1)
        self.assertAlmostEqual(r["mbps"], 9380.9, places=1)
        self.assertEqual(r["retransmits"], 37)
        self.assertEqual(r["streams"], 4)
        self.assertTrue(r["reverse"])

    def test_ping(self):
        r = report.parse_ping(open(os.path.join(FIX, "ping.txt")).read())
        self.assertEqual(r["sent"], 20)
        self.assertEqual(r["loss_pct"], 0.0)
        self.assertEqual(r["avg_ms"], 1.943)
        self.assertEqual(r["max_ms"], 2.31)
        self.assertEqual(r["host"], "1.1.1.1")

    def test_curl_ttfb(self):
        r = report.parse_curl_ttfb("https://x/ ttfb=0.100000 connect=0.01 tls=0.02 http=200\nhttps://x/ ttfb=0.120000 connect=0.01 tls=0.02 http=200\nhttps://x/ ttfb=0.090000 connect=0.01 tls=0.02 http=301\n")
        self.assertEqual(r["samples"], 3)
        self.assertEqual(r["ttfb_ms_median"], 100.0)
        self.assertEqual(r["ttfb_ms_min"], 90.0)
        self.assertEqual(r["http_codes"], ["200", "301"])


class RunATests(unittest.TestCase):
    """End-to-end over the fixture run dir laid out the way bench.sh writes it."""

    @classmethod
    def setUpClass(cls):
        cls.run_a, cls.run_b = fixture_runs()
        cls.summary = report.build_summary(cls.run_a)

    def test_summary_shape(self):
        s = self.summary
        self.assertEqual(s["schema_version"], report.SCHEMA_VERSION)
        for key in ("run", "system", "disk", "cpu", "memory", "network", "probe", "extras", "headline"):
            self.assertIn(key, s)
        self.assertEqual(s["run"]["label"], "bmh-nvme-noida-vm-4c8g")
        self.assertEqual(s["system"]["virt"], "kvm")

    def test_disk_numbers(self):
        d = self.summary["disk"]
        self.assertIn("4k-randread-qd32", d)
        self.assertAlmostEqual(d["4k-randread-qd32"]["iops"], 127498.2, places=1)
        self.assertAlmostEqual(d["4k-randread-qd32"]["p99_us"], 1187.8, places=1)
        self.assertAlmostEqual(d["1m-seqread"]["bw_mbps"], 2362.2, places=1)
        self.assertAlmostEqual(d["4k-randread-qd1"]["iops"], 11850.4, places=1)
        self.assertAlmostEqual(d["4k-randread-lat-qd1"]["p99"] if "p99" in d["4k-randread-lat-qd1"] else d["4k-randread-lat-qd1"]["p99_us"], 145.0 + 2.5, places=1)
        # fsync test reports the sync() latency, not the write completion latency
        self.assertAlmostEqual(d["4k-fsync-write"]["p99_us"], 620.0, places=1)
        # mixed workload: IOPS is read + write
        m = d["4k-randrw70-qd32"]
        self.assertAlmostEqual(m["iops"], m["read"]["iops"] + m["write"]["iops"], places=1)
        self.assertNotIn("prefill", d)

    def test_cpu_mem_net_probe(self):
        s = self.summary
        self.assertEqual(s["cpu"]["single_thread"]["events_per_second"], 1187.42)
        self.assertEqual(s["cpu"]["all_threads"]["threads"], 4)
        self.assertAlmostEqual(s["cpu"]["scaling"], 3.82, places=2)
        self.assertEqual(s["memory"]["read"]["mib_per_sec"], 10968.52)
        self.assertAlmostEqual(s["network"]["iperf3"]["download"]["mbps"], 9380.9, places=1)
        self.assertTrue(s["network"]["iperf3"]["download"]["reverse"])
        self.assertFalse(s["network"]["iperf3"]["upload"]["reverse"])
        self.assertIn("1.1.1.1", s["network"]["ping"])
        self.assertIn("bookmyhost.com", s["network"]["ttfb"])
        self.assertEqual(s["probe"]["steal"]["samples"], 20)
        self.assertAlmostEqual(s["probe"]["steal"]["max_pct"], 0.31, places=2)
        self.assertEqual(len(s["probe"]["latency_samples"]), 3)
        self.assertAlmostEqual(s["extras"]["pyloop_mops"], 5.21, places=2)

    def test_headline_rows(self):
        names = [r["metric"] for r in self.summary["headline"]]
        self.assertIn("4k random read IOPS (QD32)", names)
        self.assertIn("4k fsync write latency p99 (us)", names)
        self.assertIn("iperf3 download Mbit/s", names)

    def test_render_all_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = report.main([self.run_a, "--out", tmp, "--quiet", "--blog"])
            self.assertEqual(rc, 0)
            for f in ("summary.json", "summary.md", "summary.html", "summary.csv", "blog.md"):
                self.assertTrue(os.path.getsize(os.path.join(tmp, f)) > 0, f)
            md = open(os.path.join(tmp, "summary.md")).read()
            self.assertIn("## Headline numbers", md)
            self.assertIn("| 4k random read IOPS (QD32) | 127,498 | IOPS |", md)
            self.assertIn("## Reproduce", md)
            self.assertIn("--profile standard", md)
            html = open(os.path.join(tmp, "summary.html")).read()
            self.assertIn("<svg", html)
            self.assertNotIn("<script", html)
            with open(os.path.join(tmp, "summary.csv")) as fh:
                rows = fh.read().splitlines()
            self.assertEqual(rows[0], "label,section,test,metric,value,unit")
            self.assertTrue(any(r.startswith("bmh-nvme-noida-vm-4c8g,disk,4k-randread-qd32,iops,127498.2,IOPS") for r in rows), rows[:5])
            blog = open(os.path.join(tmp, "blog.md")).read()
            self.assertNotIn("{{label}}", blog)
            self.assertIn("bmh-nvme-noida-vm-4c8g", blog)
            json.load(open(os.path.join(tmp, "summary.json")))

    def test_json_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(report.main([self.run_a, "--out", tmp, "--quiet", "--json-only"]), 0)
            self.assertTrue(os.path.exists(os.path.join(tmp, "summary.json")))
            self.assertFalse(os.path.exists(os.path.join(tmp, "summary.md")))

    def test_repeats_median(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(self.run_a, os.path.join(tmp, "r"))
            src = os.path.join(tmp, "r", "fio", "4k-randread-qd1.json")
            for n, factor in ((2, 0.5), (3, 2.0)):
                data = json.load(open(src))
                data["jobs"][0]["read"]["iops"] *= factor
                json.dump(data, open(os.path.join(tmp, "r", "fio", f"4k-randread-qd1.r{n}.json"), "w"))
            s = report.build_summary(os.path.join(tmp, "r"))
            self.assertEqual(s["disk"]["4k-randread-qd1"]["repeats"], 3)
            self.assertAlmostEqual(s["disk"]["4k-randread-qd1"]["iops"], 11850.4, places=1)

    def test_exit_codes(self):
        self.assertEqual(report.main(["/nonexistent/run/dir", "--quiet"]), 2)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(report.main([tmp, "--quiet"]), 2)  # exists but empty
            self.assertEqual(report.main(["compare", tmp, "--quiet"]), 1)  # needs >= 2 dirs


class CompareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_a, cls.run_b = fixture_runs()

    def test_compare_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = report.main(["compare", self.run_a, self.run_b, "--labels", "BookMyHost,Competitor X", "--out", tmp, "--quiet"])
            self.assertEqual(rc, 0)
            for f in ("compare.json", "compare.md", "compare.html", "compare.svg"):
                self.assertTrue(os.path.getsize(os.path.join(tmp, f)) > 0, f)
            c = json.load(open(os.path.join(tmp, "compare.json")))
            self.assertEqual(c["labels"], ["BookMyHost", "Competitor X"])
            byname = {m["test"] + ":" + m["key"]: m for m in c["metrics"]}
            rr = byname["4k-randread-qd32:iops"]
            self.assertEqual(rr["best_index"], 0)
            self.assertAlmostEqual(rr["x_vs_first"][1], 0.42, places=2)  # competitor is 0.42x
            lat = byname["4k-randread-lat-qd1:p99_us"]
            self.assertFalse(lat["higher_is_better"])
            self.assertAlmostEqual(lat["x_vs_first"][1], 1 / 2.6, delta=0.01)  # higher latency -> <1x
            self.assertEqual(lat["best_index"], 0)
            vfm = c["value_for_money"]
            self.assertAlmostEqual(vfm[0]["inr_per_10k_read_iops"], 1499 / 12.74982, places=2)
            self.assertIsNotNone(vfm[1]["inr_per_10k_read_iops"])
            md = open(os.path.join(tmp, "compare.md")).read()
            self.assertIn("| Metric | BookMyHost | Competitor X | x (Competitor X) |", md)
            self.assertIn("## Value for money", md)
            self.assertIn("0.42x", md)
            svg = open(os.path.join(tmp, "compare.svg")).read()
            self.assertTrue(svg.startswith("<?xml"))
            self.assertIn("<rect", svg)

    def test_median_across_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "med")
            rc = report.main(["median", self.run_a, self.run_b, self.run_a, "--out", out, "--quiet"])
            self.assertEqual(rc, 0)
            for f in ("median.json", "median.md", "median.html", "median.csv", "runs-compare.md"):
                self.assertTrue(os.path.getsize(os.path.join(out, f)) > 0, f)
            m = json.load(open(os.path.join(out, "median.json")))
            a = report.build_summary(self.run_a)
            # two of three runs are run_a, so the median equals run_a
            self.assertEqual(m["disk"]["4k-randread-qd32"]["iops"], a["disk"]["4k-randread-qd32"]["iops"])
            self.assertEqual(m["run"]["repeats"], 3)
            self.assertEqual(len(m["run"]["median_of_runs"]), 3)
            cmp_out = os.path.join(tmp, "cmp")
            self.assertEqual(report.main(["compare", out, self.run_b, "--out", cmp_out, "--quiet"]), 0)
        self.assertEqual(report.main(["median", self.run_a, "--out", "x", "--quiet"]), 1)

    def test_compare_label_mismatch(self):
        self.assertEqual(report.main(["compare", self.run_a, self.run_b, "--labels", "only-one", "--quiet"]), 1)


if __name__ == "__main__":
    unittest.main()
