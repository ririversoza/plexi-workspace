# Tiny Town — seed robustness (Phase 3)

Report of the runner's multi-seed table against the Phase 2/3 acceptance targets:

1. At least **5 of 6** shops still solvent on day 90 (`balance_cents > 0`).
2. No shop sits at **$0** for more than **3** days in a row.
3. Average resident wallet on day 90 is **below $600**.

## Command

From the worktree root (scratch redirected to `$TMPDIR`; nothing written into the repo):

```bash
python3 -m taro.tinytown.run --seeds 1-20 --days 90
```

## Table (real output)

```
seed  shops  max_$0  avg_wallet    treasury  result
   1      6       0     $379.42      1000.0  PASS
   2      6       0     $359.69      1060.0  PASS
   3      6       0     $405.18      1000.0  PASS
   4      6       0     $411.13      1060.0  PASS
   5      6       0     $423.98      1000.0  PASS
   6      6       2     $396.18       990.0  PASS
   7      6       0     $398.27      1000.0  PASS
   8      6       0     $346.75      1000.0  PASS
   9      6       0     $408.85      1000.0  PASS
  10      6       0     $351.15      1060.0  PASS
  11      6       0     $371.93      1060.0  PASS
  12      6       0     $431.92      1000.0  PASS
  13      6       0     $371.28      1000.0  PASS
  14      6       0     $370.24      1030.0  PASS
  15      6       0     $379.94      1000.0  PASS
  16      6       0     $361.89      1000.0  PASS
  17      6       0     $391.63       982.0  PASS
  18      6       1     $387.60      1070.0  PASS
  19      6       0     $381.04      1000.0  PASS
  20      6       0     $372.11      1000.0  PASS
20 of 20 seeds pass
```

## Summary

**20 of 20** seeds meet all three targets.

No failing seeds in this range, so there is no missed-target note to attach. Closest edges: seed 6 reached a max `$0` streak of 2 (still ≤3); day-90 average wallets stayed between about $347 and $432.
