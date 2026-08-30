from __future__ import annotations

from pathlib import Path
import math
import os
import textwrap
import warnings

os.environ.setdefault("MPLCONFIGDIR", "/tmp/cumcm_mplconfig")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "8")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, SplineTransformer, StandardScaler
from sklearn.tree import DecisionTreeRegressor


warnings.filterwarnings("ignore", category=FutureWarning)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "data" / "processed" / "q2_male_cleaned.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "results" / "q2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = OUTPUT_DIR / "q2_model_report.txt"
CURVE_IMAGE = OUTPUT_DIR / "q2_probability_curves.png"
GROUP_IMAGE = OUTPUT_DIR / "q2_bmi_groups.png"
MODEL_IMAGE = OUTPUT_DIR / "q2_model_comparison.png"
ERROR_IMAGE = OUTPUT_DIR / "q2_error_sensitivity.png"

TARGET_PROBABILITY = 0.90
MIN_WEEK = 10.0
MAX_WEEK = 25.0
WEEK_STEP = 1.0 / 7.0
RANDOM_STATE = 2025


def set_chinese_font() -> None:
    plt.rcParams["font.sans-serif"] = [
        "PingFang SC",
        "Heiti SC",
        "Arial Unicode MS",
        "SimHei",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def build_models() -> dict[str, object]:
    """候选模型都只使用检测孕周和基线BMI。"""
    return {
        "基准常数模型": DummyClassifier(strategy="prior"),
        "线性Logistic": Pipeline(
            [
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=5000, C=1.0)),
            ]
        ),
        "二次交互Logistic": Pipeline(
            [
                ("poly", PolynomialFeatures(degree=2, include_bias=False)),
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=5000, C=1.0)),
            ]
        ),
        "样条Logistic": Pipeline(
            [
                ("spline", SplineTransformer(n_knots=5, degree=3, include_bias=False)),
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=5000, C=0.7)),
            ]
        ),
        "梯度提升树": HistGradientBoostingClassifier(
            max_iter=250,
            learning_rate=0.04,
            max_depth=3,
            min_samples_leaf=25,
            l2_regularization=2.0,
            random_state=RANDOM_STATE,
        ),
    }


def fit_with_weight(model, x, y, sample_weight):
    """Pipeline 的样本权重需要传给最后一个模型步骤。"""
    if isinstance(model, Pipeline):
        model.fit(x, y, model__sample_weight=sample_weight)
    else:
        model.fit(x, y, sample_weight=sample_weight)
    return model


def grouped_cross_validation(models, x, y, groups, weights) -> pd.DataFrame:
    """同一孕妇的全部检测记录始终落在同一折，防止信息泄漏。"""
    splitter = GroupKFold(n_splits=5)
    rows = []
    for model_name, model_template in models.items():
        fold_metrics = []
        for train_index, test_index in splitter.split(x, y, groups):
            model = clone(model_template)
            fit_with_weight(
                model,
                x.iloc[train_index],
                y.iloc[train_index],
                weights.iloc[train_index],
            )
            probability = np.clip(model.predict_proba(x.iloc[test_index])[:, 1], 1e-6, 1 - 1e-6)
            fold_metrics.append(
                {
                    "LogLoss": log_loss(y.iloc[test_index], probability),
                    "Brier": brier_score_loss(y.iloc[test_index], probability),
                    "AUC": roc_auc_score(y.iloc[test_index], probability),
                }
            )
        fold_df = pd.DataFrame(fold_metrics)
        rows.append(
            {
                "模型": model_name,
                "LogLoss均值": fold_df["LogLoss"].mean(),
                "LogLoss标准差": fold_df["LogLoss"].std(ddof=1),
                "LogLoss标准误": fold_df["LogLoss"].std(ddof=1) / math.sqrt(len(fold_df)),
                "Brier均值": fold_df["Brier"].mean(),
                "AUC均值": fold_df["AUC"].mean(),
            }
        )
    result = pd.DataFrame(rows).sort_values(["LogLoss均值", "Brier均值"]).reset_index(drop=True)
    return result


def monotone_probability(model, bmi_values: np.ndarray, week_grid: np.ndarray) -> np.ndarray:
    """预测达标概率，并按孕周做累积最大值以满足达标率不随孕周下降的临床约束。"""
    prediction_matrix = np.empty((len(bmi_values), len(week_grid)))
    for index, bmi in enumerate(bmi_values):
        prediction_frame = pd.DataFrame(
            {
                "孕周_周": week_grid,
                "基线BMI": np.full(len(week_grid), bmi),
            }
        )
        raw_probability = model.predict_proba(prediction_frame)[:, 1]
        prediction_matrix[index] = np.maximum.accumulate(raw_probability)
    return prediction_matrix


def earliest_target_week(probability_matrix: np.ndarray, week_grid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """返回最早达到目标概率的孕周，以及25周内是否达到目标。"""
    target_weeks = np.full(probability_matrix.shape[0], MAX_WEEK, dtype=float)
    reached = np.zeros(probability_matrix.shape[0], dtype=bool)
    for row_index, row in enumerate(probability_matrix):
        locations = np.flatnonzero(row >= TARGET_PROBABILITY)
        if len(locations):
            target_weeks[row_index] = week_grid[locations[0]]
            reached[row_index] = True
    return target_weeks, reached


def tree_cv_table(bmi: np.ndarray, target_week: np.ndarray, minimum_leaf: int) -> pd.DataFrame:
    """比较3至5个叶节点，并用一标准误差规则偏向更简单的分组。"""
    splitter = KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    rows = []
    for leaves in (3, 4, 5):
        errors = []
        for train_index, test_index in splitter.split(bmi):
            tree = DecisionTreeRegressor(
                max_leaf_nodes=leaves,
                min_samples_leaf=minimum_leaf,
                random_state=RANDOM_STATE,
            )
            tree.fit(bmi[train_index].reshape(-1, 1), target_week[train_index])
            prediction = tree.predict(bmi[test_index].reshape(-1, 1))
            errors.append(float(np.mean(np.abs(target_week[test_index] - prediction))))
        rows.append(
            {
                "目标组数": leaves,
                "CV_MAE均值": np.mean(errors),
                "CV_MAE标准误": np.std(errors, ddof=1) / math.sqrt(len(errors)),
            }
        )
    result = pd.DataFrame(rows)
    best_row = result.loc[result["CV_MAE均值"].idxmin()]
    one_se_limit = best_row["CV_MAE均值"] + best_row["CV_MAE标准误"]
    eligible = result[result["CV_MAE均值"] <= one_se_limit]
    chosen_leaves = int(eligible["目标组数"].min())
    result["是否选择"] = result["目标组数"].eq(chosen_leaves)
    return result


def extract_thresholds(tree: DecisionTreeRegressor) -> list[float]:
    thresholds = tree.tree_.threshold
    return sorted(float(x) for x in thresholds if x > -2)


def round_up_half_week(value: float) -> float:
    return math.ceil(value * 2 - 1e-10) / 2


def build_groups(
    subjects: pd.DataFrame,
    thresholds: list[float],
    model,
    week_grid: np.ndarray,
) -> pd.DataFrame:
    bins = [-np.inf, *thresholds, np.inf]
    labels = list(range(1, len(bins)))
    subjects = subjects.copy()
    subjects["组别"] = pd.cut(subjects["基线BMI"], bins=bins, labels=labels, right=False).astype(int)
    rows = []
    for group_number, group in subjects.groupby("组别", sort=True):
        bmi_values = group["基线BMI"].to_numpy(dtype=float)
        probability = monotone_probability(model, bmi_values, week_grid)
        mean_probability = probability.mean(axis=0)
        locations = np.flatnonzero(mean_probability >= TARGET_PROBABILITY)
        if len(locations):
            exact_week = float(week_grid[locations[0]])
            recommended_week = min(round_up_half_week(exact_week), MAX_WEEK)
            status = "达到90%目标"
        else:
            fallback_locations = np.flatnonzero(mean_probability >= 0.85)
            if len(fallback_locations):
                exact_week = float(week_grid[fallback_locations[0]])
                recommended_week = min(round_up_half_week(exact_week), MAX_WEEK)
                status = "90%不可达；采用85%时点并建议复测"
            else:
                exact_week = MAX_WEEK
                recommended_week = MAX_WEEK
                status = "25周内连85%目标也未达到"
        selected_index = int(np.argmin(np.abs(week_grid - recommended_week)))
        average_probability = float(mean_probability[selected_index])
        sensitivity_times = {}
        for probability_level in (0.85, 0.90, 0.95):
            sensitivity_locations = np.flatnonzero(mean_probability >= probability_level)
            sensitivity_times[probability_level] = (
                min(round_up_half_week(float(week_grid[sensitivity_locations[0]])), MAX_WEEK)
                if len(sensitivity_locations)
                else None
            )
        left = bins[group_number - 1]
        right = bins[group_number]
        if np.isneginf(left):
            interval = f"BMI < {right:.2f}"
        elif np.isposinf(right):
            interval = f"BMI ≥ {left:.2f}"
        else:
            interval = f"{left:.2f} ≤ BMI < {right:.2f}"
        rows.append(
            {
                "组别": int(group_number),
                "BMI区间": interval,
                "样本数": int(len(group)),
                "BMI中位数": float(group["基线BMI"].median()),
                "推荐检测孕周": recommended_week,
                "推荐时点平均达标概率": average_probability,
                "85%概率时点": sensitivity_times[0.85],
                "90%概率时点": sensitivity_times[0.90],
                "95%概率时点": sensitivity_times[0.95],
                "状态": status,
            }
        )
    return pd.DataFrame(rows)


def bootstrap_thresholds(
    bmi: np.ndarray,
    target_week: np.ndarray,
    chosen_leaves: int,
    minimum_leaf: int,
    repetitions: int = 300,
) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_STATE)
    threshold_samples = []
    for repetition in range(repetitions):
        sample_index = rng.integers(0, len(bmi), size=len(bmi))
        tree = DecisionTreeRegressor(
            max_leaf_nodes=chosen_leaves,
            min_samples_leaf=minimum_leaf,
            random_state=RANDOM_STATE + repetition,
        )
        tree.fit(bmi[sample_index].reshape(-1, 1), target_week[sample_index])
        current = extract_thresholds(tree)
        if len(current) == chosen_leaves - 1:
            threshold_samples.append(current)
    if not threshold_samples:
        return pd.DataFrame(columns=["切点", "Bootstrap中位数", "95%区间下限", "95%区间上限"])
    array = np.asarray(threshold_samples)
    rows = []
    for index in range(array.shape[1]):
        rows.append(
            {
                "切点": index + 1,
                "Bootstrap中位数": np.median(array[:, index]),
                "95%区间下限": np.quantile(array[:, index], 0.025),
                "95%区间上限": np.quantile(array[:, index], 0.975),
            }
        )
    return pd.DataFrame(rows)


def plot_probability_curves(model, group_table, week_grid):
    set_chinese_font()
    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=170)
    colors = plt.cm.viridis(np.linspace(0.10, 0.90, len(group_table)))
    for (_, row), color in zip(group_table.iterrows(), colors):
        bmi = float(row["BMI中位数"])
        probability = monotone_probability(model, np.array([bmi]), week_grid)[0]
        ax.plot(week_grid, probability, linewidth=2.5, color=color, label=f"第{int(row['组别'])}组：{row['BMI区间']}")
        ax.axvline(float(row["推荐检测孕周"]), color=color, linestyle=":", alpha=0.65)
    ax.axhline(TARGET_PROBABILITY, color="#C00000", linestyle="--", linewidth=2, label="90%达标概率")
    ax.set_xlim(MIN_WEEK, MAX_WEEK)
    ax.set_ylim(0.70, 1.00)
    ax.set_yticks(np.arange(0.70, 1.01, 0.05))
    ax.set_xlabel("检测孕周（周）")
    ax.set_ylabel("预测Y染色体浓度达标概率")
    ax.set_title("不同BMI组的Y染色体浓度达标概率曲线")
    ax.grid(alpha=0.22, linestyle="--")
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    fig.tight_layout()
    fig.savefig(CURVE_IMAGE, bbox_inches="tight")
    plt.close(fig)


def plot_model_comparison(comparison: pd.DataFrame):
    set_chinese_font()
    plot_data = comparison.sort_values("LogLoss均值", ascending=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.8), dpi=170)
    colors = ["#9EADBA" if name == "基准常数模型" else "#377EB8" for name in plot_data["模型"]]
    axes[0].barh(plot_data["模型"], plot_data["LogLoss均值"], xerr=plot_data["LogLoss标准误"], color=colors, alpha=0.9)
    axes[0].set_xlabel("五折交叉验证 LogLoss（越低越好）")
    axes[0].set_title("概率预测误差")
    axes[0].grid(axis="x", alpha=0.2, linestyle="--")
    axes[1].barh(plot_data["模型"], plot_data["AUC均值"], color=colors, alpha=0.9)
    axes[1].axvline(0.5, color="#C00000", linestyle="--", linewidth=1.5, label="随机水平")
    axes[1].set_xlim(0.45, max(0.65, float(plot_data["AUC均值"].max()) + 0.03))
    axes[1].set_xlabel("五折交叉验证 AUC（越高越好）")
    axes[1].set_title("区分能力")
    axes[1].grid(axis="x", alpha=0.2, linestyle="--")
    axes[1].legend(frameon=False)
    fig.suptitle("候选达标概率模型的交叉验证比较", fontsize=15)
    fig.tight_layout()
    fig.savefig(MODEL_IMAGE, bbox_inches="tight")
    plt.close(fig)


def plot_bmi_groups(subjects, target_week, tree, thresholds, group_table):
    set_chinese_font()
    bmi = subjects["基线BMI"].to_numpy(dtype=float)
    order = np.argsort(bmi)
    predicted = tree.predict(bmi[order].reshape(-1, 1))
    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=170)
    ax.scatter(bmi, target_week, s=28, alpha=0.48, color="#377EB8", edgecolors="white", linewidths=0.4, label="模型推导的个体90%达标孕周")
    ax.step(bmi[order], predicted, where="mid", color="#C00000", linewidth=2.7, label="CART组内预测")
    for threshold in thresholds:
        ax.axvline(threshold, color="#7F6000", linestyle="--", linewidth=1.5)
    for _, row in group_table.iterrows():
        ax.text(float(row["BMI中位数"]), float(row["推荐检测孕周"]) + 0.35, f"第{int(row['组别'])}组：{row['推荐检测孕周']:.1f}周", ha="center", fontsize=9)
    ax.set_xlabel("基线BMI")
    ax.set_ylabel("达到90%预测达标概率的最早孕周")
    ax.set_title("CART自动BMI分组与推荐NIPT时点")
    ax.grid(alpha=0.22, linestyle="--")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(GROUP_IMAGE, bbox_inches="tight")
    plt.close(fig)


def raw_logistic_equation(model) -> tuple[float, float, float] | None:
    if not isinstance(model, Pipeline) or "scale" not in model.named_steps or "model" not in model.named_steps:
        return None
    scaler = model.named_steps["scale"]
    logistic = model.named_steps["model"]
    if logistic.coef_.shape[1] != 2:
        return None
    raw_coefficients = logistic.coef_[0] / scaler.scale_
    raw_intercept = float(logistic.intercept_[0] - np.sum(logistic.coef_[0] * scaler.mean_ / scaler.scale_))
    return raw_intercept, float(raw_coefficients[0]), float(raw_coefficients[1])


def measurement_error_analysis(
    model_template,
    model_data: pd.DataFrame,
    subjects: pd.DataFrame,
    thresholds: list[float],
    chosen_leaves: int,
    minimum_leaf: int,
    week_grid: np.ndarray,
    weights: pd.Series,
    repetitions: int = 200,
):
    repeated = model_data[model_data["重复测序数"] > 1].copy()
    differences = repeated["Y浓度_最大值"] - repeated["Y浓度_最小值"]
    sigma = float(np.sqrt(np.mean(np.square(differences)) / 2.0))
    rng = np.random.default_rng(RANDOM_STATE + 77)
    x = model_data[["孕周_周", "基线BMI"]]
    original_y = model_data["是否达标_Y>=0.04"].astype(int).to_numpy()
    group_records = []
    threshold_records = []
    flip_rates = []
    subject_bmi = subjects["基线BMI"].to_numpy(dtype=float)

    for repetition in range(repetitions):
        perturbed_y_value = np.clip(
            model_data["Y浓度_中位数"].to_numpy(dtype=float)
            + rng.normal(0.0, sigma, size=len(model_data)),
            0.0,
            1.0,
        )
        simulated_y = (perturbed_y_value >= 0.04).astype(int)
        flip_rates.append(float(np.mean(simulated_y != original_y)))
        simulation_model = clone(model_template)
        fit_with_weight(simulation_model, x, pd.Series(simulated_y, index=model_data.index), weights)

        simulation_group_table = build_groups(subjects, thresholds, simulation_model, week_grid)
        for _, row in simulation_group_table.iterrows():
            group_records.append(
                {
                    "重复": repetition,
                    "组别": int(row["组别"]),
                    "推荐检测孕周": float(row["推荐检测孕周"]),
                }
            )

        simulation_probability = monotone_probability(simulation_model, subject_bmi, week_grid)
        simulation_target_week, _ = earliest_target_week(simulation_probability, week_grid)
        simulation_tree = DecisionTreeRegressor(
            max_leaf_nodes=chosen_leaves,
            min_samples_leaf=minimum_leaf,
            random_state=RANDOM_STATE + repetition,
        )
        simulation_tree.fit(subject_bmi.reshape(-1, 1), simulation_target_week)
        current_thresholds = extract_thresholds(simulation_tree)
        if len(current_thresholds) == chosen_leaves - 1:
            threshold_records.append(current_thresholds)

    group_simulations = pd.DataFrame(group_records)
    group_summary = group_simulations.groupby("组别")["推荐检测孕周"].agg(
        误差扰动中位数="median",
        误差扰动均值="mean",
    ).reset_index()
    quantiles = group_simulations.groupby("组别")["推荐检测孕周"].quantile([0.025, 0.975]).unstack()
    quantiles.columns = ["95%区间下限", "95%区间上限"]
    group_summary = group_summary.merge(quantiles.reset_index(), on="组别")

    if threshold_records:
        threshold_array = np.asarray(threshold_records)
        threshold_summary = pd.DataFrame(
            {
                "切点": np.arange(1, threshold_array.shape[1] + 1),
                "误差扰动中位数": np.median(threshold_array, axis=0),
                "95%区间下限": np.quantile(threshold_array, 0.025, axis=0),
                "95%区间上限": np.quantile(threshold_array, 0.975, axis=0),
            }
        )
    else:
        threshold_summary = pd.DataFrame(columns=["切点", "误差扰动中位数", "95%区间下限", "95%区间上限"])
    return sigma, float(np.mean(flip_rates)), group_summary, threshold_summary


def plot_error_analysis(group_table: pd.DataFrame, error_summary: pd.DataFrame):
    set_chinese_font()
    merged = group_table[["组别", "推荐检测孕周"]].merge(error_summary, on="组别")
    x = merged["组别"].to_numpy(dtype=float)
    y = merged["误差扰动中位数"].to_numpy(dtype=float)
    lower = y - merged["95%区间下限"].to_numpy(dtype=float)
    upper = merged["95%区间上限"].to_numpy(dtype=float) - y
    fig, ax = plt.subplots(figsize=(9, 5.8), dpi=170)
    ax.errorbar(x, y, yerr=np.vstack([lower, upper]), fmt="o", color="#377EB8", ecolor="#7EA6C9", capsize=6, linewidth=2, markersize=7, label="测量误差扰动后的95%区间")
    ax.scatter(x, merged["推荐检测孕周"], marker="D", s=65, color="#C00000", label="原始推荐时点", zorder=3)
    ax.set_xticks(x, [f"第{int(value)}组" for value in x])
    ax.set_ylabel("推荐检测孕周（周）")
    ax.set_title("Y染色体浓度检测误差对推荐时点的影响")
    ax.grid(axis="y", alpha=0.22, linestyle="--")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(ERROR_IMAGE, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"找不到清洗文件：{DATA_FILE}")

    tests = pd.read_excel(DATA_FILE, sheet_name="逐次检测清洗")
    subjects = pd.read_excel(DATA_FILE, sheet_name="第二问个体表")
    baseline = subjects[["孕妇代码", "基线BMI"]].copy()
    model_data = tests.merge(baseline, on="孕妇代码", how="left")
    model_data = model_data[
        [
            "孕妇代码", "孕周_周", "基线BMI", "是否达标_Y>=0.04",
            "Y浓度_中位数", "Y浓度_最小值", "Y浓度_最大值", "重复测序数",
        ]
    ].dropna(subset=["孕妇代码", "孕周_周", "基线BMI", "是否达标_Y>=0.04", "Y浓度_中位数"])
    model_data["是否达标_Y>=0.04"] = model_data["是否达标_Y>=0.04"].astype(int)

    # 每位孕妇总权重为1，避免检测次数多的孕妇支配模型。
    record_count = model_data.groupby("孕妇代码")["孕妇代码"].transform("size")
    weights = 1.0 / record_count
    x = model_data[["孕周_周", "基线BMI"]]
    y = model_data["是否达标_Y>=0.04"]
    groups = model_data["孕妇代码"]

    models = build_models()
    comparison = grouped_cross_validation(models, x, y, groups, weights)
    substantive = comparison[comparison["模型"] != "基准常数模型"].copy()
    absolute_best = substantive.iloc[0]
    model_one_se_limit = absolute_best["LogLoss均值"] + absolute_best["LogLoss标准误"]
    eligible_models = set(substantive.loc[substantive["LogLoss均值"] <= model_one_se_limit, "模型"])
    complexity_order = ["线性Logistic", "二次交互Logistic", "样条Logistic", "梯度提升树"]
    best_model_name = next(name for name in complexity_order if name in eligible_models)
    best_model = clone(models[best_model_name])
    fit_with_weight(best_model, x, y, weights)

    week_grid = np.arange(MIN_WEEK, MAX_WEEK + WEEK_STEP / 2, WEEK_STEP)
    subject_bmi = subjects["基线BMI"].to_numpy(dtype=float)
    subject_probability = monotone_probability(best_model, subject_bmi, week_grid)
    target_week, reached_target = earliest_target_week(subject_probability, week_grid)

    minimum_leaf = max(20, int(math.ceil(0.08 * len(subjects))))
    cart_cv = tree_cv_table(subject_bmi, target_week, minimum_leaf)
    chosen_leaves = int(cart_cv.loc[cart_cv["是否选择"], "目标组数"].iloc[0])
    final_tree = DecisionTreeRegressor(
        max_leaf_nodes=chosen_leaves,
        min_samples_leaf=minimum_leaf,
        random_state=RANDOM_STATE,
    )
    final_tree.fit(subject_bmi.reshape(-1, 1), target_week)
    thresholds = extract_thresholds(final_tree)
    group_table = build_groups(subjects, thresholds, best_model, week_grid)
    bootstrap = bootstrap_thresholds(subject_bmi, target_week, chosen_leaves, minimum_leaf)

    sigma, flip_rate, error_summary, error_thresholds = measurement_error_analysis(
        models[best_model_name], model_data, subjects, thresholds, chosen_leaves,
        minimum_leaf, week_grid, weights, repetitions=200,
    )

    comparison.to_csv(OUTPUT_DIR / "q2_model_comparison.csv", index=False, encoding="utf-8-sig")
    cart_cv.to_csv(OUTPUT_DIR / "q2_cart_cv.csv", index=False, encoding="utf-8-sig")
    group_table.to_csv(OUTPUT_DIR / "q2_group_recommendations.csv", index=False, encoding="utf-8-sig")
    bootstrap.to_csv(OUTPUT_DIR / "q2_cutpoint_bootstrap.csv", index=False, encoding="utf-8-sig")
    error_summary.to_csv(OUTPUT_DIR / "q2_error_timing_summary.csv", index=False, encoding="utf-8-sig")
    error_thresholds.to_csv(OUTPUT_DIR / "q2_error_cutpoint_summary.csv", index=False, encoding="utf-8-sig")

    plot_model_comparison(comparison)
    plot_probability_curves(best_model, group_table, week_grid)
    plot_bmi_groups(subjects, target_week, final_tree, thresholds, group_table)
    plot_error_analysis(group_table, error_summary)

    comparison_print = comparison.copy()
    for column in comparison_print.columns[1:]:
        comparison_print[column] = comparison_print[column].map(lambda value: f"{value:.4f}")
    group_print = group_table.copy()
    group_print["BMI中位数"] = group_print["BMI中位数"].map(lambda value: f"{value:.2f}")
    group_print["推荐检测孕周"] = group_print["推荐检测孕周"].map(lambda value: f"{value:.1f}")
    group_print["推荐时点平均达标概率"] = group_print["推荐时点平均达标概率"].map(lambda value: f"{value:.1%}")
    for column in ["85%概率时点", "90%概率时点", "95%概率时点"]:
        group_print[column] = group_print[column].map(lambda value: ">25" if pd.isna(value) else f"{value:.1f}")

    cutpoint_text = "、".join(f"{value:.2f}" for value in thresholds) if thresholds else "未形成有效切点"
    group_sentences = []
    for _, row in group_table.iterrows():
        time85 = ">25" if pd.isna(row["85%概率时点"]) else f"{row['85%概率时点']:.1f}"
        time90 = ">25" if pd.isna(row["90%概率时点"]) else f"{row['90%概率时点']:.1f}"
        time95 = ">25" if pd.isna(row["95%概率时点"]) else f"{row['95%概率时点']:.1f}"
        group_sentences.append(
            f"第{int(row['组别'])}组（{row['BMI区间']}，n={int(row['样本数'])}）的推荐检测时点为{row['推荐检测孕周']:.1f}周，"
            f"模型估计该时点的平均达标概率为{row['推荐时点平均达标概率']:.1%}；"
            f"当目标达标概率分别取85%、90%和95%时，对应时点依次为"
            f"{time85}、{time90}和{time95}周。"
        )

    selected_metrics = comparison.loc[comparison["模型"] == best_model_name].iloc[0]
    baseline_metrics = comparison.loc[comparison["模型"] == "基准常数模型"].iloc[0]
    equation = raw_logistic_equation(best_model)
    equation_text = (
        f"logit(p)={equation[0]:.4f}+{equation[1]:.4f}×孕周{equation[2]:+.4f}×BMI"
        if equation is not None
        else "最终模型为非线性模型，不写成单一线性方程。"
    )
    methods_text = textwrap.dedent(
        f"""
        【可用于论文的方法描述】
        为避免将首次观测达标孕周误认为精确生理达标时间，本文使用每名孕妇的全部纵向检测记录，定义D_ij=I(Y_ij≥0.04)，
        以检测孕周和基线BMI为解释变量建立达标概率模型。候选模型包括线性Logistic回归、含二次项与交互项的Logistic回归、
        样条Logistic回归和梯度提升树。采用按孕妇代码分组的五折交叉验证，确保同一孕妇的多次检测不会同时进入训练集与验证集，
        并以交叉验证LogLoss为主要选择指标、Brier得分和AUC为辅助指标。在绝对最小误差模型的一标准误差范围内优先选择结构更简单的模型，
        最终选择{best_model_name}，以降低样本波动导致的过拟合风险。

        最终模型的估计方程为：{equation_text}，其中p表示给定孕周和基线BMI时Y染色体浓度达到4%的概率。

        对模型给出的达标概率随孕周曲线施加单调不减约束，并定义t_0.90(BMI)=min{{w:P(Y≥0.04|BMI,w)≥0.90}}。
        决策上采用“可靠性约束下尽可能早”的词典序准则：若组平均达标概率能在25周内达到90%，取满足90%约束的最早孕周；
        若90%约束不可行，则取达到85%的最早孕周并安排后续复测，以避免为追求小幅准确率提升而过度压缩治疗窗口。
        随后以基线BMI为输入、模型预测的t_0.90为输出建立一维CART回归树，在最小叶节点样本量为{minimum_leaf}的约束下，
        比较3至5个叶节点的方案，并采用一标准误差规则选择较简单的分组结构。最终BMI切点为：{cutpoint_text}。
        """
    ).strip()

    results_text = "\n".join(
        [
            "【可用于论文的结果描述】",
            f"清洗后共纳入{model_data['孕妇代码'].nunique()}名男胎孕妇的{len(model_data)}次独立采血检测记录。",
            f"五折交叉验证中，绝对最低LogLoss由{absolute_best['模型']}取得（{absolute_best['LogLoss均值']:.4f}），但其与更简单模型的差异处于一标准误差范围内，"
            f"因此按照一标准误差规则选择{best_model_name}作为最终模型。该模型的LogLoss为{selected_metrics['LogLoss均值']:.4f}，"
            f"Brier得分为{selected_metrics['Brier均值']:.4f}，AUC为{selected_metrics['AUC均值']:.4f}。",
            f"与仅使用总体达标率的常数基准模型（LogLoss={baseline_metrics['LogLoss均值']:.4f}）相比，最终模型的误差改善有限，说明BMI和孕周对个体达标状态的区分能力偏弱，结论应结合敏感性分析解释。",
            f"在10至25周的分析范围内，共有{int(reached_target.sum())}/{len(reached_target)}名孕妇对应的BMI达到90%预测达标概率。",
            *group_sentences,
            "该分组不是直接照搬经验BMI区间，而是由模型预测的达标时点差异和CART组内误差最小化共同确定。",
            f"根据19组同次采血重复测序结果估计，Y染色体浓度的单次测量误差标准差约为{sigma:.4f}（即{sigma*100:.2f}个百分点）。",
            f"在200次蒙特卡洛误差扰动中，平均有{flip_rate:.1%}的检测记录跨越4%达标阈值；各组推荐时点的扰动区间见检测误差敏感性表。",
        ]
    )

    bootstrap_text = "【切点Bootstrap稳定性】\n" + (
        bootstrap.to_string(index=False, formatters={
            "Bootstrap中位数": "{:.2f}".format,
            "95%区间下限": "{:.2f}".format,
            "95%区间上限": "{:.2f}".format,
        })
        if len(bootstrap)
        else "Bootstrap中未能稳定形成规定数量的切点，说明BMI分组稳定性有限。"
    )
    error_text = "【检测误差敏感性：推荐时点】\n" + error_summary.to_string(
        index=False,
        formatters={
            "误差扰动中位数": "{:.2f}".format,
            "误差扰动均值": "{:.2f}".format,
            "95%区间下限": "{:.2f}".format,
            "95%区间上限": "{:.2f}".format,
        },
    )
    error_cutpoint_text = "【检测误差敏感性：BMI切点】\n" + (
        error_thresholds.to_string(
            index=False,
            formatters={
                "误差扰动中位数": "{:.2f}".format,
                "95%区间下限": "{:.2f}".format,
                "95%区间上限": "{:.2f}".format,
            },
        )
        if len(error_thresholds)
        else "误差扰动后未能稳定形成规定数量的切点。"
    )

    report = "\n\n".join(
        [
            "【候选模型交叉验证比较】\n" + comparison_print.to_string(index=False),
            "【CART组数选择】\n" + cart_cv.to_string(index=False),
            "【最终BMI分组与推荐时点】\n" + group_print.to_string(index=False),
            bootstrap_text,
            error_text,
            error_cutpoint_text,
            methods_text,
            results_text,
            "【重要解释】\n该方案以预测准确性和临床90%达标概率为依据。如果BMI切点的Bootstrap区间很宽，论文中应说明BMI单因素分组存在不确定性，不能夸大分组精度。",
        ]
    )
    REPORT_FILE.write_text(report, encoding="utf-8")

    print("=" * 86)
    print("候选模型交叉验证比较（LogLoss、Brier越低越好，AUC越高越好）")
    print(comparison_print.to_string(index=False))
    print("\n最终选择模型：", best_model_name)
    print("\nCART组数选择：")
    print(cart_cv.to_string(index=False))
    print("\n最终BMI分组与推荐检测时点：")
    print(group_print.to_string(index=False))
    print(f"\n重复测序估计的Y浓度测量误差标准差：{sigma:.6f}（{sigma*100:.3f}个百分点）")
    print(f"200次误差扰动中的平均阈值翻转比例：{flip_rate:.2%}")
    print("\n检测误差下的推荐时点稳定性：")
    print(error_summary.to_string(index=False))
    print("=" * 86)
    print(f"论文结果文字：{REPORT_FILE}")
    print(f"达标概率曲线：{CURVE_IMAGE}")
    print(f"BMI分组图片：{GROUP_IMAGE}")
    print(f"模型比较图片：{MODEL_IMAGE}")
    print(f"检测误差图片：{ERROR_IMAGE}")


if __name__ == "__main__":
    main()
