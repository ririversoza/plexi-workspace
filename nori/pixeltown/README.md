# Pixel Town (Nori)

Read-only **pixelated sim view** of Tiny Town. Plays Taro's timeline back day by
day on a `<canvas>` with `image-rendering: pixelated` — grass, roads, named
shop buildings, homes, walking resident sprites, weather tint/particles, and a
HUD. One self-contained HTML file; inline CSS/JS only; no image files, no CDN.

## Run

From the repo root:

```bash
python3 -m nori.pixeltown --out "$TMPDIR/tinytown.html"
python3 -m nori.pixeltown --out "$TMPDIR/tinytown.html" --seed 42 --days 90
python3 -m taro.tinytown --export "$TMPDIR/town.json" --quiet
python3 -m nori.pixeltown --out "$TMPDIR/tinytown.html" --from "$TMPDIR/town.json"
```

Open the HTML in a browser (works on a phone).

## Rules

- Reuses `taro.tinytown.run` helpers (`_load_systems`, `_snapshot_day`,
  `_count_events_by_kind`, `validate_export_path`) — **does not copy** them.
- Live runs load systems with `csv_path=None` (no `events.csv`).
- Only writes `--out`. No extra `town.rng` draws beyond the normal town run used
  to build the timeline. Sprite walks use a seeded JS PRNG for looks only.
- Shops with `balance_cents <= 0` render dark / boarded up.

## Tests

```bash
python3 -m unittest discover -s nori/pixeltown -t .
python3 -m unittest bao.tinytown.test_town_acceptance
```

— Nori · *Teamwork makes the dream work!*
