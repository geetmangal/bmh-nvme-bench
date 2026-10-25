#!/usr/bin/env bash
# bmh-nvme-bench — reproducible NVMe / CPU / memory / network benchmark orchestrator.
# Maintained by BookMyHost engineering (https://bookmyhost.com/blog). MIT licence.
#
# Usage: ./bench.sh [--profile quick|standard|full] [--target DIR] [--size 4G] [--runtime 60]
#                   [--label NAME] [--provider NAME] [--plan-price-inr N] [--skip cpu,mem,net,disk]
#                   [--iperf-server HOST] [--out DIR] [--dry-run] [--no-prompt] [--keep-file]
set -Eeuo pipefail

BENCH_VERSION="0.1.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# ---------- colours (NO_COLOR aware) ----------
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  C_RESET=$'\e[0m'; C_BOLD=$'\e[1m'; C_GREEN=$'\e[32m'; C_YELLOW=$'\e[33m'; C_RED=$'\e[31m'; C_BLUE=$'\e[34m'
else
  C_RESET=""; C_BOLD=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BLUE=""
fi
info()  { printf '%s[bench]%s %s\n' "$C_BLUE" "$C_RESET" "$*"; }
ok()    { printf '%s[ ok ]%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn()  { printf '%s[warn]%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
die()   { printf '%s[fail]%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; exit "${2:-1}"; }

# ---------- defaults ----------
PROFILE="standard"
TARGET="./bench-tmp"
OPT_SIZE=""; OPT_RUNTIME=""
LABEL=""
PROVIDER="unknown"
PLAN_PRICE_INR=""
SKIP=""
IPERF_SERVER=""
OUT=""
DRY_RUN=0
NO_PROMPT=0
KEEP_FILE=0

usage() {
  sed -n '2,8p' "${BASH_SOURCE[0]:-$0}" | sed 's/^# \{0,1\}//'
  cat <<EOF

Options:
  --profile P         quick | standard | full (default: standard)
  --target DIR        directory holding the fio test file (default: ./bench-tmp)
  --size S            fio file size, e.g. 4G (profile default)
  --runtime N         seconds per fio job (profile default)
  --label NAME        run label, e.g. bmh-nvme-noida-vm-4c8g (default: hostname-profile)
  --provider NAME     provider name recorded in run.json (bookmyhost, hetzner, ...)
  --plan-price-inr N  monthly plan price in INR, enables INR-per-10k-IOPS in compare
  --skip LIST         comma list of cpu,mem,net,disk,probe,extras to skip
  --iperf-server HOST iperf3 server (network test skipped without it)
  --out DIR           output dir (default: results/<label>-<ts>/)
  --dry-run           print the command plan, run nothing heavy
  --no-prompt         do not ask for confirmation before writing the test file
  --keep-file         keep the fio test file after the run
  -h, --help          this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2;;
    --target) TARGET="$2"; shift 2;;
    --size) OPT_SIZE="$2"; shift 2;;
    --runtime) OPT_RUNTIME="$2"; shift 2;;
    --label) LABEL="$2"; shift 2;;
    --provider) PROVIDER="$2"; shift 2;;
    --plan-price-inr) PLAN_PRICE_INR="$2"; shift 2;;
    --skip) SKIP="$2"; shift 2;;
    --iperf-server) IPERF_SERVER="$2"; shift 2;;
    --out) OUT="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    --no-prompt) NO_PROMPT=1; shift;;
    --keep-file) KEEP_FILE=1; shift;;
    -h|--help) usage; exit 0;;
    *) usage; die "unknown option: $1" 1;;
  esac
done

case "$PROFILE" in quick|standard|full) ;; *) die "--profile must be quick, standard or full" 1;; esac
# Piped install (curl ... | bash): profiles and fio jobs are not next to us; fetch the repo tarball once.
if [[ ! -d "$SCRIPT_DIR/profiles" || ! -d "$SCRIPT_DIR/fio" ]]; then
  CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/bmh-nvme-bench"
  if [[ ! -f "$CACHE_DIR/bench.sh" ]]; then
    command -v curl >/dev/null 2>&1 || die "profiles/ not found next to bench.sh and curl is missing; use: git clone https://github.com/geetmangal/bmh-nvme-bench" 2
    info "fetching bmh-nvme-bench into $CACHE_DIR"
    mkdir -p "$CACHE_DIR"
    curl -fsSL "${BMH_BENCH_TARBALL:-https://github.com/geetmangal/bmh-nvme-bench/archive/refs/heads/main.tar.gz}" \
      | tar -xz -C "$CACHE_DIR" --strip-components=1 || die "download failed; use git clone instead" 2
  fi
  SCRIPT_DIR="$CACHE_DIR"
  RESULTS_BASE="$PWD/results"   # results still go under the caller's directory
fi
RESULTS_BASE="${RESULTS_BASE:-$SCRIPT_DIR/results}"
PROFILE_FILE="$SCRIPT_DIR/profiles/$PROFILE.conf"
[[ -f "$PROFILE_FILE" ]] || die "profile file missing: $PROFILE_FILE" 1
# shellcheck source=profiles/standard.conf
source "$PROFILE_FILE"
SIZE="${OPT_SIZE:-$SIZE}"
RUNTIME="${OPT_RUNTIME:-$RUNTIME}"
[[ "$RUNTIME" =~ ^[0-9]+$ ]] || die "--runtime must be an integer number of seconds" 1
[[ "$SIZE" =~ ^[0-9]+[KMGT]?$ ]] || die "--size must look like 4G / 512M" 1

skip_has() { [[ ",$SKIP," == *",$1,"* ]]; }

HOSTNAME_SHORT="$(hostname -s 2>/dev/null || hostname)"
[[ -n "$LABEL" ]] || LABEL="${HOSTNAME_SHORT}-${PROFILE}"
LABEL="${LABEL//[^A-Za-z0-9._-]/_}"
TS_IST="$(TZ=Asia/Kolkata date +%Y-%m-%dT%H:%M:%S%z)"
TS_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TS_FILE="$(TZ=Asia/Kolkata date +%Y%m%d-%H%M%S)"
[[ -n "$OUT" ]] || OUT="$RESULTS_BASE/${LABEL}-${TS_FILE}"

# ---------- cleanup trap ----------
CHILD_PIDS=()
TEST_FILE=""
cleanup() {
  local rc=$?
  for p in "${CHILD_PIDS[@]:-}"; do [[ -n "$p" ]] && kill "$p" 2>/dev/null || true; done
  if [[ $KEEP_FILE -eq 0 && -n "$TEST_FILE" && -f "$TEST_FILE" ]]; then
    rm -f "$TEST_FILE" "$TEST_FILE".* 2>/dev/null || true
  fi
  if [[ $rc -ne 0 ]]; then warn "exited with status $rc (partial results in $OUT)"; fi
}
trap cleanup EXIT
trap 'die "interrupted" 130' INT TERM

# ---------- dependency checks ----------
have() { command -v "$1" >/dev/null 2>&1; }
MISSING=()
check_deps() {
  local fio_ver
  if have fio; then
    fio_ver="$(fio --version 2>/dev/null | sed 's/^fio-//')"
    [[ "${fio_ver%%.*}" =~ ^[0-9]+$ && "${fio_ver%%.*}" -ge 3 ]] || warn "fio $fio_ver found; 3.x recommended"
  else MISSING+=(fio); fi
  have sysbench || MISSING+=(sysbench)
  have jq || MISSING+=(jq)
  have python3 || MISSING+=(python3)
  have iperf3 || warn "iperf3 not installed: network throughput test will be skipped"
  have nvme || warn "nvme-cli not installed: nvme smart-log will be skipped"
  if [[ ${#MISSING[@]} -gt 0 ]]; then
    warn "missing tools: ${MISSING[*]}"
    warn "install: sudo apt-get install -y fio sysbench iperf3 jq python3 nvme-cli    # Debian/Ubuntu"
    warn "         sudo dnf install -y fio sysbench iperf3 jq python3 nvme-cli        # RHEL/Alma/Rocky"
    [[ $DRY_RUN -eq 1 ]] || die "cannot run without: ${MISSING[*]}" 2
  fi
}
check_deps

# ---------- target checks ----------
check_target() {
  local abs fstype
  [[ "$TARGET" != "/" ]] || die "--target / is refused; point it at a directory on the disk under test" 1
  if ! mkdir -p "$TARGET" 2>/dev/null; then
    [[ $DRY_RUN -eq 1 ]] || die "cannot create $TARGET" 1
    warn "cannot create $TARGET (dry-run continues)"; return
  fi
  abs="$(cd "$TARGET" && pwd -P)"
  TARGET="$abs"
  if have findmnt; then
    fstype="$(findmnt -n -o FSTYPE -T "$TARGET" 2>/dev/null || true)"
    [[ -n "$fstype" ]] || die "$TARGET is not on any mounted filesystem" 1
    case "$fstype" in
      tmpfs|ramfs) die "$TARGET is on $fstype (RAM) — that would benchmark memory, not disk" 1;;
      overlay|9p|drvfs|fuse*) warn "$TARGET is on $fstype; numbers will not reflect the raw NVMe";;
    esac
  fi
  TEST_FILE="$TARGET/bench.file"
  local free_kb need_kb
  free_kb="$(df -Pk "$TARGET" | awk 'NR==2{print $4}')"
  need_kb="$(size_to_kb "$SIZE")"
  if [[ "$free_kb" -lt $((need_kb + 262144)) ]]; then
    [[ $DRY_RUN -eq 1 ]] || die "not enough free space in $TARGET for a $SIZE test file" 1
    warn "only $((free_kb/1024)) MiB free in $TARGET, need $((need_kb/1024)) MiB"
  fi
}
size_to_kb() {
  local n="${1%[KMGT]}" u="${1: -1}"
  case "$u" in
    K) echo "$n";; M) echo $((n*1024));; G) echo $((n*1024*1024));; T) echo $((n*1024*1024*1024));;
    *) echo $((n/1024));;
  esac
}
check_target

# ---------- run helpers ----------
run_cmd() {
  # run_cmd <outfile|-> <cmd...>; records the command in commands.log
  local out="$1"; shift
  printf '%s\n' "$*" >> "$OUT/commands.log"
  if [[ $DRY_RUN -eq 1 ]]; then
    printf '%s[plan]%s %s' "$C_BOLD" "$C_RESET" "$*"
    [[ "$out" == "-" ]] || printf '  -> %s' "${out#"$OUT"/}"
    printf '\n'
    return 0
  fi
  if [[ "$out" == "-" ]]; then
    "$@"
  elif "$@" > "$out" 2> "$out.stderr"; then
    [[ -s "$out.stderr" ]] || rm -f "$out.stderr"
  else
    warn "command failed (see $out.stderr): $*"
  fi
}

mkdir -p "$OUT"/{fio,sysbench,net,probe,extras}
: > "$OUT/commands.log"
info "bmh-nvme-bench v$BENCH_VERSION  profile=$PROFILE  label=$LABEL"
info "target=$TARGET  size=$SIZE  runtime=${RUNTIME}s  out=$OUT"
[[ $DRY_RUN -eq 1 ]] && info "DRY RUN: nothing heavy will be executed"

if [[ $DRY_RUN -eq 0 && $NO_PROMPT -eq 0 && -t 0 ]]; then
  printf 'This will write a %s file to %s and load the machine for several minutes. Continue? [y/N] ' "$SIZE" "$TARGET"
  read -r ans; [[ "$ans" =~ ^[Yy] ]] || die "aborted by user" 1
fi

# ---------- system facts ----------
collect_sysinfo() {
  info "collecting system facts -> sysinfo.json"
  local cpu_model cores threads sockets mhz ram_kb kernel virt distro disk_dev disk_model sched rot fstype mount steal
  cpu_model="$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | sed 's/^ *//' || echo unknown)"
  threads="$(nproc 2>/dev/null || echo 0)"
  cores="$(lscpu -p=CORE 2>/dev/null | grep -v '^#' | sort -u | wc -l || echo "$threads")"
  sockets="$(lscpu 2>/dev/null | awk -F: '/^Socket\(s\)/{gsub(/ /,"",$2);print $2}' || echo 1)"
  mhz="$(grep -m1 'cpu MHz' /proc/cpuinfo | awk -F: '{gsub(/ /,"",$2);print $2}' || echo 0)"
  ram_kb="$(awk '/MemTotal/{print $2}' /proc/meminfo)"
  kernel="$(uname -r)"
  virt="$(systemd-detect-virt 2>/dev/null || echo unknown)"
  distro="$(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-unknown}")"
  mount="$(findmnt -n -o TARGET -T "$TARGET" 2>/dev/null || echo unknown)"
  fstype="$(findmnt -n -o FSTYPE -T "$TARGET" 2>/dev/null || echo unknown)"
  disk_dev="$(findmnt -n -o SOURCE -T "$TARGET" 2>/dev/null | sed 's/\[.*\]//' || echo unknown)"
  local base; base="$(lsblk -no PKNAME "$disk_dev" 2>/dev/null | head -1 || true)"
  [[ -n "$base" ]] || base="$(basename "$disk_dev" 2>/dev/null || echo unknown)"
  disk_model="$(cat "/sys/block/$base/device/model" 2>/dev/null | sed 's/ *$//' || echo unknown)"
  sched="$(cat "/sys/block/$base/queue/scheduler" 2>/dev/null || echo unknown)"
  rot="$(cat "/sys/block/$base/queue/rotational" 2>/dev/null || echo unknown)"
  lscpu > "$OUT/extras/lscpu.txt" 2>/dev/null || true
  grep -m1 '^flags' /proc/cpuinfo | cut -d: -f2- > "$OUT/extras/cpuflags.txt" 2>/dev/null || true
  uname -a > "$OUT/extras/uname.txt" 2>/dev/null || true
  cat /proc/cpuinfo > "$OUT/extras/cpuinfo.txt" 2>/dev/null || true
  if have nvme && [[ "$base" == nvme* ]]; then
    nvme smart-log "/dev/$base" -o json > "$OUT/extras/nvme-smart-log.json" 2>/dev/null || warn "nvme smart-log needs root; skipped"
  fi
  # steal baseline: sample /proc/stat over 5 s (1 s in dry-run)
  local secs=5; [[ $DRY_RUN -eq 1 ]] && secs=1
  steal="$(steal_pct "$secs")"
  jq -n \
    --arg cpu_model "$cpu_model" --argjson cores "${cores:-0}" --argjson threads "${threads:-0}" --argjson sockets "${sockets:-1}" \
    --arg mhz "$mhz" --argjson ram_mib "$((ram_kb/1024))" --arg kernel "$kernel" --arg virt "$virt" --arg distro "$distro" \
    --arg hostname "$HOSTNAME_SHORT" --arg disk_dev "$disk_dev" --arg disk_model "$disk_model" --arg scheduler "$sched" \
    --arg rotational "$rot" --arg fstype "$fstype" --arg mount "$mount" --arg steal "$steal" \
    --arg flags "$(cat "$OUT/extras/cpuflags.txt" 2>/dev/null | tr -s ' ' | sed 's/^ //')" \
    '{cpu:{model:$cpu_model,cores:$cores,threads:$threads,sockets:$sockets,mhz:($mhz|tonumber? // 0),flags:($flags|split(" "))},
      ram_mib:$ram_mib, kernel:$kernel, virt:$virt, distro:$distro, hostname:$hostname,
      disk:{device:$disk_dev,model:$disk_model,scheduler:$scheduler,rotational:($rotational=="1"),fstype:$fstype,mount:$mount},
      steal_baseline_pct:($steal|tonumber? // 0)}' > "$OUT/sysinfo.json"
}
steal_pct() {
  # prints steal % over N seconds
  local n="$1" a b
  a="$(head -1 /proc/stat)"; sleep "$n"; b="$(head -1 /proc/stat)"
  awk -v a="$a" -v b="$b" 'BEGIN{na=split(a,x," ");nb=split(b,y," ");ta=0;tb=0;for(i=2;i<=na;i++){ta+=x[i];tb+=y[i]}; d=tb-ta; if(d<=0){print 0}else{printf "%.3f",(y[9]-x[9])*100/d}}'
}
collect_sysinfo

# ---------- fio ----------
export TARGET SIZE RUNTIME
fio_job() {
  # fio_job <name> <jobfile> RW BS IODEPTH NUMJOBS [extra env assignments...]
  local name="$1" jobfile="$2"; export RW="$3" BS="$4" IODEPTH="$5" NUMJOBS="$6" JOBNAME="$1"; shift 6
  local r out
  for ((r=1; r<=REPEATS; r++)); do
    out="$OUT/fio/$name.json"; [[ $r -gt 1 ]] && out="$OUT/fio/$name.r$r.json"
    run_cmd "$out" env "$@" RW="$RW" BS="$BS" IODEPTH="$IODEPTH" NUMJOBS="$NUMJOBS" JOBNAME="$name" fio --output-format=json "$SCRIPT_DIR/fio/$jobfile"
  done
}
disk_tests() {
  info "disk: pre-filling $SIZE test file (real writes, not fallocate)"
  run_cmd "$OUT/fio/prefill.json" fio --output-format=json "$SCRIPT_DIR/fio/prefill.fio"
  info "disk: random 4k"
  fio_job 4k-randread-qd1   rand.fio randread  4k 1  1
  fio_job 4k-randread-qd32  rand.fio randread  4k 32 "$NUMJOBS_RAND"
  [[ -n "${EXTRA_QD:-}" ]] && fio_job "4k-randread-qd$EXTRA_QD" rand.fio randread 4k "$EXTRA_QD" "$NUMJOBS_RAND"
  fio_job 4k-randwrite-qd1  rand.fio randwrite 4k 1  1
  fio_job 4k-randwrite-qd32 rand.fio randwrite 4k 32 "$NUMJOBS_RAND"
  fio_job 4k-randrw70-qd32  mixed.fio randrw   4k 32 "$NUMJOBS_RAND" RWMIXREAD=70
  info "disk: sequential"
  fio_job 64k-seqread   seq.fio read  64k "$QD_SEQ" "$NUMJOBS_SEQ"
  fio_job 64k-seqwrite  seq.fio write 64k "$QD_SEQ" "$NUMJOBS_SEQ"
  fio_job 1m-seqread    seq.fio read  1M  "$QD_SEQ" "$NUMJOBS_SEQ"
  fio_job 1m-seqwrite   seq.fio write 1M  "$QD_SEQ" "$NUMJOBS_SEQ"
  info "disk: latency (4k randread QD1, lat_percentiles)"
  fio_job 4k-randread-lat-qd1 latency.fio randread 4k 1 1
  if [[ "${FSYNC_TEST:-1}" == "1" ]]; then
    info "disk: fsync latency (4k write, fsync=1)"
    fio_job 4k-fsync-write fsync.fio write 4k 1 1
  fi
}
if skip_has disk; then info "disk tests skipped"; else disk_tests; fi

# ---------- CPU / memory ----------
cpu_tests() {
  local nt; nt="$(nproc)"
  info "cpu: sysbench cpu-max-prime=20000 (1 thread, $nt threads)"
  run_cmd "$OUT/sysbench/cpu-1t.txt" sysbench cpu --cpu-max-prime=20000 --threads=1 --time="$SB_TIME" run
  run_cmd "$OUT/sysbench/cpu-nt.txt" sysbench cpu --cpu-max-prime=20000 --threads="$nt" --time="$SB_TIME" run
}
mem_tests() {
  info "mem: sysbench memory read/write"
  run_cmd "$OUT/sysbench/mem-read.txt"  sysbench memory --memory-block-size=1M --memory-total-size=20G --memory-oper=read  --threads=1 --time="$SB_TIME" run
  run_cmd "$OUT/sysbench/mem-write.txt" sysbench memory --memory-block-size=1M --memory-total-size=20G --memory-oper=write --threads=1 --time="$SB_TIME" run
}
extras_tests() {
  if have openssl; then
    info "extras: openssl speed aes-256-gcm"
    run_cmd "$OUT/extras/openssl.txt" openssl speed -evp aes-256-gcm -seconds 3
  fi
  info "extras: pure-python loop sanity score"
  run_cmd "$OUT/extras/pyloop.txt" python3 -c 'import time; t=time.perf_counter(); s=0
for i in range(10_000_000): s+=i*i%7
d=time.perf_counter()-t; print(f"pyloop_seconds={d:.3f} score={10_000_000/d/1e6:.2f} Mops/s")'
}
if skip_has cpu; then info "cpu tests skipped"; else cpu_tests; fi
if skip_has mem; then info "mem tests skipped"; else mem_tests; fi
if skip_has extras; then info "extras skipped"; else extras_tests; fi

# ---------- network ----------
net_tests() {
  if have iperf3 && [[ -n "$IPERF_SERVER" ]]; then
    info "net: iperf3 -> $IPERF_SERVER (4 streams, 10 s, both directions)"
    run_cmd "$OUT/net/iperf3-up.json"   iperf3 -c "$IPERF_SERVER" -P 4 -t 10 -J
    run_cmd "$OUT/net/iperf3-down.json" iperf3 -c "$IPERF_SERVER" -P 4 -t 10 -J -R
    run_cmd "$OUT/net/ping-iperf.txt" ping -c 20 -i 0.2 "$IPERF_SERVER"
  else
    info "net: no --iperf-server or iperf3 missing; throughput skipped"
  fi
  info "net: ping 1.1.1.1 (20 packets)"
  run_cmd "$OUT/net/ping-1.1.1.1.txt" ping -c 20 -i 0.2 1.1.1.1
  if have curl; then
    info "net: curl TTFB x5 bookmyhost.com / google.com"
    local u
    for u in https://bookmyhost.com https://www.google.com; do
      local host f
      host="${u#https://}"; host="${host//[^A-Za-z0-9.]/_}"
      f="$OUT/net/curl-ttfb-$host.txt"
      # shellcheck disable=SC2016  # $1 expands in the child bash, not here
      run_cmd "$f" bash -c 'for i in 1 2 3 4 5; do curl -o /dev/null -s -w "%{url_effective} ttfb=%{time_starttransfer} connect=%{time_connect} tls=%{time_appconnect} http=%{http_code}\n" --max-time 15 "$1"; done' _ "$u"
    done
  fi
}
if skip_has net; then info "net tests skipped"; else net_tests; fi

# ---------- noisy-neighbour probe ----------
probe_tests() {
  info "probe: ${PROBE_SECS}s steal%/latency loop (fio 4k QD1 sample every 10 s)"
  if [[ $DRY_RUN -eq 1 ]]; then
    run_cmd "$OUT/probe/steal.csv" bash -c "for t in \$(seq 1 $PROBE_SECS); do <sample /proc/stat steal%>; done"
    run_cmd "$OUT/probe/lat-NN.json" env RW=randread BS=4k IODEPTH=1 NUMJOBS=1 JOBNAME=probe RUNTIME=5 fio --output-format=json "$SCRIPT_DIR/fio/probe.fio"
    return
  fi
  local t n=0 prev cur
  echo "t,steal_pct,idle_pct" > "$OUT/probe/steal.csv"
  prev="$(head -1 /proc/stat)"
  for ((t=1; t<=PROBE_SECS; t++)); do
    sleep 1
    cur="$(head -1 /proc/stat)"
    awk -v a="$prev" -v b="$cur" -v t="$t" 'BEGIN{na=split(a,x," ");split(b,y," ");ta=0;tb=0;for(i=2;i<=na;i++){ta+=x[i];tb+=y[i]}; d=tb-ta; if(d<=0)d=1; printf "%d,%.3f,%.3f\n",t,(y[9]-x[9])*100/d,(y[5]-x[5])*100/d}' >> "$OUT/probe/steal.csv"
    prev="$cur"
    if (( (t-1) % 10 == 0 )); then
      n=$((n+1))
      ( RW=randread BS=4k IODEPTH=1 NUMJOBS=1 JOBNAME=probe RUNTIME=5 fio --output-format=json "$SCRIPT_DIR/fio/probe.fio" > "$OUT/probe/lat-$(printf '%02d' "$n").json" 2>/dev/null ) &
      CHILD_PIDS+=($!)
    fi
  done
  wait
}
if skip_has probe; then info "probe skipped"; else probe_tests; fi

# ---------- manifest ----------
write_manifest() {
  local fio_v sb_v ip_v
  fio_v="$(fio --version 2>/dev/null || echo missing)"
  sb_v="$(sysbench --version 2>/dev/null || echo missing)"
  ip_v="$(iperf3 --version 2>/dev/null | head -1 || echo missing)"
  jq -n \
    --arg version "$BENCH_VERSION" --arg profile "$PROFILE" --arg label "$LABEL" --arg provider "$PROVIDER" \
    --arg price "$PLAN_PRICE_INR" --arg size "$SIZE" --argjson runtime "$RUNTIME" --arg target "$TARGET" \
    --arg ts_ist "$TS_IST" --arg ts_utc "$TS_UTC" --arg end_ist "$(TZ=Asia/Kolkata date +%Y-%m-%dT%H:%M:%S%z)" --arg end_utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg hostname "$HOSTNAME_SHORT" --arg skip "$SKIP" --arg iperf "$IPERF_SERVER" --argjson dry "$DRY_RUN" \
    --arg fio_v "$fio_v" --arg sb_v "$sb_v" --arg ip_v "$ip_v" --argjson repeats "${REPEATS:-1}" \
    --argjson numjobs_rand "$NUMJOBS_RAND" --argjson numjobs_seq "$NUMJOBS_SEQ" --argjson qd_seq "$QD_SEQ" --argjson probe_secs "$PROBE_SECS" \
    '{bench_version:$version, profile:$profile, label:$label, provider:$provider,
      plan_price_inr:($price|tonumber? // null), size:$size, runtime_s:$runtime, target:$target, repeats:$repeats,
      numjobs_rand:$numjobs_rand, numjobs_seq:$numjobs_seq, qd_seq:$qd_seq, probe_secs:$probe_secs,
      started_ist:$ts_ist, started_utc:$ts_utc, finished_ist:$end_ist, finished_utc:$end_utc,
      hostname:$hostname, skip:($skip|split(",")|map(select(.!=""))), iperf_server:$iperf, dry_run:($dry==1),
      tools:{fio:$fio_v, sysbench:$sb_v, iperf3:$ip_v}}' > "$OUT/run.json"
}
write_manifest
ok "raw results in $OUT"
if [[ $DRY_RUN -eq 0 ]] && have python3; then
  if python3 "$SCRIPT_DIR/report.py" "$OUT"; then ok "report: $OUT/summary.md"; else warn "report.py failed; raw data is intact"; fi
else
  info "next: python3 report.py $OUT"
fi
