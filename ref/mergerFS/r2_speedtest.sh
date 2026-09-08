#!/bin/bash
#
# Benchmarks whether the R2 cold tier (via GeeseFS) can sustain video streaming.
# Tests: write, cold sequential read, seek/scrub latency, and concurrent streams.
#
# Usage:
#   ./r2_speedtest.sh                          # defaults: 2GB file, 1 stream
#   ./r2_speedtest.sh --size 4096 --streams 3  # 4GB file, simulate 3 concurrent streams
#   ./r2_speedtest.sh --keep                   # don't delete test files afterward
#
# IMPORTANT: this measures COLD reads (bypassing GeeseFS's local cache) since
# that's what real playback of aged-out media will experience. If you just
# wrote the test file, GeeseFS's local --cache dir will make reads look
# artificially fast unless cleared first — this script clears it for you.

set -uo pipefail

R2_MOUNT="/mnt/r2_emby"
TEST_DIR="$R2_MOUNT/_speedtest"
GEESEFS_CACHE="/tmp/cache"

SIZE_MB=2048
STREAMS=1
KEEP=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --size) SIZE_MB="$2"; shift 2 ;;
        --streams) STREAMS="$2"; shift 2 ;;
        --keep) KEEP=true; shift ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if ! [[ "$SIZE_MB" =~ ^[0-9]+$ ]] || ! [[ "$STREAMS" =~ ^[0-9]+$ ]]; then
    echo "Error: --size and --streams must be positive integers." >&2
    exit 1
fi

if ! mountpoint -q "$R2_MOUNT"; then
    echo "Error: $R2_MOUNT is not mounted." >&2
    exit 1
fi

human() {
    numfmt --to=iec-i --suffix=B/s "$1" 2>/dev/null || echo "${1} B/s"
}

mbps_from_bytes_per_sec() {
    # bytes/sec -> megabits/sec
    echo "scale=1; ($1 * 8) / 1000000" | bc
}

echo "================================================================"
echo " R2 Cold-Tier Streaming Benchmark - $(date '+%Y-%m-%d %H:%M:%S')"
echo " Test file size : ${SIZE_MB} MB each"
echo " Concurrent streams: $STREAMS"
echo "================================================================"

mkdir -p "$TEST_DIR"

# --- Step 1: Write test file(s) ---
echo ""
echo "-- Write test (uploading to R2) --"
for i in $(seq 1 "$STREAMS"); do
    f="$TEST_DIR/testfile_$i.bin"
    if [[ ! -f "$f" ]]; then
        start=$(date +%s.%N)
        dd if=/dev/urandom of="$f" bs=1M count="$SIZE_MB" status=none
        end=$(date +%s.%N)
        elapsed=$(echo "$end - $start" | bc)
        bytes=$((SIZE_MB * 1024 * 1024))
        rate=$(echo "scale=0; $bytes / $elapsed" | bc)
        echo "  File $i: wrote ${SIZE_MB}MB in ${elapsed}s -> $(human "$rate") ($(mbps_from_bytes_per_sec "$rate") Mbps)"
    else
        echo "  File $i already exists, skipping write."
    fi
done

# --- Step 2: Clear caches so reads are truly cold ---
echo ""
echo "-- Clearing caches for a true cold-read test --"
if [[ -d "$GEESEFS_CACHE" ]]; then
    rm -rf "${GEESEFS_CACHE:?}"/* 2>/dev/null
    echo "  Cleared GeeseFS local cache at $GEESEFS_CACHE"
fi
if [[ -w /proc/sys/vm/drop_caches ]]; then
    sync
    echo 3 > /proc/sys/vm/drop_caches 2>/dev/null && echo "  Dropped Linux page cache" \
        || echo "  Could not drop page cache (try running as root)"
else
    echo "  Skipping page cache drop (need root)"
fi
echo "  Note: GeeseFS also keeps in-memory metadata/readahead state; for a fully"
echo "  cold test, consider 'sudo systemctl restart geesefs-r2.service' (or"
echo "  remount if using fstab) before re-running this script."

# --- Step 3: Sequential cold read test (single stream) ---
echo ""
echo "-- Sequential read test (simulates linear playback) --"
f="$TEST_DIR/testfile_1.bin"
start=$(date +%s.%N)
dd if="$f" of=/dev/null bs=1M status=none
end=$(date +%s.%N)
elapsed=$(echo "$end - $start" | bc)
bytes=$((SIZE_MB * 1024 * 1024))
rate=$(echo "scale=0; $bytes / $elapsed" | bc)
mbps=$(mbps_from_bytes_per_sec "$rate")
echo "  Read ${SIZE_MB}MB in ${elapsed}s -> $(human "$rate") (${mbps} Mbps)"
echo "  For reference: 4K remux needs ~60-100 Mbps, 4K H.265 ~25-40 Mbps, 1080p ~8-10 Mbps"

# --- Step 4: Seek / scrub latency test ---
echo ""
echo "-- Seek latency test (simulates scrubbing/resume) --"
seek_total=0
seek_count=5
for i in $(seq 1 "$seek_count"); do
    offset_mb=$(( (SIZE_MB * i) / (seek_count + 1) ))
    start=$(date +%s.%N)
    dd if="$f" of=/dev/null bs=1M skip="$offset_mb" count=8 status=none 2>/dev/null
    end=$(date +%s.%N)
    elapsed=$(echo "$end - $start" | bc)
    seek_total=$(echo "$seek_total + $elapsed" | bc)
    echo "  Seek to ${offset_mb}MB -> first 8MB in ${elapsed}s"
done
avg_seek=$(echo "scale=3; $seek_total / $seek_count" | bc)
echo "  Average seek-to-first-byte: ${avg_seek}s"
echo "  Under ~1-2s is generally fine for Emby seeking/scrubbing; 3s+ will feel laggy."

# --- Step 5: Concurrent stream test ---
if [[ "$STREAMS" -gt 1 ]]; then
    echo ""
    echo "-- Concurrent read test ($STREAMS simultaneous streams) --"
    start=$(date +%s.%N)
    pids=()
    for i in $(seq 1 "$STREAMS"); do
        dd if="$TEST_DIR/testfile_$i.bin" of=/dev/null bs=1M status=none &
        pids+=("$!")
    done
    for pid in "${pids[@]}"; do
        wait "$pid"
    done
    end=$(date +%s.%N)
    elapsed=$(echo "$end - $start" | bc)
    total_bytes=$((SIZE_MB * 1024 * 1024 * STREAMS))
    agg_rate=$(echo "scale=0; $total_bytes / $elapsed" | bc)
    agg_mbps=$(mbps_from_bytes_per_sec "$agg_rate")
    per_stream_mbps=$(echo "scale=1; $agg_mbps / $STREAMS" | bc)
    echo "  $STREAMS streams finished in ${elapsed}s"
    echo "  Aggregate throughput: $(human "$agg_rate") (${agg_mbps} Mbps)"
    echo "  Effective per-stream : ~${per_stream_mbps} Mbps"
fi

echo ""
echo "================================================================"
echo " Benchmark complete."
echo "================================================================"

if ! $KEEP; then
    rm -rf "$TEST_DIR"
    echo "Test files removed. Re-run with --keep to preserve them for repeat testing."
else
    echo "Test files kept at $TEST_DIR"
fi