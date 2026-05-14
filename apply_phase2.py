"""Phase 2: implement TrackingError + CDaR, gate RB+BL in frontend."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


# ============================================================================
# FILE 1: portopt/portopt/models/tracking.py
# ============================================================================
TRACKING_PY = r'''"""Tracking Error optimization (Roll 1992, Jorion 2003)."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy import optimize

from portopt.estimators import LedoitWolfCC, SampleMean
from portopt.models.base import (
    ConstraintSet,
    OptimizationModel,
    OptimizationResult,
)


class TrackingError(OptimizationModel):
    """Minimize tracking error vs a benchmark.

    Formulation (Jorion 2003):

        TE(omega) = sqrt((omega - omega_B)' Sigma (omega - omega_B))

    Two modes:
      1. target_te is None: pure TE minimization (long-only, sum=1)
      2. target_te is set: maximize excess return s.t. TE <= target_te

    The benchmark weights omega_B must be passed via
    constraints.benchmark_weights. Defaults to equal-weight if absent (with
    a warning).
    """

    name = "tracking_error"
    native_risk_measure = "tracking_error"
    requires_returns = True
    supports_short = False

    def __init__(
        self,
        target_te: float | None = None,
        cov_estimator=None,
        mean_estimator=None,
        backend: str = "scipy",
    ):
        self.target_te = target_te
        self.cov_estimator = cov_estimator or LedoitWolfCC()
        self.mean_estimator = mean_estimator or SampleMean()
        self.backend = backend

    def fit(self, log_returns, constraints=None):
        constraints = constraints or ConstraintSet()
        T, N = log_returns.shape
        names = list(log_returns.columns)

        Sigma = self.cov_estimator.fit(log_returns).cov_
        mu = self.mean_estimator.fit(log_returns).mean_

        if constraints.benchmark_weights is not None:
            omega_B = np.asarray(constraints.benchmark_weights, dtype=float)
            if len(omega_B) != N:
                raise ValueError(
                    f"benchmark_weights has {len(omega_B)} entries, "
                    f"expected {N} (one per asset)"
                )
        else:
            omega_B = np.ones(N) / N
            warnings.warn(
                "No benchmark_weights set; defaulting to equal-weight. "
                "Pass constraints.benchmark_weights for meaningful tracking.",
                stacklevel=2,
            )

        if self.target_te is None:
            return self._minimize_te(Sigma, mu, omega_B, constraints, names)
        else:
            return self._max_excess_return(Sigma, mu, omega_B, constraints, names)

    def _minimize_te(self, Sigma, mu, omega_B, constraints, names):
        N = len(omega_B)
        lb, ub = constraints.bounds
        sum_to = constraints.sum_to or 1.0

        def te_sq(omega):
            d = omega - omega_B
            return float(d @ Sigma @ d)

        def te_sq_grad(omega):
            return 2.0 * Sigma @ (omega - omega_B)

        cons = [{"type": "eq", "fun": lambda w: float(np.sum(w) - sum_to)}]
        if constraints.target_return is not None:
            cons.append({
                "type": "ineq",
                "fun": lambda w: float(w @ mu - constraints.target_return),
            })

        bounds = [(lb, ub)] * N
        x0 = omega_B.copy()

        res = optimize.minimize(
            te_sq, x0, jac=te_sq_grad, method="SLSQP",
            bounds=bounds, constraints=cons,
            options={"maxiter": 200, "ftol": 1e-10},
        )

        omega = np.clip(res.x, lb, ub)
        if omega.sum() > 0:
            omega = omega / omega.sum() * sum_to
        te_value = float(np.sqrt(max(te_sq(omega), 0.0)))

        return OptimizationResult(
            weights={n: float(w) for n, w in zip(names, omega)},
            expected_return=float(omega @ mu),
            risk=te_value,
            risk_measure="tracking_error",
            converged=bool(res.success),
            diagnostics={
                "backend": "scipy_slsqp",
                "iterations": int(res.nit),
                "message": str(res.message),
                "benchmark_weights": omega_B.tolist(),
                "mode": "minimize_te",
            },
        )

    def _max_excess_return(self, Sigma, mu, omega_B, constraints, names):
        N = len(omega_B)
        lb, ub = constraints.bounds
        sum_to = constraints.sum_to or 1.0
        te_sq_limit = self.target_te ** 2

        def neg_excess(omega):
            return -float((omega - omega_B) @ mu)

        def neg_excess_grad(omega):
            return -mu

        def te_budget(omega):
            d = omega - omega_B
            return te_sq_limit - float(d @ Sigma @ d)

        cons = [
            {"type": "eq", "fun": lambda w: float(np.sum(w) - sum_to)},
            {"type": "ineq", "fun": te_budget},
        ]
        bounds = [(lb, ub)] * N
        x0 = omega_B.copy()

        res = optimize.minimize(
            neg_excess, x0, jac=neg_excess_grad, method="SLSQP",
            bounds=bounds, constraints=cons,
            options={"maxiter": 200, "ftol": 1e-10},
        )

        omega = np.clip(res.x, lb, ub)
        if omega.sum() > 0:
            omega = omega / omega.sum() * sum_to
        d = omega - omega_B
        te_value = float(np.sqrt(max(d @ Sigma @ d, 0.0)))

        return OptimizationResult(
            weights={n: float(w) for n, w in zip(names, omega)},
            expected_return=float(omega @ mu),
            risk=te_value,
            risk_measure="tracking_error",
            converged=bool(res.success),
            diagnostics={
                "backend": "scipy_slsqp",
                "iterations": int(res.nit),
                "message": str(res.message),
                "benchmark_weights": omega_B.tolist(),
                "target_te": self.target_te,
                "mode": "max_excess_return",
            },
        )
'''


# ============================================================================
# FILE 2: portopt/portopt/models/cdar.py
# ============================================================================
CDAR_PY = r'''"""Conditional Drawdown-at-Risk (Chekhlov-Uryasev-Zabarankin 2003, 2005)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from portopt.models.base import (
    ConstraintSet,
    OptimizationModel,
    OptimizationResult,
)


class CDaR(OptimizationModel):
    """Minimize Conditional Drawdown-at-Risk via LP formulation.

    CDaR_alpha is the expected drawdown over the alpha-worst portion of the
    drawdown distribution. Path-dependent risk measure suitable for managed
    accounts, hedge funds, and any strategy with drawdown limits.

    LP formulation (Chekhlov-Uryasev-Zabarankin 2005, Eq. 33-37):

        min  z + (1 / (T * alpha)) * sum_t u_t

        s.t. u_t >= y_t - V_t - z       (excess over VaR threshold)
             u_t >= 0
             y_t >= V_t                  (running max >= current)
             y_t >= y_{t-1}              (running max monotonic)
             y_0 >= 0
             V_t = sum_{s<=t} (R[s,:] @ omega)
             sum(omega) = 1
             omega in [lb, ub]

    Variables: omega (N) + z (1) + u (T) + y (T). V_t is pre-computed as a
    linear function of omega via the cumulative returns matrix M, where
    M[t, i] = sum_{s<=t} R[s, i]. Then V_t = M[t, :] @ omega.

    Final formulation has N + 1 + 2T variables and ~3T inequalities + 1
    equality. Solved with linprog HiGHS (fast and reliable for sparse LPs).
    """

    name = "cdar"
    native_risk_measure = "cdar"
    requires_returns = True
    supports_short = False

    def __init__(self, alpha: float = 0.05, backend: str = "linprog"):
        if not (0 < alpha < 1):
            raise ValueError(f"alpha must be in (0,1), got {alpha}")
        self.alpha = alpha
        self.backend = backend

    def fit(self, log_returns, constraints=None):
        constraints = constraints or ConstraintSet()
        T, N = log_returns.shape
        names = list(log_returns.columns)
        R = log_returns.values

        lb, ub = constraints.bounds
        sum_to = constraints.sum_to or 1.0

        # Pre-compute cumulative returns matrix: M[t, i] = sum_{s<=t} R[s, i]
        M = np.cumsum(R, axis=0)

        # Variable layout: [omega (N) | z (1) | u (T) | y (T)]
        off_omega = 0
        off_z = N
        off_u = N + 1
        off_y = N + 1 + T
        n_total = N + 1 + 2 * T

        # Objective: c^T x = z + (1/(T*alpha)) * sum(u_t)
        c = np.zeros(n_total)
        c[off_z] = 1.0
        c[off_u:off_u + T] = 1.0 / (T * self.alpha)

        # Inequalities: 3T constraints
        # (1) -M[t,:] @ omega - z - u_t + y_t <= 0   (u_t >= y_t - V_t - z)
        # (2)  M[t,:] @ omega - y_t <= 0              (y_t >= V_t)
        # (3) -y_t + y_{t-1} <= 0  for t >= 1         (y monotonic)
        A_ub = np.zeros((3 * T, n_total))

        for t in range(T):
            # (1)
            A_ub[t, off_omega:off_omega + N] = -M[t, :]
            A_ub[t, off_z] = -1.0
            A_ub[t, off_u + t] = -1.0
            A_ub[t, off_y + t] = 1.0

            # (2)
            A_ub[T + t, off_omega:off_omega + N] = M[t, :]
            A_ub[T + t, off_y + t] = -1.0

        for t in range(1, T):
            # (3)
            A_ub[2 * T + t, off_y + t] = -1.0
            A_ub[2 * T + t, off_y + t - 1] = 1.0
        # Row 2T+0 is all zeros (no y_{-1}); trivially satisfied.

        b_ub = np.zeros(3 * T)

        # Equality: sum(omega) = sum_to
        A_eq = np.zeros((1, n_total))
        A_eq[0, off_omega:off_omega + N] = 1.0
        b_eq = np.array([sum_to])

        # Bounds
        bounds = []
        for _ in range(N):
            bounds.append((lb, ub))
        bounds.append((None, None))   # z free
        for _ in range(T):
            bounds.append((0.0, None))  # u_t >= 0
        for _ in range(T):
            bounds.append((0.0, None))  # y_t >= 0

        res = linprog(
            c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
            bounds=bounds, method="highs",
        )

        if not res.success:
            raise RuntimeError(f"CDaR linprog failed: {res.message}")

        x = res.x
        omega = x[off_omega:off_omega + N]
        z_star = float(x[off_z])
        u_t = x[off_u:off_u + T]
        y_t = x[off_y:off_y + T]
        V_t = M @ omega

        cdar = float(z_star + np.sum(u_t) / (T * self.alpha))
        mu = R.mean(axis=0)
        expected_log_ret = float(omega @ mu)
        max_drawdown_realized = float(np.max(y_t - V_t))

        return OptimizationResult(
            weights={n: float(w) for n, w in zip(names, omega)},
            expected_return=expected_log_ret,
            risk=cdar,
            risk_measure="cdar",
            converged=bool(res.success),
            diagnostics={
                "backend": "linprog_highs",
                "iterations": int(getattr(res, "nit", -1)),
                "message": str(res.message),
                "alpha": self.alpha,
                "z_star": z_star,
                "max_drawdown_realized": max_drawdown_realized,
                "T": T,
                "N": N,
            },
        )
'''


# ============================================================================
# Tests to add at the end of test_smoke.py
# ============================================================================
NEW_TESTS = '''

# ============================================================================
# TrackingError tests (Phase 2)
# ============================================================================

def test_tracking_error_minimization_stays_near_benchmark():
    """Pure TE minimization (no return target) should track benchmark."""
    import numpy as np
    import pandas as pd
    from portopt.models.tracking import TrackingError
    from portopt.models.base import ConstraintSet

    rng = np.random.default_rng(42)
    T, N = 500, 5
    R = pd.DataFrame(
        rng.standard_normal((T, N)) * 0.01,
        columns=[f"asset_{i}" for i in range(N)],
    )
    omega_B = np.array([0.4, 0.3, 0.2, 0.05, 0.05])

    model = TrackingError()
    cons = ConstraintSet(bounds=(0.0, 1.0), benchmark_weights=omega_B)
    result = model.fit(R, cons)

    assert result.converged
    omega = np.array(list(result.weights.values()))
    assert abs(omega.sum() - 1.0) < 1e-4
    # Should be very close to benchmark (low TE)
    assert np.max(np.abs(omega - omega_B)) < 0.10
    assert result.risk >= 0.0


def test_tracking_error_with_target_seeks_excess_return():
    """With target_te budget, optimizer should deviate from benchmark to gain excess return."""
    import numpy as np
    import pandas as pd
    from portopt.models.tracking import TrackingError
    from portopt.models.base import ConstraintSet

    rng = np.random.default_rng(7)
    T, N = 300, 4
    base = rng.standard_normal((T, N)) * 0.01
    # Make asset 0 strictly dominant in mean
    base[:, 0] += 0.005
    R = pd.DataFrame(base, columns=[f"asset_{i}" for i in range(N)])
    omega_B = np.array([0.25, 0.25, 0.25, 0.25])

    model = TrackingError(target_te=0.005)
    cons = ConstraintSet(bounds=(0.0, 1.0), benchmark_weights=omega_B)
    result = model.fit(R, cons)

    assert result.converged
    # Should overweight asset 0 (dominant returns)
    assert result.weights["asset_0"] > 0.25


# ============================================================================
# CDaR tests (Phase 2)
# ============================================================================

def test_cdar_produces_valid_portfolio():
    """CDaR LP should solve and produce valid weights."""
    import numpy as np
    import pandas as pd
    from portopt.models.cdar import CDaR

    rng = np.random.default_rng(0)
    T, N = 250, 5
    R = pd.DataFrame(
        rng.standard_normal((T, N)) * 0.01,
        columns=[f"asset_{i}" for i in range(N)],
    )

    model = CDaR(alpha=0.05)
    result = model.fit(R)

    assert result.converged
    omega = np.array(list(result.weights.values()))
    assert abs(omega.sum() - 1.0) < 1e-4
    assert all(w >= -1e-6 for w in omega)
    assert result.risk_measure == "cdar"
    assert result.risk >= 0.0


def test_cdar_avoids_high_drawdown_asset():
    """CDaR should underweight assets with severe historical drawdowns."""
    import numpy as np
    import pandas as pd
    from portopt.models.cdar import CDaR

    rng = np.random.default_rng(42)
    T = 500
    # asset "stable": low vol, no drawdown
    stable = rng.standard_normal(T) * 0.005
    # asset "crashes": severe sustained loss in first half
    crashes = np.concatenate([
        np.full(T // 4, -0.02),
        rng.standard_normal(T - T // 4) * 0.01,
    ])
    R = pd.DataFrame({"stable": stable, "crashes": crashes})

    model = CDaR(alpha=0.05)
    result = model.fit(R)

    assert result.converged
    # CDaR should heavily favor the stable asset
    assert result.weights["stable"] > result.weights["crashes"]
'''


# ============================================================================
# Workshop.tsx: add gates for risk_budget and black_litterman
# ============================================================================
WORKSHOP_BEFORE = '''<select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            {models.map((m) => (
              <option key={m.name} value={m.name}>
                {m.pedagogy.model_name}
              </option>
            ))}
          </select>'''

WORKSHOP_AFTER = '''<select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            title="Modelos com configuração avançada (Risk Budget, Black-Litterman) requerem API direta."
          >
            {models.map((m) => {
              const isAdvanced = m.name === "risk_budget" || m.name === "black_litterman";
              return (
                <option
                  key={m.name}
                  value={m.name}
                  disabled={isAdvanced}
                >
                  {m.pedagogy.model_name}{isAdvanced ? " (avançado — via API)" : ""}
                </option>
              );
            })}
          </select>'''


# ============================================================================
# Apply all changes
# ============================================================================
def main():
    # 1. Write tracking.py
    p = ROOT / "portopt" / "portopt" / "models" / "tracking.py"
    p.write_text(TRACKING_PY, encoding="utf-8")
    print(f"Wrote: {p}")

    # 2. Write cdar.py
    p = ROOT / "portopt" / "portopt" / "models" / "cdar.py"
    p.write_text(CDAR_PY, encoding="utf-8")
    print(f"Wrote: {p}")

    # 3. Append new tests
    p = ROOT / "portopt" / "tests" / "test_smoke.py"
    c = p.read_text(encoding="utf-8")
    if "test_tracking_error_minimization_stays_near_benchmark" not in c:
        p.write_text(c + NEW_TESTS, encoding="utf-8")
        print(f"Added 4 new tests: {p}")
    else:
        print(f"Tests already present: {p}")

    # 4. Patch Workshop.tsx
    p = ROOT / "frontend" / "src" / "pages" / "Workshop.tsx"
    c = p.read_text(encoding="utf-8")
    if "isAdvanced" not in c and WORKSHOP_BEFORE in c:
        c = c.replace(WORKSHOP_BEFORE, WORKSHOP_AFTER)
        p.write_text(c, encoding="utf-8")
        print(f"Patched: {p}")
    elif "isAdvanced" in c:
        print(f"Workshop.tsx already patched: {p}")
    else:
        print(f"WARN: Workshop.tsx select pattern not found - manual edit needed: {p}")

    print("\nDONE. Next steps:")
    print("  1) cd portopt && python -m pytest -q")
    print("  2) cd .. && git add -A && git commit && git push")
    print("  3) fly deploy")


if __name__ == "__main__":
    main()