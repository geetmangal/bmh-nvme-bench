# Competitor comparison runbook (4 vCPU / 8 GB NVMe)

How to benchmark a competitor VM against BookMyHost with bmh-nvme-bench, the cheapest way:
on free-trial credit where it exists, or a short hourly-billed run where it does not.

- Researched and checked: **25 Oct 2026 IST**, only from the providers' own official pages.
- Currency: **1 USD = ₹84**, **1 EUR = ₹91** (approximate; prices exclude GST/VAT).
- "unverified" means the official page could not be fetched (403) or did not state the fact.
  Free-trial offers change often: re-check the linked page on the day of signup.
- Target shape: 4 vCPU, 8 GB RAM, NVMe (or the provider's closest), Ubuntu 24.04, region nearest India.
- Time needed per provider: 3 x `standard` profile (~25 min each) + setup = **budget ~2 hours of VM time**
  (two VMs if a same-region iperf3 server is used).

## 1. Provider table

| Provider | Trial terms (credit, duration, card?) | Usable for 4c/8g? | Closest 4c/8g plan, price (monthly / hourly) | Region nearest India | Source (checked 25 Oct 2026 IST) |
| --- | --- | --- | --- | --- | --- |
| DigitalOcean | **$5 credit, no card required** (official blog, Oct 2026). Validity unverified (pricing page mentions a $5/90-day example). The old $200/60-day offer is no longer the standard signup credit. | Partly: $5 covers ~70 h of the Basic 4/8 droplet *if* the trial allows that size (size limits unverified). | Basic 4 vCPU / 8 GiB, 160 GiB SSD: $48.00/mo (₹4,032), $0.07143/h (₹6.00/h). Basic is "SSD"; NVMe only on Premium/General Purpose variants (no 4/8 GP plan). | BLR1 Bangalore (unverified on page) | https://www.digitalocean.com/pricing/droplets , https://www.digitalocean.com/blog/introducing-agent-droplets |
| Vultr | "Free credits for up to 30 days" for new accounts; **payment method required** ($0.00 card link allowed). Amount: promo page says $250 (page returned 403, so amount unverified). | Yes, if the credit is granted (no plan restriction stated). | Cloud Compute Regular 4 vCPU / 8 GB, 180 GB: ~$48/mo (₹4,032), ~$0.071/h (₹5.96/h) (pricing page 403: unverified). NVMe on High Performance / High Frequency tiers (price unverified). | Mumbai / Bangalore / Delhi NCR (unverified) | https://docs.vultr.com/platform/create-an-account , https://www.vultr.com/pricing/ |
| Linode / Akamai | **US$100 credit** for new users; 60-day window appears in the FAQ (see promotion rules). Card: unverified. | Yes. | Shared CPU Linode 8 GB (4 CPU, 160 GB): $48/mo (₹4,032), $0.072/h (₹6.05/h). Dedicated 8 GB (4 vCPU) G7 $86/mo, $0.13/h (₹10.92/h). Prices shown for Jakarta; "some plans differ by region". | Mumbai / Chennai (region prices unverified) | https://www.akamai.com/cloud/pricing , https://www.akamai.com/cloud/pricing/cpu |
| Hetzner | **No free trial** (none on the cloud page). | No (paid hourly). | CPX32 4 vCPU AMD / 8 GB / 160 GB NVMe. Singapore: €49.49/mo (₹4,504), €0.0785/h (₹7.14/h). EU: €35.99/mo, €0.0577/h (₹5.25/h). CX33 (4/8/80 GB NVMe, EU only) €8.49/mo, €0.0136/h, listed as currently unavailable. | Singapore (SIN1) | https://www.hetzner.com/cloud/regular-performance/ , https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/ |
| AWS | New accounts (on/after 15 Jul 2025): **$100 credit + up to $100 more, 6 months** or until credits run out. Card: unverified on page. | **No on the Free plan**: only t3.micro, t3.small, t4g.micro, t4g.small, c7i-flex.large, m7i-flex.large are eligible (max 2 vCPU). A 4c/8g (c7i-flex.xlarge / c7i.xlarge) needs an upgrade to the Paid plan, which still gets up to $200 credits, but the account then becomes billable. | c7i.xlarge 4 vCPU / 8 GB: ~$0.17-0.18/h (~₹15/h), ~₹11,000/mo (unverified). Storage is EBS gp3 = network storage (NVMe interface only, not local). | ap-south-1 Mumbai (also ap-south-2 Hyderabad) | https://aws.amazon.com/free/ , https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html |
| Google Cloud | **$300 credit, 90 days**; card or other payment method required ($0-1 temporary hold). Trial: no GPUs, no quota increases, no Windows images. | Yes, very likely: a custom e2 4 vCPU / 8 GB fits the trial; any concurrent vCPU cap is not stated on the page (unverified). | e2-custom-4-8192: ~$0.11/h (~₹9.3/h), ~₹6,800/mo (us-central1 rates, unverified; Mumbai is somewhat higher). Disk = Persistent Disk (network); local NVMe SSD is not offered on e2. | asia-south1 Mumbai / asia-south2 Delhi | https://docs.cloud.google.com/free/docs/free-cloud-features , https://cloud.google.com/compute/vm-instance-pricing |
| Azure | **$200 credit, use within 30 days**; non-prepaid credit/debit card + phone required (temporary hold). Quota increases need Pay-As-You-Go. | Probably: a 4-vCPU VM should fit, but the free-trial core quota is not on the page (unverified). | F4s_v2 (4 vCPU / 8 GB) or B4als_v2 (4 / 8): price unverified (~$0.17/h, ~₹14/h). Managed disks are network storage. | Central India (Pune) / South India (Chennai) / West India (Mumbai) | https://azure.microsoft.com/en-us/pricing/offers/ms-azr-0044p , https://azure.microsoft.com/en-us/pricing/free-services |
| Oracle Cloud | **$300 trial credit** (30-day length unverified, page 403). **Always Free A1 is now 2 OCPU / 12 GB total** (docs), not 4 OCPU / 24 GB. Always Free must be in the home region. Card: unverified. | Always Free: **no** (2 OCPU = 2 Arm cores). Trial credit: yes, VM.Standard.A1.Flex 4 OCPU / 8 GB (Arm, not x86) or E5.Flex 2 OCPU (4 vCPU) / 8 GB. | A1.Flex 4 OCPU / 8 GB: ~$0.052/h (~₹4.4/h) (unverified). Boot volume = block storage (network). Arm results are not comparable 1:1 to x86 for CPU tests. | Mumbai / Hyderabad (pick as home region at signup) | https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm , https://www.oracle.com/cloud/free/ |
| UpCloud | A getting-started page mentions trial credit ("Explore with €500 for 30 days"): terms unverified (pricing page 403). | Unverified. | Premium / General Purpose 4 cores / 8 GB / 100 GB MaxIOPS: €52/mo (₹4,732); Starter 4 cores / 8 GB / 40 GB: €20/mo (₹1,820). Hourly unverified. | Singapore | https://upcloud.com/pricing/ , https://upcloud.com/get-started-with-upcloud/ |
| Kamatera | **30-day trial, up to $100 of services**: one server (scalable within $100), 1 TB block storage, 1 TB traffic. **Valid credit card required.** | Yes (one server). | Custom 4 vCPU / 8 GB: price only in the calculator (unverified). | Singapore (no India DC listed) | https://www.kamatera.com/free-trial/ , https://www.kamatera.com/pricing/ |
| OVHcloud | **₹18,000 free credit** for a first Public Cloud project (en-in page). Duration, card and eligibility: unverified. | Yes, if the credit is granted. | c3-8 (4 vCPU / 8 GB): price unverified. b3-8 is 2 vCPU / 8 GB at ~$0.0605/h. Outbound traffic is billed separately in APAC (Mumbai/Singapore). | Mumbai | https://www.ovhcloud.com/en-in/public-cloud/prices/ |
| E2E Networks | FAQ: new users can sign up for a "free trial account with limited resources"; credit amount unverified. | Unverified (trial limits unknown). | C3.8GB 4 vCPU / 8 GB / 100 GB NVMe: $35.64/mo (₹2,994), $0.049/h (₹4.12/h) (page shows USD). | Delhi NCR / Mumbai / Chennai (unverified on page) | https://www.e2enetworks.com/pricing |
| Hostinger | **No free trial**; 30-day money-back guarantee. No hourly billing. | No (no 4c/8g plan; prepaid terms). | No 4/8. KVM 2 (2 vCPU / 8 GB / 100 GB NVMe) ₹779/mo promo; KVM 4 (4 / 16 / 200 GB NVMe) ₹1,099/mo on 24-month prepay, renews ₹2,399/mo. | India DC unverified | https://www.hostinger.com/in/vps-hosting , https://www.hostinger.com/in/pricing/vps-hosting |
| Contabo | **No free trial.** Minimum 1-month contract, no hourly billing mentioned. | No (paid month). | Cloud VPS 4 (4 vCPU / 8 GB / 100 GB SSD, NVMe only on Cloud VPS 6+): €4.40-5.50/mo shown (₹400-500) (price label unclear; location surcharge / setup fee unverified). | Mumbai (India) and Singapore listed | https://contabo.com/en/vps/ |
| Utho | **₹1,800 credit** for new customers, valid credit card required, first-time customers only (landing page 403, from official-page search snippet: unverified). | Yes, ~15 days of the 4/8 plan. | Basic 2: 4 vCPU / 8 GB / 160 GB NVMe, ₹2,875/mo (₹8,625/qtr); hourly billing available (~₹3.9/h computed). | Mumbai / Bangalore / Delhi-Noida (unverified) | https://utho.com/pricing , https://utho.com/lp/index.php?title=30-day-trial-vps |
| MilesWeb | "30-day free VPS trial" but you **pay the sign-up amount** up front, refunded if cancelled within 30 days (i.e. a money-back trial). KYC not mentioned. | Only as pay-then-refund. | Managed VPS 4 vCPU / 8 GB / 160 GB NVMe ~₹799/mo (unverified, cached listings disagree); Cloud VPS SM-L3 4 vCPU / 16 GB ₹999/mo. | India DC (Delhi / Mumbai / Bengaluru pages) | https://www.milesweb.in/hosting/vps-hosting/free , https://www.milesweb.in/hosting/cloud-hosting/cloud-vps |
| Netcup | **No VPS trial** (only a web-hosting test account). 1, 12 or 24-month terms; no hourly billing. | No. | VPS 1000 G12.5: 4 vCore / 8 GB / 128 GB SSD, from €14.50/mo on 12 months (₹1,320). | Singapore | https://www.netcup.com/en/server/vps |

## 2. Who has a usable free trial

**Usable free trial / credit for a 4c/8g run (no out-of-pocket cost if destroyed in time):**

1. **Google Cloud** - $300 / 90 days, custom e2 4/8 in Mumbai or Delhi. Best documented. (network disk)
2. **Linode / Akamai** - $100 credit, Shared 8 GB (4 CPU) in Mumbai or Chennai.
3. **Vultr** - free credits up to 30 days (amount unverified), Mumbai / Bangalore / Delhi.
4. **Azure** - $200 / 30 days, Central/South/West India (core quota unverified).
5. **Kamatera** - $100 / 30 days, one server, Singapore. Card required.
6. **OVHcloud** - ₹18,000 credit, Mumbai (terms unverified).
7. **Utho** - ₹1,800 credit, Indian regions (unverified).
8. **Oracle Cloud** - $300 trial credit for an A1 4 OCPU/8 GB (Arm) or E5 4 vCPU/8 GB in Mumbai/Hyderabad. Always Free alone is only 2 OCPU / 12 GB now.
9. **DigitalOcean** - $5, no card: enough for ~70 h of Basic 4/8 *if* the size is allowed (unverified).
10. **AWS** - only after upgrading to the Paid plan (credits still apply; account becomes billable). The Free plan caps at 2 vCPU.

Unclear: **UpCloud** (trial wording unverified), **E2E Networks** (trial "limited resources", amount unknown), **MilesWeb** (pay first, refund within 30 days).

**No free trial (paid instead), approximate cost of a ~2 h test window (3 x standard + setup), 1 VM:**

| Provider | Billing | Approx cost |
| --- | --- | --- |
| Hetzner CPX32 Singapore | hourly, €0.0785/h | ~₹15 for 2 h (~₹7 per hour); +₹15 for an iperf3 VM |
| E2E C3.8GB (if no trial) | hourly, $0.049/h | ~₹8 for 2 h |
| Contabo Cloud VPS 4 | monthly only, 1-month minimum | ~₹400-500 for the month (plus any setup/location fee, unverified) |
| Netcup VPS 1000 G12.5 | 1/12/24-month terms | 1-month price unverified; 12-month ₹1,320/mo |
| Hostinger KVM 2 / KVM 4 | prepaid 24 months, 30-day refund | ₹779-1,099/mo x term up front, refundable in 30 days (no exact 4/8 plan) |

## 3. Steps for Geet (manual; Claude never signs up or enters payment details)

1. **Create the trial account** on the provider's official site (links above). Use the BookMyHost/Blazing Bullet
   card only where the trial requires one. Set a **billing alert / budget of ₹500** where the console allows it.
   For Oracle, choose **India West (Mumbai)** or **India South (Hyderabad)** as the home region at signup (it cannot be changed).
2. **Create the VM**:
   - Image: **Ubuntu 24.04 LTS** (x86_64; note it if the only option is Arm, e.g. Oracle A1).
   - Size: **4 vCPU / 8 GB** (closest plan from the table; write down the exact plan name and its monthly price).
   - Disk: NVMe / local SSD if the provider offers a choice; at least **40 GB free** for the 4 GiB test file plus OS.
     Write down whether the disk is local or network block storage (EBS, Persistent Disk, Managed Disk, Block Volume).
   - Region: nearest India (Mumbai > Delhi > Bangalore/Chennai > Hyderabad > Singapore).
   - Network: public IPv4, firewall allowing **TCP 22** from anywhere (or from our office IP), and **TCP/UDP 5201** between the two VMs if step 4 is used.
3. **Add our SSH public key** for user `bench` (preferred, with passwordless sudo) or `root`:
   ```
   ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF+vIzW1+aUh17Ftnw13VMeT7duMCIl9KTJEUrCjkogP
   ```
   Most consoles have an "SSH keys" field; otherwise paste it into cloud-init:
   ```yaml
   #cloud-config
   users:
     - name: bench
       sudo: ALL=(ALL) NOPASSWD:ALL
       shell: /bin/bash
       ssh_authorized_keys:
         - ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF+vIzW1+aUh17Ftnw13VMeT7duMCIl9KTJEUrCjkogP
   ```
4. **Optional: a second, small VM in the same region** (1-2 vCPU is enough) as the iperf3 server, same key.
5. **Send Claude**: provider, region, plan name + monthly price, public IP of the bench VM, private + public IP of
   the iperf3 VM, login user, and whether the disk is local or network.
6. **After Claude reports the run is done: destroy both VMs** (and any extra volumes, snapshots and reserved IPs),
   then check the billing page shows no running resources. On trials with auto-conversion, cancel or downgrade.

## 4. Commands Claude runs

Replace `<ip>`, `<provider>` (lowercase, e.g. `gcp`), `<Provider>` (display name, e.g. `GoogleCloud`), `<region>`
(e.g. `mumbai`), `<iperf-ip>` and `<price>` (monthly INR). All times IST.

```bash
# 0. connect (user bench or root)
ssh -o StrictHostKeyChecking=accept-new bench@<ip>

# 1. packages
sudo apt-get update && sudo apt-get install -y fio sysbench iperf3 jq nvme-cli git python3

# 2. suite
git clone https://github.com/geetmangal/bmh-nvme-bench ~/bmh-nvme-bench && cd ~/bmh-nvme-bench

# 3. (optional) iperf3 server on the second VM
ssh bench@<iperf-ip> 'sudo apt-get install -y iperf3 && (iperf3 -s -D)'

# 4. three standard runs (~25 min each), same label, back to back; each run gets results/<label>-<ts>/
for i in 1 2 3; do
  ./bench.sh --profile standard --no-prompt \
    --label <provider>-<region>-4c8g --provider <Provider> \
    --plan-price-inr <price> \
    --iperf-server <iperf-ip> --target $HOME/bench-tmp
done
# (drop --iperf-server if there is no second VM: the network test is then skipped)
# (use --dry-run first if in doubt; never --skip disk)

# 5. copy results back and render each run
scp -r bench@<ip>:~/bmh-nvme-bench/results/<provider>-<region>-4c8g-* results/
for d in results/<provider>-<region>-4c8g-*; do python3 report.py "$d"; done

# 6. fold the three runs into one median summary (every numeric metric = median across runs)
python3 report.py median results/<provider>-<region>-4c8g-* --out results/<provider>-median

# 7. compare against the BookMyHost standard baseline (median of 3 runs, 25 Oct 2026 IST)
python3 report.py compare data/2026-10-25-bmh-noida-standard/median results/<provider>-median \
  --labels BookMyHost,<Provider> --out compare/<provider>
```

`report.py median RUN_DIR... --out DIR` writes `median.json/.md/.html/.csv` plus `runs-compare.md`
(the runs side by side, to show run-to-run spread). `compare` accepts run dirs or median dirs, two or more,
and `--labels` must have the same count. It writes `compare.json/.md/.html/.svg` into `--out`.

Notes:
- The BookMyHost baseline is `data/2026-10-25-bmh-noida-standard/` (3 x `standard`, 4c/8g, Ubuntu 24.04,
  Ceph EC 3+1 RBD on NVMe; iperf3 VM to VM in the same zone). Use `.../median` as the first compare column.
- `--plan-price-inr` enables INR per 10k IOPS in `compare`; use the monthly price from the table.

## 5. Fairness rules (from docs/methodology.md)

1. **Same profile, `--size` and `--runtime`** on every machine compared (`standard`: 4G file, 60 s per job, 60 s probe).
2. **Same OS image and kernel where possible** (Ubuntu 24.04 everywhere); bench.sh records OS, kernel, fs and I/O scheduler.
3. **Fresh VM, nothing else running.** On hosts we own, `fstrim` (or `blkdiscard` a test device) before the run.
   bench.sh pre-fills the test file with real data, so thin-provisioned zero blocks do not inflate reads.
4. **At least 3 repeats, report the median** (3 x `standard`, or `full` which repeats each fio job 3 times).
5. **Time of day:** shared clouds vary; run in the same IST window as the BookMyHost baseline and publish the
   start time (`run.json` stores IST and UTC). Ideally repeat once at a different time of day.
6. **Local vs network storage:** say it in the post. EBS, Persistent Disk, Managed Disk, Oracle Block Volume
   and similar are network storage even when the guest sees an NVMe device; QD1 latency shows the difference.
7. **Steal probe:** `sysinfo.json` stores a 5 s steal baseline and the probe samples steal every second.
   Above ~2 % sustained, the CPU numbers do not represent the plan: note it, re-run later or discard.
8. **Check RAM** (`ram_mib` in `sysinfo.json`) against the plan for ballooning/overcommit.
9. **Burst credits / IOPS caps:** look at the probe spread; burst-then-throttle clouds look good for the first
   minutes only. Note any provider IOPS/throughput cap for the disk size chosen.
10. **Quote QD1 and QD32, and p99/p99.9**, never mean latency alone. `direct=1` bypasses the guest page cache
    but not a host cache, so QD1 latency is the number that is hard to fake.
11. **Architecture:** do not compare Arm (Oracle A1) CPU scores 1:1 with x86; disk numbers are still comparable.
12. **Publish the raw run directories** with the post, and state that one run describes that VM on that day,
    not the provider in general.
