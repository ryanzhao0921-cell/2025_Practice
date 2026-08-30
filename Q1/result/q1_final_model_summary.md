# Q1 Final Linear Mixed-Effects Model Summary

Analysis unit: blood draw. Repeated Y concentration records with the same 孕妇代码 + 检测抽血次数 were averaged for main analysis. Current blood-draw BMI was retained.

Centered week definition: centered_week = gestational_week - 16.667343. Prediction figure uses BMI Q25=30.18, Q50=31.79, Q75=33.86; Age fixed at mean Age=28.90.

## A. Fixed Effects

| term | coefficient | std_error | ci_95_low | ci_95_high | p_value |
| --- | --- | --- | --- | --- | --- |
| Intercept | 0.138148 | 0.0220571 | 0.0949174 | 0.181379 | 3.77087e-10 |
| centered_week | 0.00317639 | 0.000253384 | 0.00267976 | 0.00367301 | 4.75334e-36 |
| centered_week_sq | 0.000263752 | 3.42901e-05 | 0.000196545 | 0.000330959 | 1.45095e-14 |
| BMI | -0.00148552 | 0.000523961 | -0.00251247 | -0.000458577 | 0.00458005 |
| Age | -0.000514631 | 0.000487137 | -0.0014694 | 0.000440141 | 0.290768 |

## B. Random Effects

| quantity | value |
| --- | --- |
| random_intercept_variance | 0.000903303 |
| random_intercept_SD | 0.030055 |
| random_slope_variance_centered_week | 7.42294e-06 |
| random_slope_SD_centered_week | 0.00272451 |
| intercept_slope_correlation | 0.485073 |
| residual_variance | 0.000175874 |
| residual_SD | 0.0132617 |

## C. Model Fit

| n_blood_draw_observations | n_women | log_likelihood | AIC | BIC | converged |
| --- | --- | --- | --- | --- | --- |
| 1021 | 267 | 2463.64 | -4909.29 | -4864.93 | True |

## D. Minimal Diagnostics

未见明显严重违背；残差-拟合图未显示强系统性曲线，Q-Q图尾部有一定偏离但不构成明显严重异常。

## E. Sensitivity: Original Unaggregated Records

| term | main_coef | unaggregated_coef | same_sign | main_p | unaggregated_p | main_sig_0.05 | unaggregated_sig_0.05 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| centered_week | 0.00317639 | 0.0031972 | True | 4.75334e-36 | 2.7805e-36 | True | True |
| centered_week_sq | 0.000263752 | 0.000269831 | True | 1.45095e-14 | 1.42644e-16 | True | True |
| BMI | -0.00148552 | -0.00139471 | True | 0.00458005 | 0.00696388 | True | True |
| Age | -0.000514631 | -0.00048136 | True | 0.290768 | 0.323838 | False | False |

Substantive conclusion changes: No. Coefficient signs and significance conclusions for Week, Week^2, BMI, and Age are substantively unchanged.

## Output Paths

- /Users/theromsoltheromsol/Desktop/2025C/result/q1_final_model_summary.md

- /Users/theromsoltheromsol/Desktop/2025C/图表/q1_residual_vs_fitted.png

- /Users/theromsoltheromsol/Desktop/2025C/图表/q1_residual_qq.png

- /Users/theromsoltheromsol/Desktop/2025C/图表/q1_predicted_Y_by_week_BMI.png