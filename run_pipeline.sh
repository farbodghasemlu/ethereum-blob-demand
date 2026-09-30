#!/bin/bash
cd "$(dirname "$0")" || exit 1
export PAGE_CONCURRENCY="${PAGE_CONCURRENCY:-8}"
mkdir -p state
STEPS=("$@")
[ ${#STEPS[@]} -eq 0 ] && STEPS=(blobtxs blobstats celestia prices growthepie merge)
LONG=" headers blobtxs mempool "
CRITICAL=" headers blobtxs merge "
[ "${FORCE:-0}" = "1" ] && rm -f state/done_*
for step in "${STEPS[@]}"; do
  if [ -f "state/done_$step" ]; then echo "=== skip '$step', completed $(cat "state/done_$step") ==="; continue; fi
  if [[ "$LONG" == *" $step "* ]]; then max="${LONG_ATTEMPTS:-300}"; else max="${SHORT_ATTEMPTS:-3}"; fi
  ok=0
  for i in $(seq 1 "$max"); do
    echo "=== '$step' attempt $i/$max at $(date -Is) ==="
    npm run "$step"
    code=$?
    if [ $code -eq 0 ]; then ok=1; date -Is > "state/done_$step"; echo "=== '$step' done at $(date -Is) ==="; break; fi
    case $code in 129) why="SIGHUP";; 137) why="SIGKILL, check dmesg for OOM";; 143) why="SIGTERM";; *) why="error";; esac
    echo "=== '$step' exited $code ($why) at $(date -Is), $(df -h . | tail -1 | awk '{print $4}') free ==="
    [ $i -lt "$max" ] && sleep "${RETRY_SLEEP:-30}"
  done
  if [ $ok -eq 0 ]; then
    if [[ "$CRITICAL" == *" $step "* ]]; then echo "=== critical step '$step' failed $max times, stopping ==="; exit 1; fi
    echo "=== optional step '$step' failed $max times, continuing without it ==="
  fi
done
echo "=== pipeline finished at $(date -Is) ==="
