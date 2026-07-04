"""Machine-learning ensemble.

Six model families each produce probabilities for the core outcomes
(home / draw / away, over 2.5, BTTS):

* Random Forest             (scikit-learn)
* Gradient Boosting         (scikit-learn)
* XGBoost                   (optional dependency, skipped if not installed)
* LightGBM                  (optional dependency, skipped if not installed)
* Neural network            (scikit-learn MLP)
* Bayesian Poisson          (analytic Dixon-Coles-style model with a
                              Gamma prior over goal expectations)

The classifiers are trained once, on a corpus generated from the same
generative process the engine assumes (bivariate Poisson scoring driven by
the engineered feature vector).  With real historical results connected, the
`_training_corpus` function is the single place to swap in actual match data
— the rest of the pipeline is unchanged.

Ensemble output = precision-weighted average of the per-model probabilities;
the cross-model standard deviation is surfaced as a "model agreement" signal
used by the confidence score.
"""
from __future__ import annotations

import logging
import math
import threading
import warnings
from dataclasses import dataclass

warnings.filterwarnings("ignore", message="X does not have valid feature names")

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from app.core.config import get_settings

logger = logging.getLogger(__name__)

FEATURE_ORDER = [
    "elo_diff", "attack_diff", "defence_diff", "ppg5_diff", "ppg10_diff",
    "xg5_h", "xg5_a", "xga5_h", "xga5_a", "possession_diff", "ppda_diff",
    "big_chances_diff", "deep_completions_diff", "venue_ppg_diff",
    "injury_pen_h", "injury_pen_a", "fatigue_h", "fatigue_a",
    "motivation_diff", "h2h_home_edge", "weather_penalty",
    "lambda_home", "lambda_away",
]

try:
    from xgboost import XGBClassifier
    HAS_XGB = True
except ImportError:  # pragma: no cover
    HAS_XGB = False

try:
    from lightgbm import LGBMClassifier
    HAS_LGBM = True
except ImportError:  # pragma: no cover
    HAS_LGBM = False

try:
    from catboost import CatBoostClassifier
    HAS_CATBOOST = True
except ImportError:  # pragma: no cover
    HAS_CATBOOST = False


def _poisson_pmf(lam: float, k: int) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def _training_corpus(n: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate a supervised corpus: features -> (1x2 label, over25, btts).

    Feature distributions mirror the engineered vector; outcomes are sampled
    from the bivariate Poisson process implied by the lambdas so the models
    learn the true mapping including the noisy contextual features.
    """
    elo_diff = rng.normal(0, 120, n)
    attack_diff = rng.normal(0, 12, n)
    defence_diff = rng.normal(0, 12, n)
    ppg5_diff = rng.normal(0, 0.8, n)
    ppg10_diff = ppg5_diff * 0.8 + rng.normal(0, 0.3, n)
    xg5_h = np.clip(rng.normal(1.5, 0.45, n), 0.3, 3.5)
    xg5_a = np.clip(rng.normal(1.3, 0.45, n), 0.3, 3.5)
    xga5_h = np.clip(rng.normal(1.2, 0.4, n), 0.3, 3.0)
    xga5_a = np.clip(rng.normal(1.4, 0.4, n), 0.3, 3.0)
    possession_diff = rng.normal(0, 8, n)
    ppda_diff = rng.normal(0, 3, n)
    big_chances_diff = rng.normal(0, 1.5, n)
    deep_completions_diff = rng.normal(0, 4, n)
    venue_ppg_diff = rng.normal(0.2, 0.7, n)
    injury_pen_h = np.clip(rng.exponential(0.05, n), 0, 0.3)
    injury_pen_a = np.clip(rng.exponential(0.05, n), 0, 0.3)
    fatigue_h = np.clip(rng.beta(2, 5, n), 0, 1)
    fatigue_a = np.clip(rng.beta(2, 5, n), 0, 1)
    motivation_diff = rng.normal(0, 0.3, n)
    h2h_home_edge = rng.normal(0.05, 0.3, n)
    weather_penalty = (rng.random(n) < 0.09).astype(float)

    lam_h = np.clip(
        1.45 + elo_diff / 400 + attack_diff / 60 + ppg5_diff * 0.12
        + (xg5_h - 1.4) * 0.35 + (xga5_a - 1.3) * 0.25 + venue_ppg_diff * 0.1
        - injury_pen_h * 1.2 - fatigue_h * 0.25 + motivation_diff * 0.15
        - weather_penalty * 0.1 + rng.normal(0, 0.12, n),
        0.15, 4.2)
    lam_a = np.clip(
        1.15 - elo_diff / 400 - defence_diff / 70
        + (xg5_a - 1.3) * 0.35 + (xga5_h - 1.2) * 0.25
        - injury_pen_a * 1.2 - fatigue_a * 0.25 - motivation_diff * 0.15
        - weather_penalty * 0.1 + rng.normal(0, 0.12, n),
        0.12, 3.8)

    goals_h = rng.poisson(lam_h)
    goals_a = rng.poisson(lam_a)
    y_1x2 = np.where(goals_h > goals_a, 0, np.where(goals_h == goals_a, 1, 2))
    y_over = (goals_h + goals_a > 2).astype(int)
    y_btts = ((goals_h > 0) & (goals_a > 0)).astype(int)

    X = np.column_stack([
        elo_diff, attack_diff, defence_diff, ppg5_diff, ppg10_diff,
        xg5_h, xg5_a, xga5_h, xga5_a, possession_diff, ppda_diff,
        big_chances_diff, deep_completions_diff, venue_ppg_diff,
        injury_pen_h, injury_pen_a, fatigue_h, fatigue_a,
        motivation_diff, h2h_home_edge, weather_penalty, lam_h, lam_a,
    ])
    return X, y_1x2, y_over, y_btts


@dataclass
class ModelOutput:
    name: str
    weight: float
    p_home: float
    p_draw: float
    p_away: float
    p_over25: float
    p_btts: float


class BayesianPoissonModel:
    """Analytic Dixon-Coles-style model.

    Applies a Gamma(alpha, beta) prior over the engineered goal expectations
    (shrinking extreme lambdas toward league means) and the Dixon-Coles low
    score correction tau, then computes market probabilities analytically.
    """

    name = "Bayesian Poisson (Dixon-Coles)"
    PRIOR_MEAN_H, PRIOR_MEAN_A, PRIOR_WEIGHT, RHO = 1.45, 1.15, 0.18, -0.06

    def predict(self, lam_h: float, lam_a: float) -> ModelOutput:
        lh = (1 - self.PRIOR_WEIGHT) * lam_h + self.PRIOR_WEIGHT * self.PRIOR_MEAN_H
        la = (1 - self.PRIOR_WEIGHT) * lam_a + self.PRIOR_WEIGHT * self.PRIOR_MEAN_A
        max_g = 10
        grid = np.zeros((max_g, max_g))
        for i in range(max_g):
            for j in range(max_g):
                p = _poisson_pmf(lh, i) * _poisson_pmf(la, j)
                # Dixon-Coles tau adjustment for low-scoring outcomes
                if i == 0 and j == 0:
                    p *= 1 - lh * la * self.RHO
                elif i == 0 and j == 1:
                    p *= 1 + lh * self.RHO
                elif i == 1 and j == 0:
                    p *= 1 + la * self.RHO
                elif i == 1 and j == 1:
                    p *= 1 - self.RHO
                grid[i, j] = p
        grid /= grid.sum()
        p_home = float(np.tril(grid, -1).sum())
        p_draw = float(np.trace(grid))
        p_away = float(np.triu(grid, 1).sum())
        idx = np.add.outer(np.arange(max_g), np.arange(max_g))
        p_over = float(grid[idx > 2].sum())
        p_btts = float(grid[1:, 1:].sum())
        return ModelOutput(self.name, 1.2, p_home, p_draw, p_away, p_over, p_btts)


class MLEnsemble:
    _instance: "MLEnsemble | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.trained = False
        self.scaler = StandardScaler()
        self.models_1x2: list[tuple[str, float, object]] = []
        self.models_over: list[tuple[str, float, object]] = []
        self.models_btts: list[tuple[str, float, object]] = []
        self.bayes = BayesianPoissonModel()

    @classmethod
    def instance(cls) -> "MLEnsemble":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                cls._instance.train()
            return cls._instance

    def _model_zoo(self) -> list[tuple[str, float, object]]:
        zoo: list[tuple[str, float, object]] = [
            ("Random Forest", 1.0, RandomForestClassifier(
                n_estimators=160, max_depth=10, min_samples_leaf=20,
                n_jobs=-1, random_state=7)),
            ("Gradient Boosting", 1.0, GradientBoostingClassifier(
                n_estimators=120, max_depth=3, learning_rate=0.08,
                random_state=7)),
            ("Neural Network (MLP)", 0.9, MLPClassifier(
                hidden_layer_sizes=(48, 24), max_iter=350,
                early_stopping=True, random_state=7)),
        ]
        if HAS_XGB:
            zoo.append(("XGBoost", 1.1, XGBClassifier(
                n_estimators=180, max_depth=4, learning_rate=0.07,
                subsample=0.85, colsample_bytree=0.85, eval_metric="mlogloss",
                random_state=7, n_jobs=-1)))
        if HAS_LGBM:
            zoo.append(("LightGBM", 1.1, LGBMClassifier(
                n_estimators=180, max_depth=5, learning_rate=0.07,
                subsample=0.85, colsample_bytree=0.85, random_state=7,
                n_jobs=-1, verbose=-1)))
        if HAS_CATBOOST:
            zoo.append(("CatBoost", 1.1, CatBoostClassifier(
                iterations=180, depth=5, learning_rate=0.07,
                random_seed=7, verbose=False)))
        return zoo

    def train(self) -> None:
        settings = get_settings()
        rng = np.random.default_rng(42)
        X, y_1x2, y_over, y_btts = _training_corpus(settings.ml_training_samples, rng)
        Xs = self.scaler.fit_transform(X)

        for target, ys, store in (("1x2", y_1x2, "models_1x2"),
                                  ("over", y_over, "models_over"),
                                  ("btts", y_btts, "models_btts")):
            fitted = []
            for name, weight, model in self._model_zoo():
                import copy
                m = copy.deepcopy(model)
                m.fit(Xs, ys)
                fitted.append((name, weight, m))
            setattr(self, store, fitted)
            logger.info("trained %d models for target %s", len(fitted), target)
        self.trained = True

    def predict(self, features: dict[str, float]) -> list[ModelOutput]:
        x = np.array([[features.get(k, 0.0) for k in FEATURE_ORDER]])
        xs = self.scaler.transform(x)

        outputs: list[ModelOutput] = []
        over_by_name = {n: m.predict_proba(xs)[0] for n, _, m in self.models_over}
        btts_by_name = {n: m.predict_proba(xs)[0] for n, _, m in self.models_btts}
        for name, weight, model in self.models_1x2:
            proba = model.predict_proba(xs)[0]
            p_over = float(over_by_name[name][1])
            p_btts = float(btts_by_name[name][1])
            outputs.append(ModelOutput(
                name=name, weight=weight,
                p_home=float(proba[0]), p_draw=float(proba[1]), p_away=float(proba[2]),
                p_over25=p_over, p_btts=p_btts,
            ))
        outputs.append(self.bayes.predict(features["lambda_home"], features["lambda_away"]))
        return outputs

    @staticmethod
    def combine(outputs: list[ModelOutput]) -> tuple[dict[str, float], float]:
        """Weighted average + agreement score (1 - normalised dispersion)."""
        w = np.array([o.weight for o in outputs])
        w = w / w.sum()
        stack = np.array([[o.p_home, o.p_draw, o.p_away, o.p_over25, o.p_btts]
                          for o in outputs])
        mean = stack.T @ w
        # renormalise 1x2 triplet
        s = mean[:3].sum()
        combined = {
            "1x2_home": float(mean[0] / s),
            "1x2_draw": float(mean[1] / s),
            "1x2_away": float(mean[2] / s),
            "ou_2.5_over": float(mean[3]),
            "btts_yes": float(mean[4]),
        }
        dispersion = float(stack.std(axis=0).mean())
        agreement = max(0.0, min(1.0, 1 - dispersion / 0.12))
        return combined, agreement
