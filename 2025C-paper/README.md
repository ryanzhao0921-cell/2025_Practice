# 2025 C题练习仓库

本仓库将完整论文工程统一收在 `2025C-paper/` 文件夹中。写作、代码、数据、图片、结果和最终PDF均在该文件夹内管理。

## 目录结构

```text
2025C-paper/
├── main.tex
├── sections/
│   ├── 01_problem.tex
│   ├── 02_assumptions.tex
│   ├── 03_data.tex
│   ├── 04_q1.tex
│   ├── 05_q2.tex
│   ├── 06_q3.tex
│   └── 07_q4.tex
├── figures/
│   ├── q1/
│   └── q2/
├── code/
├── data/
│   ├── raw/
│   └── processed/
├── results/
│   ├── q1/
│   └── q2/
├── references.bib
├── build/
└── PDF/
```

## 文件放置规则

- `data/raw/`：官方原始题目和附件，禁止直接修改。
- `data/processed/`：清洗后的分析数据。
- `code/`：可以复现清洗、模型和图表的程序。
- `results/`：程序生成的表格、文本报告和中间图。
- `figures/`：最终进入论文的图片，按题号建立子目录。
- `sections/`：论文正文，每道题只修改自己的章节文件。
- `build/`：LaTeX辅助文件，不提交。
- `PDF/`：需要留档时手动放置最终PDF。

## VS Code编译

1. 在 VS Code 中打开仓库，然后展开 `2025C-paper/` 文件夹。
2. 打开 `2025C-paper/main.tex`。
3. 第一次编译时选择配方 `XeLaTeX via latexmk`；以后保存文件会自动编译。
4. 查看 `2025C-paper/build/main.pdf`，或运行 `LaTeX Workshop: View LaTeX PDF`。

仓库根目录包含 `.vscode/settings.json`，论文工程内包含 `2025C-paper/.latexmkrc`，队友克隆后无需重复配置编译器。

## 协作约定

每项具体任务从最新 `main` 创建新的 feature 分支。同一时刻尽量只由一人负责一个 `.tex`、`.py` 或 `.xlsx` 文件；图片和结果更新后，在对应题目的章节文件中引用，不直接手写图表编号。

当前 `feature/paper-q1-q2` 分支已经完成问题一和问题二的论文整合。问题一、问题二统一以“孕妇代码+检测抽血次数”作为一次采血的分析单位，共使用1021次采血观测。
