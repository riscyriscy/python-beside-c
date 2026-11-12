#!/usr/bin/env bash
# Run each build with no Python on the PATH, and report size and start-up time.
# Run: bash check_exe.sh   (after build_exe.sh)
set -u
printf '123456789' > build/check.bin
targets=("build/exe/crc_tool" "build/exe_dir/crc_tool/crc_tool" "build/nuitka/crc_tool_nuitka" "build/crc_tool.pyz")
for t in "${targets[@]}"; do
    if [[ $t == build/exe_dir/* ]]; then
        size=$(du -sb "$(dirname "$t")" | cut -f1); what="(folder)"
    else
        size=$(stat -c %s "$t"); what=""
    fi
    echo "== $t  $(awk -v s="$size" 'BEGIN { if (s < 100000) print "under 0.1 MiB"; else printf "%.1f MiB\n", s / 1048576 }') $what"
    if [[ $t == *.pyz ]]; then run=(env PATH=/usr/bin "$t"); else run=(env -i PATH=/nonexistent "$t"); fi
    "${run[@]}" --version
    "${run[@]}" --self-test
    "${run[@]}" build/check.bin /nonexistent 2>&1; echo "exit status $?"
    start=$(date +%s.%N)
    for _ in $(seq 20); do "${run[@]}" --version > /dev/null; done
    end=$(date +%s.%N)
    echo "start-up: $(python3 -c "print(round(($end - $start) / 20 * 1000))") ms per run (mean of 20 runs of --version)"
done
