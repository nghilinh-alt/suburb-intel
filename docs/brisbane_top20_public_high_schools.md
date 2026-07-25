# Brisbane — Top 20 Public High Schools

**Generated:** 2026-07-25
**Source:** `backend/suburb_intel_dev.db` → `school_ratings` joined to `sa2_regions`
**Scope:** Brisbane SA4s (Inner City, North, South, East, West) · public (`is_public=1`) · secondary/combined
**Ranking metric:** ICSEA (no NAPLAN/OP column exists in `school_ratings`)
**Pool size:** 46 public secondary schools

| # | School | Suburb | SA4 | ICSEA | ICSEA %ile |
|---|--------|--------|-----|-------|-----------|
| 1 | Queensland Academy for Science Mathematics and Technology | Toowong | Brisbane Inner City | 1220 | 99 |
| 2 | Brisbane State High School | South Brisbane | Brisbane Inner City | 1145 | 94 |
| 3 | Indooroopilly State High School | Indooroopilly | Brisbane - West | 1138 | 93 |
| 4 | Brisbane South State Secondary College | Dutton Park | Brisbane - South | 1137 | 93 |
| 5 | Kelvin Grove State College | Kelvin Grove | Brisbane Inner City | 1135 | 92 |
| 6 | Queensland Academy for Creative Industries | Kelvin Grove | Brisbane Inner City | 1128 | 91 |
| 7 | The Gap State High School | The Gap | Brisbane - West | 1123 | 90 |
| 8 | Mansfield State High School | Mansfield | Brisbane - South | 1116 | 88 |
| 9 | Kenmore State High School | Kenmore | Brisbane - West | 1110 | 87 |
| 10 | Cavendish Road State High School | Holland Park | Brisbane - South | 1103 | 85 |
| 11 | Kedron State High School | Kedron | Brisbane - North | 1096 | 83 |
| 12 | Fortitude Valley State Secondary College | Fortitude Valley | Brisbane Inner City | 1086 | 80 |
| 13 | Mount Gravatt State High School | Mount Gravatt | Brisbane - South | 1079 | 78 |
| 14 | Craigslea State High School | Chermside West | Brisbane - North | 1070 | 76 |
| 15 | Ferny Grove State High School | Ferny Grove | Brisbane - West | 1069 | 75 |
| 16 | Stretton State College | Stretton | Brisbane - South | 1068 | 75 |
| 17 | Corinda State High School | Corinda | Brisbane - West | 1060 | 72 |
| 18 | Holland Park State High School | Holland Park West | Brisbane - South | 1055 | 70 |
| 19 | Aviation High | Hendra | Brisbane - East | 1051 | 69 |
| 20 | Centenary State High School | Jindalee | Brisbane - West | 1049 | 68 |

## Suburbs (in rank order)

Toowong, South Brisbane, Indooroopilly, Dutton Park, Kelvin Grove (×2), The Gap, Mansfield, Kenmore, Holland Park, Kedron, Fortitude Valley, Mount Gravatt, Chermside West, Ferny Grove, Stretton, Corinda, Holland Park West, Hendra, Jindalee.

## Notes / caveats

- "Brisbane" scoped to the five Brisbane SA4s. Excludes Greater Brisbane's outer rings (Ipswich, Logan – Beaudesert, Moreton Bay). Re-run with those SA4s if a wider metro definition is needed.
- Ranked on ICSEA (socio-educational advantage index), which is the only school-quality field in the db — it is a proxy for academic outcomes, not a direct performance ranking.
- Includes combined (P–12) schools where a secondary component exists.
