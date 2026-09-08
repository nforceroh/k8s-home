#!/bin/bash
#
# Nightly cascade tiering for Emby media.
# Usage:
#   ./cascade_tier.sh            # actually move files
#   ./cascade_tier.sh --dry-run  # report what WOULD move, no changes made

set -uo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

# Define absolute paths
HOT="/mnt/hdd01/emby"
WARM="/mnt/nfs_emby"
COLD="/mnt/r2_emby"

# Safety Check: Prevent data loops if mounts dropped
if ! mountpoint -q "$WARM" || ! mountpoint -q "$COLD"; then
    echo "Error: One of the remote storage tiers is unmounted. Aborting lifecycle." >&2
    exit 1
fi

# Helper: sum sizes (bytes) of a list of files from stdin
sum_bytes() {
    local total=0
    local f
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
echo "================================================================"

# --- Step A: WARM (61+ days old) -> COLD ---
mapfile -t warm_to_cold < <(find "$WARM" -type f -mtime +60)
warm_count=${#warm_to_cold[@]}
warm_bytes=$(printf '%s\n' "${warm_to_cold[@]}" | sum_bytes)

echo ""
echo "-- WARM ($WARM) -> COLD ($COLD), files older than 60 days --"
echo "   Files to move : $warm_count"
echo "   Total size    : $(human "$warm_bytes")"
if [[ $warm_count -gt 0 ]]; then
    echo "   Sample files:"
    printf '     %s\n' "${warm_to_cold[@]:0:10}"
    [[ $warm_count -gt 10 ]] && echo "     ... and $((warm_count - 10)) more"
fi

# --- Step B: HOT (31+ days old) -> WARM ---
mapfile -t hot_to_warm < <(find "$HOT" -type f -mtime +30)
hot_count=${#hot_to_warm[@]}
hot_bytes=$(printf '%s\n' "${hot_to_warm[@]}" | sum_bytes)

echo ""
echo "-- HOT ($HOT) -> WARM ($WARM), files older than 30 days --"
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

# Step A: Move files older than 60 days from WARM (NFS) to COLD (R2 Cloud)
for file in "${warm_to_cold[@]}"; do
    relative_path="${file#$WARM/}"
    relative_dir=$(dirname "$relative_path")
    mkdir -p "$COLD/$relative_dir"
    mv "$file" "$COLD/$relative_path"
done

# Step B: Move files older than 30 days from HOT (Local ZFS) to WARM (NFS)
for file in "${hot_to_warm[@]}"; do
    relative_path="${file#$HOT/}"
    relative_dir=$(dirname "$relative_path")
    mkdir -p "$WARM/$relative_dir"
    mv "$file" "$WARM/$relative_path"
done

# Step C: Purge stale empty folders across systems
find "$HOT" -type d -empty -delete 2>/dev/null
find "$WARM" -type d -empty -delete 2>/dev/null

echo "Migration complete."