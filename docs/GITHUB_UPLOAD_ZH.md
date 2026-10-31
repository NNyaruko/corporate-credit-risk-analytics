# 上传 GitHub 与本地运行

这是一个独立制作的、使用合成数据的信用风险分析作品集。可以公开展示分析方法、代码和 Office 成果。它不包含招商银行或其他机构的客户资料、内部模型或内部工作成果。

## 1. 先查看作品

1. 解压 `corporate-credit-risk-analytics.zip`。
2. 打开 `outputs/Credit_Risk_Review.xlsx`，从 Summary 工作表开始查看。
3. 打开 `outputs/Credit_Risk_Memo.pdf` 阅读信贷分析备忘录。
4. 打开 `outputs/Credit_Risk_Review.pptx` 查看汇报材料。
5. 打开 `README.md` 查看整体项目结构。上传后，GitHub 会自动把它显示在仓库首页。

这些成品可以直接阅读，不需要先安装 Python、R 或 SAS。Excel 文件是无宏的 `.xlsx`，VBA 模块单独提供。

## 2. 创建 GitHub 仓库

1. 登录 GitHub，点击右上角 **+ → New repository**。
2. Repository name 填写 `corporate-credit-risk-analytics`。
3. Description 可以填写：

   `Synthetic corporate credit-risk portfolio: logistic regression, model validation, stress scenarios, R/SAS implementations, and Excel/Word/PowerPoint reporting.`

4. 选择 **Public**，方便审核人员直接查看。
5. 不勾选自动生成 README、license 或 .gitignore；压缩包已经包含这些文件。
6. 点击 **Create repository**。

## 3. 上传解压后的文件

在新仓库页面选择 **uploading an existing file**。把解压后项目目录里面的文件和文件夹拖进去，然后点击 **Commit changes**。

**README.md 必须位于仓库最外层。不要只上传 ZIP，也不要再套一层同名文件夹。** 正确结构是仓库打开后立即看到 README.md、src、data、outputs、r、sas 和 excel 等项目。

如果浏览器限制一次上传的文件数量，可以分几次上传。先上传 README.md、requirements.txt、LICENSE、.gitignore 和 docs，再上传各个目录。不要把本地 `.venv`、`__pycache__` 或临时渲染文件上传。使用 GitHub Desktop 添加本地仓库也可以保留完整目录结构。

上传完，检查首页图片能否显示，点开 `notebooks/credit_risk_walkthrough.ipynb`，再下载 Excel 或 PDF 确认链接正常。

## 4. 申请表填写哪个链接

填写仓库网页链接，例如你的用户名仍是 NNyaruko 时：

`https://github.com/NNyaruko/corporate-credit-risk-analytics`

这是仓库创建后的预期地址；只有成功创建并上传后才能使用。申请表无需使用以 `.git` 结尾的 clone 地址。

如有作品说明栏，可以写：

> Independent corporate credit-risk work sample using synthetic data, with reproducible modeling, out-of-time validation, scenario analysis, and Excel, Word, and PowerPoint deliverables.

## 5. 在 Windows 上运行 Python 分析

安装 Python 3.11 或更新的兼容版本。打开项目目录，在地址栏输入 `powershell` 后回车，依次运行：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.pipeline
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

不需要运行 PowerShell 激活脚本。脚本会在项目内部重新生成模拟数据、预测结果、验证表和图，不连接任何银行系统。

## 6. 在 macOS 或 Linux 上运行

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m src.pipeline
.venv/bin/python -m unittest discover -s tests -v
```

## 7. R、SAS 与高级 Excel

- R 的入口和依赖说明见 `r/README.md`。
- SAS 需自行提供 SAS 环境，使用方式见 `sas/README.md`。
- Power Query、Power Pivot/DAX、VBA 的导入步骤见 `excel/README.md`。
- R/SAS 与 Python 的对照方式见 `docs/CROSS_TOOL_VALIDATION.md`。

Python 分析流程与已保存的 Office 成品是两个层次。运行 Python 不会自动重建全部 Office 文件。Office 生成代码、适用环境和验证限制分别记录在 `excel/`、`reports/` 中。

## 8. 面试前建议能够解释

- 为什么将训练、验证、测试数据按时间分开？为什么额外留出标签成熟期？
- 为什么用多变量 logistic regression 估计二元违约概率？
- 为什么 ROC-AUC 好不等于概率校准好？
- 分类阈值在哪里选定，混淆矩阵如何计算？
- 利率和 GDP 的百分点评移与 DSCR 的比例变动有什么不同？
- 为什么 `debt × PD × 45%` 只是演示性损失代理，不能称为完整 IFRS 9 计量？
- 哪些 Excel 计算可直接编辑？哪些 Power Query、DAX、VBA 功能需要手动配置？
- 合成样本上的统计显著性为什么不能证明真实银行组合中的因果关系？

展示时可以明确说这是根据金融分析工作流程制作的公开示例。它证明的是本仓库中可以检查和运行的内容，不用于证明银行项目的客户规模或历史业绩。
