"""Chấm điểm và chọn mã trong từng theme."""

from __future__ import annotations

from typing import Any

import pandas as pd

from common import ThemeSpec, UniverseConfig, top_k_for_theme
from features import build_feature_table, zscore_series


def score_frame(features: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    work = features.copy()
    if work.empty:
        work["score"] = []
        return work
    work["z_gtgd"] = zscore_series(work["log_gtgd"])
    work["z_vol"] = zscore_series(work["log_vol"])
    w_g = float(params.get("w_log_gtgd", 0.55))
    w_v = float(params.get("w_log_vol", 0.35))
    w_a = float(params.get("w_atr", 0.10))
    # Chuẩn hoá nhẹ trọng số.
    total = w_g + w_v + w_a
    if total <= 0:
        w_g, w_v, w_a = 0.55, 0.35, 0.10
        total = 1.0
    w_g, w_v, w_a = w_g / total, w_v / total, w_a / total
    atr = pd.to_numeric(work["atr_score"], errors="coerce").fillna(0.0)
    work["score"] = w_g * work["z_gtgd"] + w_v * work["z_vol"] + w_a * atr
    # Không có bars → score cực thấp.
    work.loc[work["has_bars"] != 1, "score"] = -1e9
    return work


def select_theme(
    theme: ThemeSpec,
    candidates: list[str],
    cfg: UniverseConfig,
    params: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Trả bảng đã rank + metrics so với seed."""
    params = params or cfg.params
    seed = set(theme.symbols)
    whitelist = set(theme.whitelist)
    features = build_feature_table(candidates, cfg)
    scored = score_frame(features, params)
    min_vol = float(params.get("min_vol20", 500_000))
    keep_seed = bool(params.get("keep_seed_if_listed", True))
    keep_wl = bool(params.get("keep_whitelist", True))

    scored["in_seed"] = scored["symbol"].isin(seed)
    scored["in_whitelist"] = scored["symbol"].isin(whitelist)
    vol = pd.to_numeric(scored["vol20"], errors="coerce")
    scored["pass_vol"] = vol.fillna(-1.0) >= min_vol

    # Ứng viên đủ điều kiện thanh khoản; seed/whitelist được giữ nếu có bars.
    eligible_mask = scored["pass_vol"] & (scored["has_bars"] == 1)
    if keep_seed:
        eligible_mask = eligible_mask | (scored["in_seed"] & (scored["has_bars"] == 1))
    if keep_wl:
        eligible_mask = eligible_mask | (scored["in_whitelist"] & (scored["has_bars"] == 1))

    ranked = scored.loc[eligible_mask].sort_values("score", ascending=False)
    k = top_k_for_theme(len(theme.symbols), params)
    selected = ranked.head(k).copy()

    # Đảm bảo whitelist luôn có mặt nếu có bars (có thể vượt K một chút).
    if keep_wl:
        missing_wl = scored.loc[
            scored["in_whitelist"] & (scored["has_bars"] == 1) & ~scored["symbol"].isin(selected["symbol"])
        ]
        if not missing_wl.empty:
            selected = pd.concat([selected, missing_wl], ignore_index=True)

    selected = selected.sort_values("score", ascending=False).reset_index(drop=True)
    selected["rank"] = range(1, len(selected) + 1)
    selected["theme"] = theme.key
    selected["theme_label"] = theme.label

    chosen = set(selected["symbol"].tolist())
    seed_with_bars = set(scored.loc[scored["in_seed"] & (scored["has_bars"] == 1), "symbol"])
    # Recall chỉ tính trên seed đã có bars (tránh phạt vì chưa pull).
    denom = len(seed_with_bars) if seed_with_bars else len(seed)
    hit = len(chosen & (seed_with_bars or seed))
    recall = hit / denom if denom else 0.0
    precision = len(chosen & seed) / len(chosen) if chosen else 0.0
    metrics = {
        "theme": theme.key,
        "seed_n": float(len(seed)),
        "seed_with_bars": float(len(seed_with_bars)),
        "candidates": float(len(candidates)),
        "selected_n": float(len(chosen)),
        "k": float(k),
        "recall": recall,
        "precision": precision,
        "hit": float(hit),
    }
    return selected, metrics


def run_all_themes(
    themes: list[ThemeSpec],
    industry: dict[str, str],
    cfg: UniverseConfig,
    params: dict[str, Any] | None = None,
) -> tuple[dict[str, pd.DataFrame], list[dict[str, float]]]:
    from common import candidate_symbols, seeds_except

    tables: dict[str, pd.DataFrame] = {}
    metrics: list[dict[str, float]] = []
    for theme in themes:
        cands = candidate_symbols(theme, industry, exclude=seeds_except(themes, theme))
        table, metric = select_theme(theme, cands, cfg, params=params)
        tables[theme.key] = table
        metrics.append(metric)
    return tables, metrics
