# -*- coding: utf-8 -*-
"""
CUMCM 2025 C题 - 问题一最终模型复现脚本

冻结口径：
1) 男胎检测数据
2) 主分析单位：一次采血
3) 同一“孕妇代码 + 检测抽血次数”的重复测序，Y染色体浓度取均值
4) 检测孕周转换为连续周数，并中心化
5) 最终模型：
   Y ~ centered_week + centered_week^2 + BMI + Age
   随机效应：孕妇层面的随机截距 + centered_week 随机斜率
6) 使用原始未聚合记录拟合同一模型做敏感性分析
7) 输出固定效应、随机效应、拟合指标和论文用图

依赖：
pandas, numpy, matplotlib, scipy, statsmodels, openpyxl
"""

from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats
import statsmodels.formula.api as smf

warnings.filterwarnings("ignore")

# =========================
# 0. 路径
# =========================
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "attachment.xlsx"
FIG_DIR = PROJECT_ROOT / "figures" / "q1"
RESULT_DIR = PROJECT_ROOT / "results" / "q1"

FIG_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

SHEET_NAME = "男胎检测数据"

# =========================
# 1. 工具函数
# =========================
def parse_gestational_week(x):
    """
    将孕周转换为连续周数。
    支持：
    - 数字：15.5
    - '11w+6' / '11W+6'
    - '11+6'
    - 常见中文/英文周天表达
    """
    if pd.isna(x):
        return np.nan

    if isinstance(x, (int, float, np.integer, np.floating)):
        return float(x)

    s = str(x).strip().lower()
    if not s:
        return np.nan

    # 直接数字
    try:
        return float(s)
    except ValueError:
        pass

    # 清理常见格式
    s = (s.replace("周", "w")
           .replace("星期", "w")
           .replace("weeks", "w")
           .replace("week", "w")
           .replace("天", "")
           .replace("d", "")
           .replace(" ", ""))

    # 11w+6 / 11w6
    if "w" in s:
        left, right = s.split("w", 1)
        right = right.lstrip("+")
        try:
            week = float(left)
            day = float(right) if right != "" else 0.0
            return week + day / 7.0
        except ValueError:
            return np.nan

    # 11+6
    if "+" in s:
        parts = s.split("+")
        if len(parts) == 2:
            try:
                return float(parts[0]) + float(parts[1]) / 7.0
            except ValueError:
                return np.nan

    return np.nan


def fit_lmm(df, week_center):
    """
    拟合最终冻结 LMM。
    注意使用 ML (reml=False)，便于得到 AIC/BIC。
    """
    d = df.copy()
    d["centered_week"] = d["week"] - week_center
    d["centered_week_sq"] = d["centered_week"] ** 2

    model = smf.mixedlm(
        "Y ~ centered_week + centered_week_sq + BMI + Age",
        data=d,
        groups=d["woman"],
        re_formula="1 + centered_week",
    )

    # 与最终报告口径一致，使用最大似然 ML
    result = model.fit(
        reml=False,
        method="lbfgs",
        maxiter=2000,
        disp=False,
    )
    return d, result


def fixed_effect_table(result):
    """整理固定效应表。"""
    names = ["Intercept", "centered_week", "centered_week_sq", "BMI", "Age"]
    ci = result.conf_int()

    rows = []
    for term in names:
        rows.append({
            "term": term,
            "coefficient": float(result.params[term]),
            "std_error": float(result.bse[term]),
            "ci_low": float(ci.loc[term, 0]),
            "ci_high": float(ci.loc[term, 1]),
            "p_value": float(result.pvalues[term]),
        })
    return pd.DataFrame(rows)


def random_effect_summary(result):
    """整理随机效应与残差。"""
    cov_re = result.cov_re.copy()

    # statsmodels 通常随机截距名为 Group，随机斜率名为 centered_week
    intercept_name = cov_re.index[0]
    slope_name = "centered_week"

    var_intercept = float(cov_re.loc[intercept_name, intercept_name])
    var_slope = float(cov_re.loc[slope_name, slope_name])
    cov_is = float(cov_re.loc[intercept_name, slope_name])

    sd_intercept = np.sqrt(max(var_intercept, 0))
    sd_slope = np.sqrt(max(var_slope, 0))

    if sd_intercept > 0 and sd_slope > 0:
        corr = cov_is / (sd_intercept * sd_slope)
    else:
        corr = np.nan

    resid_var = float(result.scale)
    resid_sd = np.sqrt(max(resid_var, 0))

    return {
        "random_intercept_variance": var_intercept,
        "random_intercept_sd": sd_intercept,
        "random_slope_variance": var_slope,
        "random_slope_sd": sd_slope,
        "intercept_slope_correlation": corr,
        "residual_variance": resid_var,
        "residual_sd": resid_sd,
    }


def significance_label(p):
    if p < 0.001:
        return "<0.001"
    return f"{p:.4f}"


# =========================
# 2. 读取数据
# =========================
if not DATA_PATH.exists():
    raise FileNotFoundError(
        f"未找到数据文件：{DATA_PATH}\n"
        "请确认脚本位于 2025C-paper/code/，且原始数据位于 2025C-paper/data/raw/attachment.xlsx"
    )

raw = pd.read_excel(DATA_PATH, sheet_name=SHEET_NAME)

required_cols = [
    "孕妇代码", "检测抽血次数", "检测孕周",
    "孕妇BMI", "年龄", "Y染色体浓度"
]
missing_cols = [c for c in required_cols if c not in raw.columns]
if missing_cols:
    raise KeyError(f"缺少必要列：{missing_cols}")

df = raw[required_cols].copy()
df = df.rename(columns={
    "孕妇代码": "woman",
    "检测抽血次数": "draw_no",
    "检测孕周": "week_raw",
    "孕妇BMI": "BMI",
    "年龄": "Age",
    "Y染色体浓度": "Y",
})

df["week"] = df["week_raw"].apply(parse_gestational_week)

for c in ["BMI", "Age", "Y", "draw_no"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

df = df.dropna(subset=["woman", "draw_no", "week", "BMI", "Age", "Y"]).copy()

# =========================
# 3. 主分析：同次采血重复测序聚合
# =========================
# 同一次采血的孕周/BMI/Age理论上应一致。
# 为避免极小格式差异，连续变量取均值；Y按冻结口径取均值。
blood_draw = (
    df.groupby(["woman", "draw_no"], as_index=False)
      .agg(
          week=("week", "mean"),
          BMI=("BMI", "mean"),
          Age=("Age", "mean"),
          Y=("Y", "mean"),
          n_seq=("Y", "size"),
      )
)

# 中心化常数只由主分析 blood-draw 数据确定；
# 敏感性分析也使用同一个中心，便于比较系数。
WEEK_CENTER = float(blood_draw["week"].mean())

main_data, main_result = fit_lmm(blood_draw, WEEK_CENTER)

# =========================
# 4. 最终参数结果
# =========================
fixed_tbl = fixed_effect_table(main_result)
random_summary = random_effect_summary(main_result)

n_obs = len(main_data)
n_women = main_data["woman"].nunique()

print("\n========== Fixed Effects ==========")
print(fixed_tbl.to_string(index=False))

print("\n========== Random Effects ==========")
for k, v in random_summary.items():
    print(f"{k}: {v:.9f}")

print("\n========== Model Fit ==========")
print(f"Blood-draw observations: {n_obs}")
print(f"Women: {n_women}")
print(f"Log-likelihood: {main_result.llf:.6f}")
print(f"AIC: {main_result.aic:.6f}")
print(f"BIC: {main_result.bic:.6f}")
print(f"Converged: {main_result.converged}")
print(f"Week center: {WEEK_CENTER:.6f}")

# =========================
# 5. 敏感性分析：原始未聚合记录
# =========================
raw_for_model = df[["woman", "week", "BMI", "Age", "Y"]].copy()
sens_data, sens_result = fit_lmm(raw_for_model, WEEK_CENTER)
sens_tbl = fixed_effect_table(sens_result)

compare = fixed_tbl[["term", "coefficient", "p_value"]].merge(
    sens_tbl[["term", "coefficient", "p_value"]],
    on="term",
    suffixes=("_main", "_unaggregated")
)
compare["sign_same"] = (
    np.sign(compare["coefficient_main"]) ==
    np.sign(compare["coefficient_unaggregated"])
)
compare["sig_main_0.05"] = compare["p_value_main"] < 0.05
compare["sig_unaggregated_0.05"] = compare["p_value_unaggregated"] < 0.05
compare["sig_conclusion_same"] = (
    compare["sig_main_0.05"] ==
    compare["sig_unaggregated_0.05"]
)

print("\n========== Sensitivity Analysis ==========")
print(compare.to_string(index=False))

# =========================
# 6. 模型诊断图
# =========================
fitted = np.asarray(main_result.fittedvalues)
resid = np.asarray(main_result.resid)

# 6.1 残差 vs 拟合值
plt.figure(figsize=(7, 5))
plt.scatter(fitted, resid, alpha=0.45, s=16)
plt.axhline(0, linewidth=1)
plt.xlabel("Fitted Y concentration")
plt.ylabel("Residual")
plt.title("Residuals vs Fitted")
plt.tight_layout()
plt.savefig(FIG_DIR / "q1_residual_vs_fitted.png", dpi=300, bbox_inches="tight")
plt.close()

# 6.2 Q-Q 图
plt.figure(figsize=(6, 6))
stats.probplot(resid, dist="norm", plot=plt)
plt.title("Q-Q Plot of Residuals")
plt.tight_layout()
plt.savefig(FIG_DIR / "q1_residual_qq.png", dpi=300, bbox_inches="tight")
plt.close()

# =========================
# 7. 不同 BMI 水平下预测曲线
# =========================
bmi_levels = main_data["BMI"].quantile([0.25, 0.50, 0.75])
age_fixed = float(main_data["Age"].mean())

week_grid = np.linspace(
    main_data["week"].quantile(0.01),
    main_data["week"].quantile(0.99),
    250,
)

fe = main_result.fe_params

plt.figure(figsize=(8, 5.5))

for q, bmi_value in bmi_levels.items():
    cw = week_grid - WEEK_CENTER
    pred = (
        fe["Intercept"]
        + fe["centered_week"] * cw
        + fe["centered_week_sq"] * cw**2
        + fe["BMI"] * bmi_value
        + fe["Age"] * age_fixed
    )
    plt.plot(
        week_grid,
        pred,
        linewidth=2,
        label=f"BMI {int(q*100)}th percentile = {bmi_value:.2f}",
    )

plt.axhline(0.04, linestyle="--", linewidth=1.2, label="Y = 4% threshold")
plt.xlabel("Gestational week")
plt.ylabel("Predicted Y chromosome concentration")
plt.title("Predicted Y Concentration by Gestational Week and BMI")
plt.legend()
plt.tight_layout()
plt.savefig(FIG_DIR / "q1_predicted_Y_by_week_BMI.png", dpi=300, bbox_inches="tight")
plt.close()

# =========================
# 8. 输出 Markdown 摘要
# =========================
summary_path = RESULT_DIR / "q1_final_model_summary_reproduced.md"

def fmt_ci(lo, hi):
    return f"[{lo:.6f}, {hi:.6f}]"

lines = []
lines.append("# Q1 Final Model Summary\n")
lines.append(f"- Blood-draw observations: {n_obs}")
lines.append(f"- Women: {n_women}")
lines.append(f"- Week centering constant: {WEEK_CENTER:.6f}")
lines.append(f"- Log-likelihood: {main_result.llf:.6f}")
lines.append(f"- AIC: {main_result.aic:.6f}")
lines.append(f"- BIC: {main_result.bic:.6f}")
lines.append(f"- Converged: {main_result.converged}\n")

lines.append("## Fixed Effects\n")
lines.append("| term | coefficient | std. error | 95% CI | p-value |")
lines.append("|---|---:|---:|---:|---:|")
for _, r in fixed_tbl.iterrows():
    lines.append(
        f"| {r['term']} | {r['coefficient']:.6f} | "
        f"{r['std_error']:.6f} | {fmt_ci(r['ci_low'], r['ci_high'])} | "
        f"{significance_label(r['p_value'])} |"
    )

lines.append("\n## Random Effects\n")
for k, v in random_summary.items():
    lines.append(f"- {k}: {v:.9f}")

lines.append("\n## Sensitivity Analysis\n")
lines.append(compare.to_markdown(index=False))

lines.append("\n## Figure Paths\n")
lines.append("- 图表/q1_residual_vs_fitted.png")
lines.append("- 图表/q1_residual_qq.png")
lines.append("- 图表/q1_predicted_Y_by_week_BMI.png")

summary_path.write_text("\n".join(lines), encoding="utf-8")

print("\n========== Saved ==========")
print(f"Code: {Path(__file__).resolve()}")
print(f"Summary: {summary_path}")
print(f"Figures: {FIG_DIR}")
