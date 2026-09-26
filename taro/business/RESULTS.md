# Fold Post results (Taro)

Exact stdout from `python3 taro/business/run.py` (do not edit by hand):

```
Fold Post · seed=42 · days=90
Starting balance: $500.00
Final balance:    $1,947.31
Profit:           $1,447.31
Growth:           289.46%
```

Reproduce from the repo root:

```bash
python3 -m unittest discover -s taro/business -v
python3 taro/business/run.py
```

`ledger.csv` is regenerated on every run. Juniper will re-run and reject any mismatch.
