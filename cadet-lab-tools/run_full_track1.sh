#!/bin/bash
# Run full Track 1 NILT benchmarks (24 runs: 6 problems × 4 tiers)

python3 scripts/run_track1_nilt_benchmarks.py \
    --cadet-cli /home/gogip/github_repos/CADET-Core/install/bin/cadet-cli \
    --output-dir artifacts/track1_full \
    --alpha 0.5 \
    --nilt-n 256 \
    2>&1 | tee /tmp/track1_full.log
