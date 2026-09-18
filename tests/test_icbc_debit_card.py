# ICBC debit card PDF statement (table-based PdfTableImporter).

import pymupdf

import helpers
import pdfgen

from china_bean_importers import icbc_debit_card

COLS = [
    "交易日期",
    "帐号",
    "储种",
    "序号",
    "币种",
    "钞汇",
    "摘要",
    "地区",
    "收入/支出金额",
    "余额",
    "对方户名",
    "对方帐号",
    "渠道",
]


def build_icbc_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page(width=1200, height=842)
    pdfgen.header_lines(
        page,
        [
            "中国工商银行借记账户历史明细（电子版）",
            "起止日期：2024-01-01 — 2024-02-01",
            "户名：测试",
            "卡号 6222020200000004444",
        ],
    )
    rows = [
        COLS,
        [
            "2024-01-05 10:00:00",
            "6222020200000004444",
            "活期",
            "1",
            "人民币",
            "钞",
            "京东购物",
            "北京",
            "-25.00",
            "1000.00",
            "张三",
            "622200000000000999",
            "手机银行",
        ],
        [
            "2024-01-06 11:00:00",
            "6222020200000004444",
            "活期",
            "2",
            "人民币",
            "钞",
            "支付宝转账",
            "北京",
            "-30.00",
            "970.00",
            "李四",
            "------",
            "手机银行",
        ],
        [
            "2024-01-07 12:00:00",
            "6222020200000004444",
            "活期",
            "3",
            "人民币",
            "钞",
            "美团支付退款",
            "北京",
            "10.00",
            "980.00",
            "张三",
            "------",
            "手机银行",
        ],
    ]
    pdfgen.draw_table(page, 50, 130, rows)
    doc.save(path)
    doc.close()
    return path


def test_icbc_debit_card(tmp_path, capsys):
    path = build_icbc_pdf(tmp_path / "icbc.pdf")
    imp, entries = helpers.run_importer(
        icbc_debit_card.Importer, helpers.make_config(), path
    )

    assert imp.date(path).isoformat().startswith("2024-01-01")
    # blacklisted expense skipped; blacklisted income kept
    err = capsys.readouterr().err
    assert "blacklist" in err and "Income kept" in err
    helpers.assert_txns(
        [
            (
                "2024-01-05",
                "张三",
                "京东购物",
                "Assets:Card:ICBC",
                "Expenses:JD",
                "-25.00 CNY",
            ),
            (
                "2024-01-07",
                "张三",
                "美团支付退款",
                "Assets:Card:ICBC",
                "Income:Unknown",
                "10.00 CNY",
            ),
        ],
        entries,
    )
    # icbc keeps the raw remainder of the date cell as time (leading space
    # included), matching real statement parsing
    assert entries[0].meta["time"] == " 10:00:00"
    assert entries[0].meta["account"] == "6222020200000004444"
