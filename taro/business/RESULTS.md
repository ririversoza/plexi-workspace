# Fold Post results (Taro)

Exact stdout from `python3 taro/business/run.py` (do not edit by hand):

```
Fold Post · seed=42 · days=90
Starting balance: $500.00
Final balance:    $3,409.76
Profit:           $2,909.76
Growth:           581.95%
```

Reproduce from the repo root:

```bash
python3 -m unittest discover -s taro/business -v
python3 taro/business/run.py
```

`ledger.csv` is regenerated on every run. Juniper will re-run and reject any mismatch.
