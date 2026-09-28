#!/usr/bin/env python3
"""PresenceDetector: the retrieval layer, ready for the sheet.

Loads what retrieval.py learned — terms per category, calibrated threshold, and the
performance measured on the held_out split — and applies it to a new contract.

Three honesty rules, wired here and not in the interface:

1. A category without a calibratable threshold never decides on its own.
2. An "absent" is asserted only if the measured recall backs it. With low recall the
   detector misses half the ones that are there, so its silence is not evidence of
   absence: the row comes out as absent_review.
3. A jump into the document is offered only where location was accurate enough on
   the held_out split. Sending the reader to the wrong paragraph is worse than not
   offering the jump at all.
"""
import json
from pathlib import Path

import retrieval as REC

MIN_RECALL_TO_ASSERT_ABSENCE = 60.0
MIN_LOCATION_TO_JUMP        = 50.0


class PresenceDetector:
    def __init__(self, path="retrieval_model.json", calibration="calibration.json"):
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        self.cues = d["cues"]
        self.thresholds = d["thresholds"]
        self.performance = {r["category"]: r for r in d["test"]}
        self._cache = {}
        # Per-row confidence: how far the score sits from the threshold, mapped
        # to the accuracy that margin actually achieved. Without it every row of
        # a clause carries the same number, which is a population rate wearing
        # the clothes of a per-row probability.
        try:
            self.calibration = json.loads(Path(calibration).read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.calibration = {}

    def row_confidence(self, category, score):
        """Calibrated accuracy for this row, or None when uncalibrated."""
        cal = self.calibration.get(category)
        threshold = self.thresholds.get(category)
        if not cal or threshold is None:
            return None
        margin, edges = abs(score - threshold), cal["edges"]
        band = next((i for i in range(len(edges) - 1)
                     if edges[i] <= margin < edges[i + 1]), len(edges) - 2)
        return 100.0 * cal["bins"].get(str(band), cal["fallback"])

    def supports(self, category):
        return category in self.cues

    def evaluate(self, category, text):
        """-> (state, confidence, start|None)"""
        perf = self.performance.get(category)
        threshold = self.thresholds.get(category)
        if threshold is None or perf is None:
            return "review", None, None

        score, where = REC.score_windows(text, self.cues[category], self._cache)
        conf = self.row_confidence(category, score)
        if conf is None:
            conf = perf["balanced"]
        located_pct = perf.get("located_pct")

        if score >= threshold:
            start = where if (located_pct or 0) >= MIN_LOCATION_TO_JUMP else None
            return "found", conf, start
        if perf["recall"] >= MIN_RECALL_TO_ASSERT_ABSENCE:
            return "absent", conf, None
        return "absent_review", conf, None
