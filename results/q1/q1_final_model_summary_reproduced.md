# Q1 Final Model Summary

- Blood-draw observations: 1021
- Women: 267
- Week centering constant: 16.667343
- Log-likelihood: 2463.644746
- AIC: -4909.289493
- BIC: -4864.932653
- Converged: True

## Fixed Effects

| term | coefficient | std. error | 95% CI | p-value |
|---|---:|---:|---:|---:|
| Intercept | 0.138148 | 0.022057 | [0.094917, 0.181379] | <0.001 |
| centered_week | 0.003176 | 0.000253 | [0.002680, 0.003673] | <0.001 |
| centered_week_sq | 0.000264 | 0.000034 | [0.000197, 0.000331] | <0.001 |
| BMI | -0.001486 | 0.000524 | [-0.002512, -0.000459] | 0.0046 |
| Age | -0.000515 | 0.000487 | [-0.001469, 0.000440] | 0.2908 |

## Random Effects

- random_intercept_variance: 0.000903303
- random_intercept_sd: 0.030054992
- random_slope_variance: 0.000007423
- random_slope_sd: 0.002724508
- intercept_slope_correlation: 0.485073098
- residual_variance: 0.000175874
- residual_sd: 0.013261740

## Sensitivity Analysis

| term             |   coefficient_main |   p_value_main |   coefficient_unaggregated |   p_value_unaggregated | sign_same   | sig_main_0.05   | sig_unaggregated_0.05   | sig_conclusion_same   |
|:-----------------|-------------------:|---------------:|---------------------------:|-----------------------:|:------------|:----------------|:------------------------|:----------------------|
| Intercept        |        0.138148    |    3.77087e-10 |                0.134142    |            9.15718e-10 | True        | True            | True                    | True                  |
| centered_week    |        0.00317639  |    4.75334e-36 |                0.0031972   |            2.7805e-36  | True        | True            | True                    | True                  |
| centered_week_sq |        0.000263752 |    1.45095e-14 |                0.000269831 |            1.42644e-16 | True        | True            | True                    | True                  |
| BMI              |       -0.00148552  |    0.00458005  |               -0.00139471  |            0.00696388  | True        | True            | True                    | True                  |
| Age              |       -0.000514631 |    0.290768    |               -0.00048136  |            0.323838    | True        | False           | False                   | True                  |

## Figure Paths

- 图表/q1_residual_vs_fitted.png
- 图表/q1_residual_qq.png
- 图表/q1_predicted_Y_by_week_BMI.png