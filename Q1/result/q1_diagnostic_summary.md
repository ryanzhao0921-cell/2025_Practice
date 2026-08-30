# Q1 Diagnostic EDA Summary

Scope: read-only diagnostic EDA on `raw_data/附件.xlsx`, sheet `男胎检测数据`. Raw data were not modified. No final relationship model was fitted, no variable selection was performed, and no outliers were removed.

## Data Scope Audit

- Total male-fetus records: 1082
- Unique pregnant women: 267
- Required columns present: 孕妇代码, 检测抽血次数, 检测孕周, 孕妇BMI, 年龄, 身高, 体重, Y染色体浓度
- Gestational-week conversion: `w+d` parsed as `week + day/7`; numeric week values retained as numeric.

## Y-Week Evidence

- Complete rows used for Y-week correlation/plot: 1082
- Pearson correlation: 0.126560
- Spearman correlation: 0.084287
- Direction: positive association.
- Linear vs LOWESS diagnostic: LOWESS visibly departs from the linear fit; nonlinear form should be considered by decision layer.
- LOWESS-linear max absolute gap: 0.028358; ratio to Y SD: 0.846

Figure: `图表/q1_y_vs_week.png`

## Y-BMI Evidence

- Complete rows used for Y-BMI correlation/plot: 1082
- Pearson correlation: -0.151300
- Spearman correlation: -0.154959
- Direction: negative association.
- Linear vs LOWESS diagnostic: LOWESS visibly departs from the linear fit; nonlinear form should be considered by decision layer.
- LOWESS-linear max absolute gap: 0.057347; ratio to Y SD: 1.711

Figure: `图表/q1_y_vs_bmi.png`

## Repeated-Measurement Evidence

- Independent pregnant women: 267
- Total records: 1082
- Women with at least 2 distinct gestational-week observations: 260
- Records per woman: median = 4.0, max = 8
- Between-woman SD of individual mean Y concentration: 0.028037
- Within-woman Y range among women with repeated valid observations: median = 0.027569, 90th percentile = 0.078696
- Diagnostic interpretation: trajectories show repeated observations per woman; compare the individual-trajectory figure before treating rows as independent. The between-woman SD and within-woman ranges indicate potential baseline differences and trajectory heterogeneity, but no mixed-effects model was fitted in this round.

Figure: `图表/q1_individual_trajectories.png`

## Repeated-Sequencing Error

Grouped by `孕妇代码 + 检测抽血次数`; for groups with more than two records, within-group range/SD are reported without pairwise expansion.

- Repeated blood-draw groups: 40
- Mean absolute Y difference/range: 0.008895
- Median absolute Y difference/range: 0.008837
- 95th percentile absolute difference/range: 0.017797
- Maximum absolute difference/range: 0.023630

Figure: `图表/q1_replicate_error.png`

Detailed repeated blood-draw values:

| 孕妇代码 | 检测抽血次数 | n_records | y_min | y_max | y_range | y_sd | 序号 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A002 | 4 | 2 | 0.042675 | 0.047362 | 0.004688 | 0.003315 | 8, 9 |
| A003 | 1 | 3 | 0.054712 | 0.065185 | 0.010472 | 0.005560 | 10, 11, 12 |
| A007 | 4 | 2 | 0.034007 | 0.035200 | 0.001192 | 0.000843 | 31, 32 |
| A010 | 3 | 3 | 0.026902 | 0.033143 | 0.006240 | 0.003312 | 43, 44, 45 |
| A010 | 4 | 2 | 0.027438 | 0.032579 | 0.005141 | 0.003635 | 46, 47 |
| A023 | 3 | 3 | 0.039166 | 0.043558 | 0.004392 | 0.002293 | 94, 95, 96 |
| A026 | 1 | 3 | 0.017967 | 0.031179 | 0.013212 | 0.006882 | 106, 107, 108 |
| A026 | 4 | 2 | 0.094117 | 0.096272 | 0.002155 | 0.001524 | 111, 112 |
| A027 | 4 | 3 | 0.163174 | 0.165248 | 0.002074 | 0.001087 | 116, 117, 118 |
| A029 | 2 | 2 | 0.038363 | 0.041186 | 0.002823 | 0.001996 | 124, 125 |
| A029 | 4 | 3 | 0.085871 | 0.095799 | 0.009928 | 0.005295 | 127, 128, 129 |
| A032 | 4 | 2 | 0.083473 | 0.085154 | 0.001681 | 0.001189 | 141, 142 |
| A035 | 3 | 2 | 0.033125 | 0.050768 | 0.017643 | 0.012476 | 153, 154 |
| A041 | 3 | 3 | 0.031305 | 0.037199 | 0.005894 | 0.002958 | 178, 179, 180 |
| A041 | 4 | 3 | 0.026088 | 0.041189 | 0.015100 | 0.007945 | 181, 182, 183 |
| A049 | 1 | 3 | 0.071869 | 0.077439 | 0.005570 | 0.002943 | 212, 213, 214 |
| A055 | 3 | 2 | 0.050333 | 0.056394 | 0.006061 | 0.004286 | 240, 241 |
| A055 | 4 | 3 | 0.079357 | 0.084048 | 0.004691 | 0.002430 | 242, 243, 244 |
| A066 | 1 | 3 | 0.026986 | 0.040974 | 0.013988 | 0.007228 | 285, 286, 287 |
| A069 | 1 | 3 | 0.078611 | 0.085943 | 0.007331 | 0.003673 | 299, 300, 301 |
| A069 | 4 | 3 | 0.065545 | 0.075399 | 0.009855 | 0.005335 | 304, 305, 306 |
| A073 | 4 | 3 | 0.061930 | 0.066187 | 0.004258 | 0.002231 | 321, 322, 323 |
| A079 | 2 | 3 | 0.031315 | 0.032965 | 0.001650 | 0.000944 | 339, 340, 341 |
| A079 | 3 | 3 | 0.042604 | 0.051643 | 0.009039 | 0.004573 | 342, 343, 344 |
| A084 | 4 | 2 | 0.092456 | 0.107804 | 0.015348 | 0.010852 | 360, 361 |
| A091 | 1 | 2 | 0.090533 | 0.094202 | 0.003669 | 0.002595 | 384, 385 |
| A091 | 4 | 3 | 0.116126 | 0.125851 | 0.009724 | 0.005086 | 388, 389, 390 |
| A096 | 3 | 2 | 0.046008 | 0.063180 | 0.017172 | 0.012142 | 409, 410 |
| A109 | 4 | 2 | 0.068474 | 0.080365 | 0.011891 | 0.008408 | 462, 463 |
| A111 | 1 | 2 | 0.043477 | 0.048931 | 0.005454 | 0.003856 | 468, 469 |
| A111 | 3 | 2 | 0.055729 | 0.060431 | 0.004702 | 0.003325 | 471, 472 |
| A114 | 2 | 3 | 0.033147 | 0.041782 | 0.008635 | 0.004427 | 483, 484, 485 |
| A130 | 4 | 2 | 0.107131 | 0.130762 | 0.023630 | 0.016709 | 537, 538 |
| A141 | 3 | 2 | 0.089201 | 0.100465 | 0.011265 | 0.007965 | 575, 576 |
| A141 | 4 | 2 | 0.114168 | 0.127463 | 0.013295 | 0.009401 | 577, 578 |
| A146 | 3 | 3 | 0.061680 | 0.082393 | 0.020713 | 0.010868 | 596, 597, 598 |
| A147 | 3 | 2 | 0.033170 | 0.048316 | 0.015146 | 0.010710 | 602, 603 |
| A155 | 2 | 3 | 0.034721 | 0.045971 | 0.011250 | 0.005955 | 636, 637, 638 |
| A155 | 3 | 3 | 0.046575 | 0.056020 | 0.009444 | 0.004742 | 639, 640, 641 |
| A163 | 3 | 2 | 0.027892 | 0.037289 | 0.009397 | 0.006644 | 668, 669 |


## BMI / Weight / Height Collinearity

Pearson correlation matrix:

|  | BMI | Weight | Height |
| --- | --- | --- | --- |
| BMI | 1.000000 | 0.835304 | 0.088037 |
| Weight | 0.835304 | 1.000000 | 0.618591 |
| Height | 0.088037 | 0.618591 | 1.000000 |


VIF using BMI, Weight, Height, Age only as a diagnostic, with no automatic deletion decision:

| variable | R2_against_others | VIF |
| --- | --- | --- |
| BMI | 0.995425 | 218.599591 |
| Weight | 0.997154 | 351.342309 |
| Height | 0.990646 | 106.904917 |
| Age | 0.011843 | 1.011985 |


## Minimal Data-Quality Check

- Y concentration missing: 0
- BMI missing: 0
- Gestational week missing: 0
- Gestational week parsing failures among nonmissing entries: 0
- Pregnant women with repeated valid gestational-week observations: 260
- Completely duplicated records: 0

Most important data risks:

- Same blood-draw repeated sequencing exists in 40 groups, so measurement-error sensitivity may be relevant.

## Stop Condition

Completed only the requested high-value Diagnostic EDA for Q1. No final model, variable-selection procedure, outlier deletion, raw-data modification, or Q2 work was performed.
