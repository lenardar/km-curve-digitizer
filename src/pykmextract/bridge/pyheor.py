"""Lazy bridge into the sibling or installed PyHEOR package."""

from __future__ import annotations

from functools import lru_cache
import importlib
import sys
from pathlib import Path
from typing import Any, Dict

from ..contracts import ExtractionResult
from ..exceptions import BridgeImportError


@lru_cache(maxsize=1)
def _import_pyheor():
    try:
        return importlib.import_module("pyheor")
    except ImportError:
        candidate = Path(__file__).resolve().parents[4] / "pyheor" / "src"
        if candidate.exists():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            try:
                return importlib.import_module("pyheor")
            except ImportError as exc:  # pragma: no cover - environment-specific
                raise BridgeImportError(
                    "Found a sibling pyheor checkout, but importing it still failed."
                ) from exc
        raise BridgeImportError(
            "pyheor is not installed and no sibling checkout was found."
        )


class PyHEORBridge:
    """Convert extracted curves into PyHEOR inputs and fitted models."""

    def extracted_to_ipd(self, extraction_result: ExtractionResult) -> Dict[str, Dict[str, Any]]:
        ph = _import_pyheor()
        semantic = extraction_result.semantic

        if not semantic.at_risk_table.time_points or not semantic.at_risk_table.counts_by_curve:
            raise ValueError("At-risk data is required for Guyot reconstruction")

        totals = semantic.total_events_by_curve or [None] * len(extraction_result.curves)
        ipds: Dict[str, Dict[str, Any]] = {}

        for index, curve in enumerate(extraction_result.curves):
            total_events = totals[index] if index < len(totals) else None
            ipd_time, ipd_event = ph.guyot_reconstruct(
                curve.time,
                curve.survival,
                semantic.at_risk_table.time_points,
                semantic.at_risk_table.counts_by_curve[index],
                tot_events=total_events,
            )
            ipds[curve.name] = {"time": ipd_time, "event": ipd_event}

        return ipds

    def fit_distributions(self, ipds: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        ph = _import_pyheor()
        fitters: Dict[str, Any] = {}

        for name, ipd in ipds.items():
            fitter = ph.SurvivalFitter(time=ipd["time"], event=ipd["event"], label=name)
            fitter.fit(verbose=False)
            fitters[name] = fitter

        return fitters

    def to_distributions(self, extraction_result: ExtractionResult) -> Dict[str, Any]:
        fitters = self.fit_distributions(self.extracted_to_ipd(extraction_result))
        return {name: fitter.best_model().distribution for name, fitter in fitters.items()}

    def ipd_to_km(self, ipds: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Compute Kaplan-Meier tables from reconstructed IPD."""
        ph = _import_pyheor()
        return {
            name: ph.kaplan_meier(ipd["time"], ipd["event"])
            for name, ipd in ipds.items()
        }
