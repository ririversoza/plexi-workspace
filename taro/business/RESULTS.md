# Fold Post results (Taro)

Exact stdout from `python3 taro/business/run.py` (do not edit by hand):

```
Fold Post · seed=42 · days=90
Starting balance: $500.00
Final balance:    $348.31
Profit:           $-151.69
Growth:           -30.34%
```

Reproduce from the repo root:

```bash
python3 -m unittest discover -s taro/business -v
python3 taro/business/run.py
```

`ledger.csv` is regenerated on every run. Juniper will re-run and reject any mismatch.
