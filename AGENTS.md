# Agents Guide

## 仓库概述

[jiegec/china_bean_importers](https://github.com/jiegec/china_bean_importers)
的 hard fork：面向中国用户的 beancount 导入器（importer）集合，覆盖微信、支付宝和国内多家银行等数据源。
仅支持 beancount v3 / beangulp，要求 Python >= 3.14，不发布到 PyPI。README 与账单源数据均为中文。

## 常用命令

```shell
uv sync                                                # 安装依赖
uv run python -c 'from china_bean_importers import *'  # 冒烟测试
uv run --group dev pytest tests                    # 回归测试（合成账单）
uv run --with pylint pylint china_bean_importers       # lint（非项目依赖，CI 中带 || true，不阻塞）
```

仓库没有针对真实账单的测试;CI 通过 pytest 跑 `tests/` 下的合成账单回归测试
(用 `uv run --group dev pytest tests`),另外做上述 import 冒烟测试。验证 importer
改动最可靠的方式仍是在自己的 beancount 项目中用真实导出的账单文件运行
`python3 import.py extract -o imported.beancount documents`;新增 importer 时应
同步在 `tests/` 下为其添加基于合成账单的回归测试。

## 架构

每个数据源是 `china_bean_importers/` 下的一个子包，仅暴露 `Importer(config)`（各自 `__init__.py` 中）。
新增 importer 必须同步注册到顶层 `__init__.py` 的 import 列表和 `__all__`。

- `importer.py`：`BaseImporter` 实现 beangulp 的 `Importer` 接口。子类设置 `match_keywords`（文件识别关键词）、`file_account_name`，实现 `parse_metadata()`（解析起止日期）和 `extract()`，或走表格式范式 `extract_rows()` + `generate_tx()`。中间基类按文件类型划分：`CsvImporter`、`CsvOrXlsxImporter`、`XlsImporter`（xlsx/xls 需 pandas + openpyxl/xlrd，为可选依赖，缺失时打印警告）、`PdfImporter`（按 word 坐标 + `column_offsets` 重组表格行）、`PdfTableImporter`（pymupdf `find_tables`）。
- 例外：处理 EML 邮件账单或多格式的 importer（`alipay_web`、`boc_credit_card`、`ccb_credit_card`、`cmbc_credit_card`、`icbc_credit_card`）直接继承 beangulp 的 `Importer`，不走 `BaseImporter`。
- `common.py`：全部 importer 共享、由配置驱动的核心逻辑：
  - `BillDetailMapping`（配置项 `detail_mappings`）：按 narration/payee 关键词匹配去向账户、tag、metadata，支持 `priority` 与 `match_logic`（OR/AND）；`match_destination_and_metadata()` 汇总所有匹配结果。
  - `find_account_by_card_number()` / `match_card_tail()`：按卡号尾四位在 `card_accounts` 配置中定位账户。
  - `in_blacklist()`：银行 importer 用 `card_narration_whitelist/blacklist` 跳过经由微信/支付宝产生的交易，避免与 wechat/alipay importer 重复记账。
  - `open_pdf()`（自动尝试配置中的 `pdf_passwords`）、货币中文名→ISO 4217 映射、`unknown_account()` 兜底、`my_assert`/`my_warn`。
- `dedup.py`：仅含 `DUPLICATE_META` 常量（beancount v3 兼容）。
- `thu_ecard/decode.js`：粘贴到浏览器控制台抓取数据用的脚本，不属于 Python 运行时。

典型 extract 流程（`wechat` 是最完整的范例）：

```text
逐行解析 → 按支付方式/卡尾号确定账户1（来源）→ 特判业务类型（红包、转账、零钱通等）→
    `match_destination_and_metadata` 匹配账户2（去向）→ `unknown_account` 兜底 →
    构造双 posting 的 `data.Transaction`（支出金额为负）
```

## 配置

配置为单个全局 dict，`config.example.py` 是模板，用户复制到自己项目中（`china_bean_importer_config.py`）
并传给每个 `Importer`。`importers` 键下是各 importer 的私有子配置，
顶层键（`card_accounts`、`pdf_passwords`、`detail_mappings`、`unknown_expense_account` 等）为所有 importer 共享。
字段含义详见 README。

## 约定

- 目标 Python >= 3.14，类型标注使用 PEP 604 语法（`X | None`）。
- 各 `__init__.py` 普遍使用 `from china_bean_importers.common import *`，保持一致。
- git：日常开发在 `dev` 分支，PR 目标分支为 `master`。

