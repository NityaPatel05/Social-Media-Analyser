import logging
import math
import warnings
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import skew

logger = logging.getLogger(__name__)


def _safe(v: float) -> float:
    """Replace NaN/Inf with 0.0 for safe JSON output."""
    try:
        return 0.0 if (math.isnan(v) or math.isinf(v)) else float(v)
    except Exception:
        return 0.0


def lognormal_func(x, a, mu, sigma):
    """Log-normal curve — safe against log(0) and division by zero."""
    x_safe = np.maximum(x, 1e-9)
    sigma_safe = max(abs(sigma), 1e-6)
    return a * np.exp(-((np.log(x_safe) - mu) ** 2) / (2 * sigma_safe ** 2))


def _is_constant(arr: np.ndarray, tol: float = 1e-8) -> bool:
    """True if all values are essentially the same (causes catastrophic cancellation)."""
    return float(np.ptp(arr)) < tol   # peak-to-peak range


def fit_topic_curve(daily_counts: list) -> dict:
    """
    Fit a log-normal curve to the daily post count series.
    Computes skewness and day-over-day growth rate.
    Handles near-constant data and poor convergence gracefully.
    """
    _default = {
        "skewness": 0.0,
        "growth_rate": 0.0,
        "curve_params": None,
        "fit_success": False,
        "curve_data": [],
    }

    try:
        if not daily_counts:
            return _default

        counts = np.array(daily_counts, dtype=float)

        # ── Skewness ─────────────────────────────────────────────────────────
        # scipy.stats.skew raises PrecisionLossWarning for near-constant arrays.
        # Pre-check to avoid noisy logs.
        if len(counts) > 2 and not _is_constant(counts):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")   # suppress PrecisionLossWarning
                sk = _safe(float(skew(counts)))
        else:
            sk = 0.0

        # ── Growth rate (last two days) ───────────────────────────────────────
        if len(counts) >= 2:
            yesterday = counts[-2]
            today     = counts[-1]
            if yesterday > 0:
                growth_rate = float((today - yesterday) / yesterday)
            else:
                growth_rate = 0.0 if today == 0 else 1.0
        else:
            growth_rate = 0.0

        # ── Curve fit ─────────────────────────────────────────────────────────
        fit_success  = False
        curve_params = None
        curve_data   = []

        if len(counts) >= 4 and not _is_constant(counts):
            xdata = np.arange(1, len(counts) + 1, dtype=float)
            ydata = counts

            # Smart initial guess: peak position and magnitude
            peak_idx   = int(np.argmax(ydata)) + 1   # 1-indexed
            a0         = float(np.max(ydata))
            mu0        = float(np.log(max(peak_idx, 1)))
            sigma0     = 1.0

            try:
                popt, _ = curve_fit(
                    lognormal_func,
                    xdata,
                    ydata,
                    p0=[a0, mu0, sigma0],
                    bounds=(
                        [0,       -np.inf, 1e-6],   # lower: a≥0, sigma>0
                        [np.inf,   np.inf, np.inf],  # upper: unbounded
                    ),
                    maxfev=10_000,
                    method="trf",          # Trust Region Reflective — more robust
                )
                fitted_y     = lognormal_func(xdata, *popt)
                curve_data   = [_safe(v) for v in fitted_y.tolist()]
                curve_params = popt.tolist()
                fit_success  = True

            except RuntimeError:
                # Optimizer didn't converge — not an error, just not enough signal
                logger.debug("Lognormal fit did not converge — skipping curve.")
            except Exception as exc:
                logger.debug(f"Curve fit skipped: {exc}")

        return {
            "skewness":    _safe(sk),
            "growth_rate": _safe(growth_rate),
            "curve_params": curve_params,
            "fit_success":  fit_success,
            "curve_data":   curve_data,
        }

    except Exception as e:
        logger.error(f"Error in fit_topic_curve: {e}")
        return _default
