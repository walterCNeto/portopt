"""Hierarchical Risk Parity (Lopez de Prado 2016, Chagas §4.6).

Three stages:
1. Hierarchical Clustering: build a dendrogram from correlation distances.
2. Quasi-Diagonalization: reorder Σ so similar assets are near the diagonal.
3. Recursive Bisection: distribute weights using Inverse Variance within bisections.

Implementation faithfully follows Chagas' notebook 3 (cells 60-66).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Optional

import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as sch
import scipy.spatial.distance as ssd

from portopt.estimators import SampleCov, CovEstimator
from portopt.models.base import (
    ConstraintSet,
    OptimizationModel,
    OptimizationResult,
)


def _correl_distance(corrs: np.ndarray) -> np.ndarray:
    """Convert correlation matrix to distance: d_{ij} = sqrt((1 - ρ) / 2)."""
    return np.sqrt(np.clip((1.0 - corrs) / 2.0, 0.0, 1.0))


def _quasi_diagonalization(linkages: np.ndarray, N: int, i: int) -> list[int]:
    """Recursive quasi-diagonalization: ordered list of leaf indices.

    Reproduces Chagas' nb3 cell 64.
    """
    if i < N:
        return [i]
    i_left = int(linkages[i - N, 0])
    i_right = int(linkages[i - N, 1])
    return _quasi_diagonalization(linkages, N, i_left) + _quasi_diagonalization(linkages, N, i_right)


def _recursive_bisection(qd_order: list[int], cov_df: pd.DataFrame) -> pd.Series:
    """Recursive bisection assigning weights via inverse-variance within each cluster.

    Reproduces Chagas' nb3 cell 66.
    """
    names = cov_df.columns.tolist()
    weights = pd.Series(1.0, index=names)
    subclusters = [qd_order]

    while len(subclusters) > 0:
        # Bisect every current subcluster
        subclusters = [
            sc[a:b]
            for sc in subclusters
            for (a, b) in (
                (0, len(sc) // 2),
                (len(sc) // 2, len(sc)),
            )
            if len(sc) > 1
        ]

        # Pair up left/right and adjust
        for i in range(0, len(subclusters), 2):
            left_idx = subclusters[i]
            right_idx = subclusters[i + 1]
            left_names = [names[j] for j in left_idx]
            right_names = [names[j] for j in right_idx]

            cov_L = cov_df.loc[left_names, left_names].values
            cov_R = cov_df.loc[right_names, right_names].values

            # Inverse-variance weights within each side
            inv_L = 1.0 / np.diag(cov_L)
            w_L = inv_L / inv_L.sum()
            inv_R = 1.0 / np.diag(cov_R)
            w_R = inv_R / inv_R.sum()

            var_L = float(w_L @ cov_L @ w_L)
            var_R = float(w_R @ cov_R @ w_R)

            alpha = 1.0 - var_L / (var_L + var_R)

            for name in left_names:
                weights[name] *= alpha
            for name in right_names:
                weights[name] *= (1.0 - alpha)

    return weights


class HierarchicalRiskParity(OptimizationModel):
    """Hierarchical Risk Parity (Lopez de Prado 2016).

    Parameters
    ----------
    cov_estimator : CovEstimator, optional
        Default: SampleCov.
    linkage_method : str
        Linkage criterion for hierarchical clustering.
        Options: "single" (Chagas default, Prado), "complete", "average", "ward".
    return_dendrogram : bool
        If True, attach the dendrogram object to diagnostics for visualization.
    """

    name = "hrp"
    requires_returns = False
    supports_short = False
    native_risk_measure = "vol"

    def __init__(
        self,
        cov_estimator: Optional[CovEstimator] = None,
        linkage_method: str = "single",
        return_dendrogram: bool = False,
    ):
        self.cov_estimator = cov_estimator or SampleCov()
        self.linkage_method = linkage_method
        self.return_dendrogram = return_dendrogram

    def fit(self, returns: pd.DataFrame, constraints: ConstraintSet, **kwargs) -> OptimizationResult:
        # Stage 1: hierarchical clustering
        corrs = returns.corr(method="pearson")
        dists = _correl_distance(corrs.values)
        condensed = ssd.squareform(dists, checks=False)
        linkages = sch.linkage(condensed, method=self.linkage_method)

        # Stage 2: quasi-diagonalization
        N = len(corrs)
        qd_order = _quasi_diagonalization(linkages, N, 2 * (N - 1))

        # Stage 3: recursive bisection with cov estimator
        cov_arr = self.cov_estimator.fit(returns)
        cov_df = pd.DataFrame(cov_arr, index=corrs.index, columns=corrs.columns)
        weights = _recursive_bisection(qd_order, cov_df)

        # Apply bounds clipping (HRP may violate bounds; this is a known issue)
        if isinstance(constraints.bounds, tuple):
            lb, ub = constraints.bounds
        else:
            lb = min(b[0] for b in constraints.bounds)
            ub = max(b[1] for b in constraints.bounds)

        if lb > 0 or ub < 1:
            # Clip & re-normalize. Production version might re-run bisection
            # with bounds-aware logic; this is a documented HRP drawback (Chagas §4.6).
            w_clipped = weights.clip(lower=lb, upper=ub)
            if w_clipped.sum() > 0:
                weights = w_clipped / w_clipped.sum()

        # Diagnostics
        cov = cov_arr
        w_arr = weights.values
        vol = float(np.sqrt(max(w_arr @ cov @ w_arr, 0.0)))
        port_ret = float(returns.mean().values @ w_arr)

        diagnostics = {
            "linkage_method": self.linkage_method,
            "qd_order": qd_order,
            "qd_order_names": [returns.columns[i] for i in qd_order],
        }
        if self.return_dendrogram:
            diagnostics["linkages"] = linkages.tolist()
            diagnostics["distances"] = dists.tolist()

        return OptimizationResult(
            weights=weights,
            expected_return=port_ret,
            risk=vol,
            risk_measure="vol",
            converged=True,
            diagnostics=diagnostics,
        )
