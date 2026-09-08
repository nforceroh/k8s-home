#!/bin/bash
#
# Benchmarks read/write throughput and seek latency across the HOT, WARM,
# and COLD storage tiers, so you can compare them against each other and
# against the bitrate you need to sustain for streaming.
#
# Usage:
#   ./xferspeed.sh                          # test all 3 tiers, defaults
#   ./xferspeed.sh --tier cold              # test only the R2 cold tier
#   ./xferspeed.sh --tier hot,warm          # test a subset
#   ./xferspeed.sh --size 4096 --streams 3  # 4GB file, 3 concurrent streams
#   ./xferspeed.sh --keep                   # don't delete test files afterward
#
# IMPORTANT (COLD tier): this measures cold reads by clearing GeeseFS's local
# cache before reading. If you just wrote the test file, skipping this would
# make R2 look artificially fast since you'd just be reading local cache.
#
# Reference bitrates for comparison:
#   1080p H.264            8-10 Mbps    (~1.0-1.3 MB/s)
#   1080p remux/high-bitrate  20-35 Mbps   (~2.5-4.4 MB/s)
#   4K H.265                25-40 Mbps   (~3.1-5.0 MB/s)
#   4K remux (UHD)           60-100+ Mbps (~7.5-12.5+ MB/s)

set -uo pipefail

declare -A TIER_PATH=(
    [hot]="/mnt/hdd01/emby"
    [warm]="/mnt/nfs_emby"
    [cold]="/mnt/r2_emby"
)
declare -A TIER_LABEL=(
    [hot]="HOT (local ZFS)"
    [warm]="WARM (NFS)"
    [cold]="COLD (R2 via GeeseFS)"
)

GEESEFS_CACHE="/tmp/cache"
SIZE_MB=2048
STREAMS=1
KEEP=false
TIERS_ARG="hot,warm,cold"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tier) TIERS_ARG="$2"; shift 2 ;;
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

IFS=',' read -ra TIERS <<< "$TIERS_ARG"
for t in "${TIERS[@]}"; do
    if [[ -z "${TIER_PATH[$t]:-}" ]]; then
        echo "Error: unknown tier '$t'. Valid tiers: hot, warm, cold." >&2
        exit 1
    fi
done

human() {
    numfmt --to=iec-i --suffix=B/s "$1" 2>/dev/null || echo "${1} B/s"
}

mbps_from_bytes_per_sec() {
    echo "scale=1; ($1 * 8) / 1000000" | bc
}

# Results storage for final summary table
declare -A RESULT_WRITE_MBPS
declare -A RESULT_READ_MBPS
declare -A RESULT_SEEK_AVG
declare -A RESULT_CONCURRENT_MBPS

test_tier() {
    local tier="$1"
    local path="${TIER_PATH[$tier]}"
    local label="${TIER_LABEL[$tier]}"
    local test_dir="$path/_speedtest"

    echo ""
    echo "================================================================"
    echo " Testing tier: $label"
    echo " Path: $path"
    echo "================================================================"

    if ! mountpoint -q "$path" 2>/dev/null && [[ "$tier" != "hot" ]]; then
        echo "  WARNING: $path is not a mountpoint. Skipping $label." >&2
        return
    fi
    if [[ ! -d "$path" ]]; then
        echo "  WARNING: $path does not exist. Skipping $label." >&2
        return
    fi

    mkdir -p "$test_dir"

    # --- Write test ---
    echo ""
    echo "-- Write test --"
    local total_write_bytes=0
    local write_start=$(date +%s.%N)
    for i in $(seq 1 "$STREAMS"); do
        dd if=/dev/urandom of="$test_dir/testfile_$i.bin" bs=1M count="$SIZE_MB" status=none
    done
    local write_end=$(date +%s.%N)
    local write_elapsed=$(echo "$write_end - $write_start" | bc)
    total_write_bytes=$((SIZE_MB * 1024 * 1024 * STREAMS))
    local write_rate=$(echo "scale=0; $total_write_bytes / $write_elapsed" | bc)
    local write_mbps=$(mbps_from_bytes_per_sec "$write_rate")
    RESULT_WRITE_MBPS[$tier]="$write_mbps"
    echo "  Wrote ${SIZE_MB}MB x $STREAMS in ${write_elapsed}s -> $(human "$write_rate") (${write_mbps} Mbps)"

    # --- Clear caches (only meaningful for COLD, harmless elsewhere) ---
    if [[ "$tier" == "cold" ]]; then
        echo ""
        echo "-- Clearing GeeseFS cache for a true cold-read test --"
        if [[ -d "$GEESEFS_CACHE" ]]; then
            rm -rf "${GEESEFS_CACHE:?}"/* 2>/dev/null
            echo "  Cleared $GEESEFS_CACHE"
        fi
        echo "  Note: for a fully cold test, restart/remount the R2 mount between runs"
        echo "  (GeeseFS retains some in-memory metadata state beyond the on-disk cache)."
    fi
    if [[ -w /proc/sys/vm/drop_caches ]]; then
        sync
        echo 3 > /proc/sys/vm/drop_caches 2>/dev/null
    fi

    # --- Sequential read test ---
    echo ""
    echo "-- Sequential read test --"
    local f="$test_dir/testfile_1.bin"
    local read_start=$(date +%s.%N)
    dd if="$f" of=/dev/null bs=1M status=none
    local read_end=$(date +%s.%N)
    local read_elapsed=$(echo "$read_end - $read_start" | bc)
    local read_bytes=$((SIZE_MB * 1024 * 1024))
    local read_rate=$(echo "scale=0; $read_bytes / $read_elapsed" | bc)
    local read_mbps=$(mbps_from_bytes_per_sec "$read_rate")
    RESULT_READ_MBPS[$tier]="$read_mbps"
    echo "  Read ${SIZE_MB}MB in ${read_elapsed}s -> $(human "$read_rate") (${read_mbps} Mbps)"

    # --- Seek/scrub latency test ---
    echo ""
    echo "-- Seek latency test (simulates scrubbing/resume) --"
    local seek_total=0
    local seek_count=5
    for i in $(seq 1 "$seek_count"); do
        local offset_mb=$(( (SIZE_MB * i) / (seek_count + 1) ))
        local s_start=$(date +%s.%N)
        dd if="$f" of=/dev/null bs=1M skip="$offset_mb" count=8 status=none 2>/dev/null
        local s_end=$(date +%s.%N)
        local s_elapsed=$(echo "$s_end - $s_start" | bc)
        seek_total=$(echo "$seek_total + $s_elapsed" | bc)
        echo "  Seek to ${offset_mb}MB -> first 8MB in ${s_elapsed}s"
    done
    local avg_seek=$(echo "scale=3; $seek_total / $seek_count" | bc)
    RESULT_SEEK_AVG[$tier]="$avg_seek"
    echo "  Average seek-to-first-byte: ${avg_seek}s"

    # --- Concurrent stream test ---
    if [[ "$STREAMS" -gt 1 ]]; then
        echo ""
        echo "-- Concurrent read test ($STREAMS simultaneous streams) --"
        local c_start=$(date +%s.%N)
        local pids=()
        for i in $(seq 1 "$STREAMS"); do
            dd if="$test_dir/testfile_$i.bin" of=/dev/null bs=1M status=none &
            pids+=("$!")
        done
        for pid in "${pids[@]}"; do
            wait "$pid"
        done
        local c_end=$(date +%s.%N)
        local c_elapsed=$(echo "$c_end - $c_start" | bc)
        local c_bytes=$((SIZE_MB * 1024 * 1024 * STREAMS))
        local c_rate=$(echo "scale=0; $c_bytes / $c_elapsed" | bc)
        local c_mbps=$(mbps_from_bytes_per_sec "$c_rate")
        RESULT_CONCURRENT_MBPS[$tier]="$c_mbps"
        echo "  $STREAMS streams finished in ${c_elapsed}s"
        echo "  Aggregate: $(human "$c_rate") (${c_mbps} Mbps) -> ~$(echo "scale=1; $c_mbps / $STREAMS" | bc) Mbps/stream"
    fi

    if ! $KEEP; then
        rm -rf "$test_dir"
    fi
}

echo "================================================================"
echo " Tiered Storage Transfer Speed Benchmark - $(date '+%Y-%m-%d %H:%M:%S')"
echo " Tiers: ${TIERS[*]}"
echo " Test file size: ${SIZE_MB} MB each, Streams: $STREAMS"
echo "================================================================"

for t in "${TIERS[@]}"; do
    test_tier "$t"
done

# --- Summary table ---
echo ""
echo "================================================================"
echo " SUMMARY"
echo "================================================================"
printf "%-25s %12s %12s %14s\n" "Tier" "Write Mbps" "Read Mbps" "Avg Seek (s)"
for t in "${TIERS[@]}"; do
    [[ -n "${RESULT_READ_MBPS[$t]:-}" ]] || continue
    printf "%-25s %12s %12s %14s\n" "${TIER_LABEL[$t]}" "${RESULT_WRITE_MBPS[$t]:-N/A}" "${RESULT_READ_MBPS[$t]:-N/A}" "${RESULT_SEEK_AVG[$t]:-N/A}"
done
if [[ "$STREAMS" -gt 1 ]]; then
    echo ""
    printf "%-25s %s\n" "Tier" "Aggregate Concurrent Mbps ($STREAMS streams)"
    for t in "${TIERS[@]}"; do
        [[ -n "${RESULT_CONCURRENT_MBPS[$t]:-}" ]] || continue
        printf "%-25s %s\n" "${TIER_LABEL[$t]}" "${RESULT_CONCURRENT_MBPS[$t]}"
    done
fi
echo ""
echo "Reference: 1080p ~8-10 Mbps | 1080p remux ~20-35 Mbps | 4K H.265 ~25-40 Mbps | 4K remux ~60-100+ Mbps"
echo "================================================================"

if ! $KEEP; then
    echo "Test files removed from all tested tiers."
else
    echo "Test files kept under _speedtest/ in each tested tier."
fi