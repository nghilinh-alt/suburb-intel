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
