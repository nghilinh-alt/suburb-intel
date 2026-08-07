diff --git a/backend/app/api/suburb.py b/backend/app/api/suburb.py
index f2a98dc..cd6a4ad 100644
--- a/backend/app/api/suburb.py
+++ b/backend/app/api/suburb.py
@@ -43,6 +43,7 @@ from app.services.property_market_service import (
     fetch_price_history,
     fetch_price_history_by_spec,
 )
+from app.services.neighbour_comparison_service import fetch_neighbour_comparison
 from app.services.regional_comparison_service import fetch_regional_comparison
 from app.services.school_rating_service import fetch_school_percentile
 from app.services.points_of_interest_service import fetch_points_of_interest
@@ -174,6 +175,7 @@ async def suburb_report(
         neighborhood_momentum = await fetch_neighborhood_momentum(db, sa2_code)
         rental_market = await fetch_rental_market_history(db, sa2_code)
         regional_comparison = await fetch_regional_comparison(db, sa2_code)
+        neighbour_comparison = await fetch_neighbour_comparison(db, sa2_code)
         schools = await fetch_schools(db, sa2_code)
         school_percentile = await fetch_school_percentile(db, sa2_code)
         points_of_interest = await fetch_points_of_interest(db, sa2_code)
@@ -193,6 +195,7 @@ async def suburb_report(
                 "housing_pressure_score": suburb_score_row.housing_pressure_score if suburb_score_row else None,
             },
             "regional_comparison": regional_comparison,
+            "neighbour_comparison": neighbour_comparison,
             "location": {
                 "distance_to_cbd_km": region.distance_to_cbd_km,
             },
diff --git a/backend/app/ingestion/points_of_interest_loader.py b/backend/app/ingestion/points_of_interest_loader.py
index fca244e..6e5f6e9 100644
--- a/backend/app/ingestion/points_of_interest_loader.py
+++ b/backend/app/ingestion/points_of_interest_loader.py
@@ -26,6 +26,7 @@ from __future__ import annotations
 
 import hashlib
 import logging
+import re
 from dataclasses import dataclass
 from pathlib import Path
 
@@ -54,6 +55,15 @@ _AU_BBOX = (112.0, -44.5, 155.0, -9.0)
 # "department_store" is deliberately excluded — it matches individual anchor
 # stores (Myer, Target, David Jones) inside a mall, not the complex itself,
 # which just produced 5-8 duplicate near-identical entries per real mall.
+#
+# NOTE: several of these categories are self-tag noise magnets — Overture lets
+# any business pick its own primary category, so "shopping_center" collects
+# individual retailers (a keyboard shop, a sunglasses reseller, a solar-parts
+# maker) and "venue_and_event_space" collects logistics/marine/office
+# businesses. "venue_and_event_space" is dropped entirely below (no reliable
+# way to keep only genuine attractions), and Shopping Centre / the generic
+# Stadium bucket get name-based precision filters in `_passes_quality_filter`
+# — same precision-over-recall trade-off already used for `_is_real_hospital`.
 _OVERTURE_POI_CATEGORIES: dict[str, str] = {
     # ── Hospitals (major facilities only — GPs/clinics stay in the amenity
     #    counts section, this is landmark-scale). Overture's "hospital"
@@ -80,7 +90,6 @@ _OVERTURE_POI_CATEGORIES: dict[str, str] = {
     "zoo": "Attraction",
     "aquarium": "Attraction",
     "casino": "Attraction",
-    "venue_and_event_space": "Attraction",
     "museum": "Attraction",
     "history_museum": "Attraction",
     "art_museum": "Attraction",
@@ -162,6 +171,68 @@ def _is_real_hospital(name: str, group_label: str) -> bool:
     return "hospital" in name.lower()
 
 
+# Name tokens that mark a genuine shopping complex, as opposed to the many
+# individual small retailers Overture self-tags as "shopping_center". Word-
+# boundary matched so "mall" doesn't fire on "small" and "shopping" catches
+# "Shoppingtown"/"Shopping Village"/"Shopping Plaza" alike.
+_SHOPPING_CENTRE_TOKENS: tuple[str, ...] = (
+    "shopping",
+    "shoppingtown",
+    "marketplace",
+    "market place",
+    "plaza",
+    "arcade",
+    "mall",
+    "westfield",
+    "homemaker",
+    "megacentre",
+    "mega centre",
+    "harbour town",
+    "outlet",
+    "dfo",
+)
+
+# Name tokens for a genuine sporting venue. Only applied to Overture's generic
+# "stadium_arena" catch-all (a social-play badminton centre self-tags into it);
+# the sport-specific categories (football_stadium, rugby_stadium, ...) are
+# trustworthy on their own and are NOT name-filtered, so venues with names like
+# "The Gabba" survive.
+_STADIUM_TOKENS: tuple[str, ...] = (
+    "stadium",
+    "arena",
+    "oval",
+    "ground",
+    "showground",
+    "velodrome",
+    "racecourse",
+    "raceway",
+    "speedway",
+    "aquatic",
+)
+
+
+def _name_has_token(name: str, tokens: tuple[str, ...]) -> bool:
+    low = name.lower()
+    return any(re.search(rf"\b{re.escape(tok)}\b", low) for tok in tokens)
+
+
+def _passes_quality_filter(name: str, category: str, group_label: str) -> bool:
+    """Precision filter for Overture's noisiest self-tag POI categories.
+
+    Overture carries no size/type signal to separate a landmark from a small
+    business that picked the same primary category, so we fall back to a name
+    heuristic per group — trading recall for precision, the same call already
+    made in `_is_real_hospital`.
+    """
+    if group_label == "Hospital":
+        return _is_real_hospital(name, group_label)
+    if group_label == "Shopping Centre":
+        return _name_has_token(name, _SHOPPING_CENTRE_TOKENS)
+    if group_label == "Stadium & Arena" and category == "stadium_arena":
+        return _name_has_token(name, _STADIUM_TOKENS)
+    return True
+
+
 def load_points_of_interest(db: Session, places_path: Path) -> PoiLoadReport:
     report = PoiLoadReport()
 
@@ -170,7 +241,10 @@ def load_points_of_interest(db: Session, places_path: Path) -> PoiLoadReport:
     places_df["group_label"] = places_df["category"].map(_OVERTURE_POI_CATEGORIES)
     places_df = places_df.dropna(subset=["group_label", "name", "lat", "lon"])
     places_df = places_df[
-        places_df.apply(lambda r: _is_real_hospital(r["name"], r["group_label"]), axis=1)
+        places_df.apply(
+            lambda r: _passes_quality_filter(r["name"], r["category"], r["group_label"]),
+            axis=1,
+        )
     ]
     report.places_loaded = len(places_df)
 
diff --git a/backend/app/services/neighbour_comparison_service.py b/backend/app/services/neighbour_comparison_service.py
new file mode 100755
index 0000000..5f70cf9
--- /dev/null
+++ b/backend/app/services/neighbour_comparison_service.py
@@ -0,0 +1,148 @@
+"""Compares a suburb's headline market metrics against its immediate
+neighbours — the adjacent SA2s already precomputed on
+`SA2Region.adjacent_sa2_codes` (the same source the Points of Interest
+"nearby" list uses). This answers the question a buyer actually asks —
+"is this dearer or cheaper than the suburbs next door?" — which the
+national-median ruler on its own can't.
+
+Metrics are PropRadar's latest-period suburb-level figures from
+`SuburbMarketStats`. A single SA2 can hold more than one real suburb row
+(a combined SA2 like "Rochedale - Burbank" — see
+suburb_market_stats_loader.py); those are averaged to one figure per SA2
+for this side-by-side, mirroring how the rest of the report treats an SA2
+as "the suburb". Distances are straight-line km between SA2 centroids,
+using the same haversine helper as points_of_interest_service.
+"""
+
+from __future__ import annotations
+
+from statistics import mean
+from typing import Any, Dict, List, Optional, Tuple
+
+from sqlalchemy import select
+from sqlalchemy.ext.asyncio import AsyncSession
+
+from app.core.geo import centroid_from_geojson, haversine_km
+from app.db.models import SA2Region, SuburbMarketStats
+
+# (field, label, format, higher_is_better). `higher_is_better` drives the
+# frontend's good/bad colouring; None = neutral (a dearer median isn't
+# inherently better or worse), matching the ContextRuler convention.
+_METRICS: List[Tuple[str, str, str, Optional[bool]]] = [
+    ("median_house_price", "Median Price", "currency", None),
+    ("gross_yield_house_pct", "Gross Yield", "pct", True),
+    ("days_on_market_house", "Days on Market", "days", False),
+]
+
+# Cap on how many neighbours to show alongside the subject — enough for
+# context without turning the section into a wall of near-identical rows.
+_MAX_NEIGHBOURS = 6
+
+
+async def fetch_neighbour_comparison(db: AsyncSession, sa2_code: str) -> Optional[Dict[str, Any]]:
+    """Return ``{"subject_sa2_code", "metrics", "suburbs"}`` comparing this
+    suburb to its adjacent SA2s, or ``None`` when there's nothing meaningful
+    to compare (no adjacency, or no market data to anchor on)."""
+    subject = await db.get(SA2Region, sa2_code)
+    if subject is None:
+        return None
+
+    adjacent_codes = [c for c in (subject.adjacent_sa2_codes or []) if c != sa2_code]
+    if not adjacent_codes:
+        return None
+
+    all_codes = [sa2_code, *adjacent_codes]
+
+    region_rows = (
+        await db.execute(
+            select(SA2Region.sa2_code, SA2Region.sa2_name, SA2Region.geometry_geojson).where(
+                SA2Region.sa2_code.in_(all_codes)
+            )
+        )
+    ).all()
+    name_by_code = {code: name for code, name, _ in region_rows}
+    centroid_by_code = {code: centroid_from_geojson(geo) for code, _, geo in region_rows}
+    origin = centroid_by_code.get(sa2_code)
+
+    stats_by_code = await _latest_metrics_by_sa2(db, all_codes)
+    # Without market data for the subject there's nothing to anchor the
+    # comparison on, so we surface nothing rather than a table of neighbours.
+    if sa2_code not in stats_by_code:
+        return None
+
+    metric_keys = [k for k, _, _, _ in _METRICS]
+    suburbs: List[Dict[str, Any]] = []
+    for code in all_codes:
+        values = stats_by_code.get(code)
+        if not values or all(values.get(k) is None for k in metric_keys):
+            continue
+        entry: Dict[str, Any] = {
+            "sa2_code": code,
+            "name": name_by_code.get(code) or code,
+            "is_subject": code == sa2_code,
+            "distance_km": None,
+            "values": {k: values.get(k) for k in metric_keys},
+        }
+        dest = centroid_by_code.get(code)
+        if code != sa2_code and origin is not None and dest is not None:
+            entry["distance_km"] = round(haversine_km(origin, dest), 1)
+        suburbs.append(entry)
+
+    # Subject plus at least one neighbour is the minimum for a comparison.
+    if len(suburbs) < 2:
+        return None
+
+    # Subject first, then neighbours nearest-first (unknown distance last).
+    suburbs.sort(
+        key=lambda s: (not s["is_subject"], s["distance_km"] is None, s["distance_km"] or 0.0)
+    )
+    suburbs = [suburbs[0], *suburbs[1 : 1 + _MAX_NEIGHBOURS]]
+
+    metrics_meta = [
+        {"key": k, "label": label, "format": fmt, "higher_is_better": higher_is_better}
+        for k, label, fmt, higher_is_better in _METRICS
+    ]
+    return {"subject_sa2_code": sa2_code, "metrics": metrics_meta, "suburbs": suburbs}
+
+
+async def _latest_metrics_by_sa2(
+    db: AsyncSession, sa2_codes: List[str]
+) -> Dict[str, Dict[str, Any]]:
+    """Latest-period value of each comparison metric per SA2, averaged across
+    whatever real suburbs that SA2 contains. Only the comparison metrics are
+    selected. `period` is a sortable 'YYYY-MM' string, so a descending sort
+    puts the newest snapshot first per (sa2_code, suburb_name)."""
+    metric_keys = [k for k, _, _, _ in _METRICS]
+    columns = [
+        SuburbMarketStats.sa2_code,
+        SuburbMarketStats.suburb_name,
+        SuburbMarketStats.period,
+        *[getattr(SuburbMarketStats, k) for k in metric_keys],
+    ]
+    stmt = (
+        select(*columns)
+        .where(SuburbMarketStats.sa2_code.in_(sa2_codes))
+        .order_by(SuburbMarketStats.period.desc())
+    )
+    rows = (await db.execute(stmt)).all()
+
+    latest: Dict[Tuple[str, str], Dict[str, Any]] = {}
+    for row in rows:
+        code, suburb_name = row[0], row[1]
+        key = (code, suburb_name)
+        if key in latest:
+            continue  # already have this suburb's newest snapshot
+        latest[key] = dict(zip(metric_keys, row[3:]))
+
+    per_sa2: Dict[str, Dict[str, List[float]]] = {}
+    for (code, _suburb_name), values in latest.items():
+        bucket = per_sa2.setdefault(code, {k: [] for k in metric_keys})
+        for k in metric_keys:
+            v = values.get(k)
+            if v is not None:
+                bucket[k].append(v)
+
+    return {
+        code: {k: (round(mean(vals), 2) if vals else None) for k, vals in buckets.items()}
+        for code, buckets in per_sa2.items()
+    }
diff --git a/frontend/src/components/Charts.tsx b/frontend/src/components/Charts.tsx
index a0faf44..eb6bea1 100644
--- a/frontend/src/components/Charts.tsx
+++ b/frontend/src/components/Charts.tsx
@@ -279,69 +279,118 @@ export function ContextRuler({
   const valuePct = clampPct(value)
   const baselinePct = clampPct(baseline)
 
-  let markerColor: string = colors.blue
-  if (higherIsBetter != null) {
-    const isBetter = higherIsBetter ? value >= baseline : value <= baseline
-    markerColor = isBetter ? colors.green : colors.amber
-  }
+  // Good/bad only exists when the metric has a direction. `null` = neutral
+  // (e.g. median price — dearer is neither good nor bad on its own).
+  const isBetter =
+    higherIsBetter == null ? null : higherIsBetter ? value >= baseline : value <= baseline
+  const markerColor = isBetter == null ? colors.blue : isBetter ? colors.green : colors.amber
+  const deltaColor = isBetter == null ? colors.textSecondary : isBetter ? colors.green : colors.amber
+
+  // Plain-language comparison — the actual point of the ruler, e.g. "18% above
+  // national median". Spelled out in words so the colour isn't load-bearing.
+  const pctDiff = baseline ? ((value - baseline) / Math.abs(baseline)) * 100 : 0
+  const deltaText =
+    Math.abs(pctDiff) < 1
+      ? `in line with ${baselineLabel}`
+      : `${Math.abs(pctDiff).toFixed(0)}% ${value > baseline ? 'above' : 'below'} ${baselineLabel}`
+
+  // Directional track: reddish (worse) → greenish (better), flipped when lower
+  // is better; a neutral ramp when the metric has no inherent direction.
+  const trackBackground =
+    isBetter == null
+      ? `linear-gradient(90deg, ${colors.blueLight}, ${colors.pageBg})`
+      : higherIsBetter
+        ? `linear-gradient(90deg, ${colors.roseLight}, ${colors.pageBg} 55%, ${colors.greenLight})`
+        : `linear-gradient(90deg, ${colors.greenLight}, ${colors.pageBg} 45%, ${colors.roseLight})`
+
+  // Keep the baseline caption on-screen when its tick sits near either edge.
+  const captionLeft = baselinePct > 85 ? 'auto' : baselinePct < 15 ? '0' : `${baselinePct}%`
+  const captionRight = baselinePct > 85 ? '0' : 'auto'
+  const captionAlign: 'left' | 'center' | 'right' =
+    baselinePct < 15 ? 'left' : baselinePct > 85 ? 'right' : 'center'
+  const captionTransform = baselinePct >= 15 && baselinePct <= 85 ? 'translateX(-50%)' : 'none'
 
   return (
     <div style={{ width: '100%' }}>
       {label && (
-        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
+        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px', fontSize: '13px' }}>
           <span style={{ color: colors.textSecondary }}>{label}</span>
           <span style={{ color: colors.textPrimary, fontWeight: 600 }}>{formatValue(value)}</span>
         </div>
       )}
+      <div style={{ fontSize: '12px', fontWeight: 600, color: deltaColor, marginTop: '2px' }}>{deltaText}</div>
       <div
         style={{
           position: 'relative',
-          height: '6px',
+          height: '8px',
           borderRadius: '999px',
-          backgroundColor: colors.pageBg,
+          background: trackBackground,
+          border: `1px solid ${colors.border}`,
           marginTop: '10px',
         }}
       >
+        {/* national-median reference tick */}
         <div
           title={`${baselineLabel}: ${formatValue(baseline)}`}
           style={{
             position: 'absolute',
             left: `${baselinePct}%`,
-            top: '-3px',
+            top: '-4px',
             width: '2px',
-            height: '12px',
-            backgroundColor: colors.textMuted,
+            height: '16px',
+            backgroundColor: colors.textSecondary,
             transform: 'translateX(-1px)',
           }}
         />
+        {/* this-suburb marker */}
         <div
           title={`This suburb: ${formatValue(value)}`}
           style={{
             position: 'absolute',
             left: `${valuePct}%`,
-            top: '-4px',
-            width: '12px',
-            height: '12px',
+            top: '-5px',
+            width: '18px',
+            height: '18px',
             borderRadius: '50%',
             backgroundColor: markerColor,
             border: '2px solid #FFFFFF',
-            boxShadow: '0 1px 2px rgba(0,0,0,0.25)',
-            transform: 'translateX(-6px)',
+            boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
+            transform: 'translateX(-9px)',
           }}
         />
       </div>
+      {/* baseline caption, anchored under its tick */}
+      <div style={{ position: 'relative', height: '14px', marginTop: '5px' }}>
+        <span
+          style={{
+            position: 'absolute',
+            left: captionLeft,
+            right: captionRight,
+            textAlign: captionAlign,
+            transform: captionTransform,
+            fontSize: '10px',
+            color: colors.textMuted,
+            whiteSpace: 'nowrap',
+          }}
+        >
+          ▏{baselineLabel} {formatValue(baseline)}
+        </span>
+      </div>
+      {/* scale endpoints + this-suburb legend */}
       <div
         style={{
           display: 'flex',
           justifyContent: 'space-between',
-          fontSize: '11px',
+          alignItems: 'center',
+          fontSize: '10px',
           color: colors.textMuted,
-          marginTop: '6px',
+          marginTop: '2px',
         }}
       >
         <span>{formatValue(min)}</span>
-        <span>
-          {baselineLabel}: {formatValue(baseline)}
+        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
+          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: markerColor, display: 'inline-block' }} />
+          this suburb
         </span>
         <span>{formatValue(max)}</span>
       </div>
diff --git a/frontend/src/pages/SuburbPage.tsx b/frontend/src/pages/SuburbPage.tsx
index 5b052ef..6cc8839 100644
--- a/frontend/src/pages/SuburbPage.tsx
+++ b/frontend/src/pages/SuburbPage.tsx
@@ -225,6 +225,27 @@ interface RegionalComparison {
   metrics: RegionalMetric[]
 }
 
+interface NeighbourMetric {
+  key: string
+  label: string
+  format: 'currency' | 'pct' | 'days'
+  higher_is_better: boolean | null
+}
+
+interface NeighbourSuburb {
+  sa2_code: string
+  name: string
+  is_subject: boolean
+  distance_km: number | null
+  values: Record<string, number | null>
+}
+
+interface NeighbourComparison {
+  subject_sa2_code: string
+  metrics: NeighbourMetric[]
+  suburbs: NeighbourSuburb[]
+}
+
 interface InvestmentHighlight {
   label: string
   format: 'text' | 'pct' | 'rate' | 'score' | 'days'
@@ -342,6 +363,7 @@ interface SuburbReport {
   tags: string[]
   scores: SuburbScores | null
   regional_comparison: RegionalComparison | null
+  neighbour_comparison: NeighbourComparison | null
   location: { distance_to_cbd_km: number | null }
   momentum: Momentum
   market_stats: SuburbMarketStat[]
@@ -386,6 +408,12 @@ function fmtDecile(v: number | null | undefined): string {
 function fmtDays(v: number | null | undefined): string {
   return v == null ? '—' : `${Math.round(v)} days`
 }
+function fmtNeighbourMetric(format: NeighbourMetric['format'], v: number | null): string {
+  if (v == null) return '—'
+  if (format === 'currency') return fmtCurrency(v)
+  if (format === 'pct') return fmtPct(v)
+  return fmtDays(v)
+}
 function titleCase(s: string): string {
   return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
 }
@@ -684,6 +712,7 @@ function ReadyView({ data }: { data: SuburbReport }) {
     tags,
     scores,
     regional_comparison,
+    neighbour_comparison,
     momentum,
     market_stats,
     rental_market,
@@ -1456,6 +1485,55 @@ function ReadyView({ data }: { data: SuburbReport }) {
         </Section>
       )}
 
+      {neighbour_comparison && neighbour_comparison.suburbs.length > 1 && (() => {
+        const cols = `minmax(120px, 1.6fr) repeat(${neighbour_comparison.metrics.length}, 1fr)`
+        return (
+          <Section
+            title={`${primarySuburbName(sa2_name)} vs Neighbouring Suburbs`}
+            subtitle="Adjacent suburbs, nearest first. Figures are PropRadar's latest suburb-level snapshot; a combined SA2 is averaged across its suburbs."
+          >
+            <div style={{ display: 'grid', gap: '2px' }}>
+              <div style={{ display: 'grid', gridTemplateColumns: cols, gap: '8px', padding: '4px 12px' }}>
+                <span style={{ fontSize: '11px', fontWeight: 600, color: colors.textMuted, textTransform: 'uppercase' }}>Suburb</span>
+                {neighbour_comparison.metrics.map((mt) => (
+                  <span key={mt.key} style={{ fontSize: '11px', fontWeight: 600, color: colors.textMuted, textTransform: 'uppercase', textAlign: 'right' }}>
+                    {mt.label}
+                  </span>
+                ))}
+              </div>
+              {neighbour_comparison.suburbs.map((sub) => (
+                <div
+                  key={sub.sa2_code}
+                  style={{
+                    display: 'grid',
+                    gridTemplateColumns: cols,
+                    gap: '8px',
+                    alignItems: 'baseline',
+                    padding: '10px 12px',
+                    borderRadius: '8px',
+                    backgroundColor: sub.is_subject ? colors.pinkLight : colors.pageBg,
+                  }}
+                >
+                  <span style={{ fontSize: '14px', color: colors.textPrimary, fontWeight: sub.is_subject ? 700 : 500 }}>
+                    {primarySuburbName(sub.name)}
+                    {sub.is_subject ? (
+                      <span style={{ fontSize: '11px', color: colors.pink, marginLeft: '6px' }}>this suburb</span>
+                    ) : sub.distance_km != null ? (
+                      <span style={{ fontSize: '11px', color: colors.textMuted, marginLeft: '6px' }}>{sub.distance_km} km</span>
+                    ) : null}
+                  </span>
+                  {neighbour_comparison.metrics.map((mt) => (
+                    <span key={mt.key} style={{ fontSize: '14px', textAlign: 'right', fontFamily: fonts.mono, color: colors.textPrimary }}>
+                      {fmtNeighbourMetric(mt.format, sub.values[mt.key] ?? null)}
+                    </span>
+                  ))}
+                </div>
+              ))}
+            </div>
+          </Section>
+        )
+      })()}
+
       {show_census_sections && (
       <>
       <Section title="Demographics" dataVintage={`${census_year} Census`}>
