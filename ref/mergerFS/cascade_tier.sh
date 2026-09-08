#!/bin/bash
#
# Nightly cascade tiering for Emby media.
# Usage:
#   ./cascade_tier.sh                                  # actually move files (full tree, default retention)
#   ./cascade_tier.sh --dry-run                        # report what WOULD move, no changes made
#   ./cascade_tier.sh --path _tiertest                  # scope to a subfolder (relative to HOT/WARM roots)
#   ./cascade_tier.sh --hot-days 14 --warm-days 90      # override retention periods
#   ./cascade_tier.sh --dry-run --path _tiertest --hot-days 14 --warm-days 90
#
# --hot-days   : age (in days) after which files move HOT -> WARM   (default: 30)
# --warm-days  : age (in days) after which files move WARM -> COLD  (default: 60)
# --path       : scope the scan to a subfolder relative to the HOT/WARM roots
# --dry-run    : report only, no files moved

set -uo pipefail

DRY_RUN=false
SCOPE=""
HOT_DAYS=30
WARM_DAYS=60

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --path) SCOPE="$2"; shift 2 ;;
        --hot-days) HOT_DAYS="$2"; shift 2 ;;
        --warm-days) WARM_DAYS="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# Validate retention values are positive integers
if ! [[ "$HOT_DAYS" =~ ^[0-9]+$ ]] || ! [[ "$WARM_DAYS" =~ ^[0-9]+$ ]]; then
    echo "Error: --hot-days and --warm-days must be positive integers." >&2
    exit 1
fi

# Define absolute paths
HOT="/mnt/hdd01/emby"
WARM="/mnt/nfs_emby"
COLD="/mnt/r2_emby"

# If --path given, scope search roots to that subfolder
HOT_SCAN="$HOT"
WARM_SCAN="$WARM"
if [[ -n "$SCOPE" ]]; then
    HOT_SCAN="$HOT/$SCOPE"
    WARM_SCAN="$WARM/$SCOPE"
fi

# Safety Check: Prevent data loops if mounts dropped
if ! mountpoint -q "$WARM" || ! mountpoint -q "$COLD"; then
    echo "Error: One of the remote storage tiers is unmounted. Aborting lifecycle." >&2
    exit 1
fi

if [[ -n "$SCOPE" ]]; then
    if [[ ! -d "$HOT_SCAN" && ! -d "$WARM_SCAN" ]]; then
        echo "Error: scoped path '$SCOPE' doesn't exist under HOT or WARM." >&2
        exit 1
    fi
fi

sum_bytes() {
    local total=0 f sz
    while IFS= read -r f; do
        [[ -f "$f" ]] || continue
        sz=$(stat -c '%s' "$f" 2>/dev/null || echo 0)
        total=$((total + sz))
    done
    echo "$total"
}

human() {
    numfmt --to=iec-i --suffix=B "$1" 2>/dev/null || echo "${1} bytes"
}

echo "================================================================"
echo " Cascade Tiering Report - $(date '+%Y-%m-%d %H:%M:%S')"
$DRY_RUN && echo " MODE: DRY RUN (no files will be moved)"
[[ -n "$SCOPE" ]] && echo " SCOPE: $SCOPE (relative to HOT/WARM roots)"
echo " RETENTION: HOT->WARM after ${HOT_DAYS}d, WARM->COLD after ${WARM_DAYS}d"
echo "================================================================"

# --- Step A: WARM (older than WARM_DAYS) -> COLD ---
mapfile -t warm_to_cold < <([[ -d "$WARM_SCAN" ]] && find "$WARM_SCAN" -type f -mtime "+$WARM_DAYS")
warm_count=${#warm_to_cold[@]}
warm_bytes=$(printf '%s\n' "${warm_to_cold[@]}" | sum_bytes)

echo ""
echo "-- WARM ($WARM_SCAN) -> COLD, files older than ${WARM_DAYS} days --"
echo "   Files to move : $warm_count"
echo "   Total size    : $(human "$warm_bytes")"
if [[ $warm_count -gt 0 ]]; then
    echo "   Sample files:"
    printf '     %s\n' "${warm_to_cold[@]:0:10}"
    [[ $warm_count -gt 10 ]] && echo "     ... and $((warm_count - 10)) more"
fi

# --- Step B: HOT (older than HOT_DAYS) -> WARM ---
mapfile -t hot_to_warm < <([[ -d "$HOT_SCAN" ]] && find "$HOT_SCAN" -type f -mtime "+$HOT_DAYS")
hot_count=${#hot_to_warm[@]}
hot_bytes=$(printf '%s\n' "${hot_to_warm[@]}" | sum_bytes)

echo ""
echo "-- HOT ($HOT_SCAN) -> WARM, files older than ${HOT_DAYS} days --"
echo "   Files to move : $hot_count"
echo "   Total size    : $(human "$hot_bytes")"
if [[ $hot_count -gt 0 ]]; then
    echo "   Sample files:"
    printf '     %s\n' "${hot_to_warm[@]:0:10}"
    [[ $hot_count -gt 10 ]] && echo "     ... and $((hot_count - 10)) more"
fi

echo ""
echo "================================================================"
echo " Totals: $((warm_count + hot_count)) files, $(human $((warm_bytes + hot_bytes)))"
echo "================================================================"

if $DRY_RUN; then
    echo ""
    echo "Dry run complete. No files were moved."
    exit 0
fi

# --- Actual migration (only runs without --dry-run) ---

# Step A: Move files older than WARM_DAYS from WARM (NFS) to COLD (R2 Cloud)
for file in "${warm_to_cold[@]}"; do
    relative_path="${file#$WARM/}"
    relative_dir=$(dirname "$relative_path")
    mkdir -p "$COLD/$relative_dir"
    mv "$file" "$COLD/$relative_path"
done

# Step B: Move files older than HOT_DAYS from HOT (Local ZFS) to WARM (NFS)
for file in "${hot_to_warm[@]}"; do
    relative_path="${file#$HOT/}"
    relative_dir=$(dirname "$relative_path")
    mkdir -p "$WARM/$relative_dir"
    mv "$file" "$WARM/$relative_path"
done

# Step C: Purge stale empty folders (only within scope, or full tree if unscoped)
find "$HOT_SCAN" -type d -empty -delete 2>/dev/null
find "$WARM_SCAN" -type d -empty -delete 2>/dev/null

echo "Migration complete."