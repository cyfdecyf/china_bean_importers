# BOC debit card PDF statement (table-based PdfTableImporter).

import pymupdf

import helpers
import pdfgen

from china_bean_importers import boc_debit_card

COLS = [
    "记账日期",
    "记账时间",
    "币别",
    "金额",
    "余额",
    "交易名称",
    "渠道",
    "网点名称",
    "附言",
    "对方账户名",
    "对方卡号/账号",
    "对方开户行",
]


def row(date, time, amount, balance, name, remark, payee, payee_acc, payee_bank):
    return [
        date,
        time,
        "人民币",
        amount,
        balance,
        name,
        "手机银行",
        "------",
        remark,
        payee,
        payee_acc,
        payee_bank,
    ]


def build_boc_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page(width=1200, height=842)
    pdfgen.header_lines(
        page,
        [
            "中国银行交易流水明细清单",
            "客户姓名：测试",
            "交易区间：2024-01-01 至 2024-02-01",
            "6222020000000001111",
        ],
    )
    rows = [
        COLS,
        row("2024-01-05", "10:00:00", "-25.00", "1000.00", "消费", "京东购物", "张三", "------", "------"),
        row("2024-01-06", "11:00:00", "500.00", "1500.00", "消费", "还款", "测试", "6222020000000001111", "中国银行"),
        # blacklisted narration (支付宝), expense: skipped
        row("2024-01-07", "12:00:00", "-30.00", "1470.00", "支付宝转账", "------", "李四", "------", "------"),
    ]
    pdfgen.draw_table(page, 50, 120, rows)
    doc.save(path)
    doc.close()
    return path


def test_boc_debit_card(tmp_path, capsys):
    path = build_boc_pdf(tmp_path / "boc.pdf")
    imp, entries = helpers.run_importer(
        boc_debit_card.Importer, helpers.make_config(), path
    )

    assert imp.date(path).isoformat().startswith("2024-01-01")
    assert "blacklist" in capsys.readouterr().err
    helpers.assert_txns(
        [
            (
                "2024-01-05",
                "张三",
                "京东购物",
                "Assets:Card:BoC",
                "Expenses:JD",
                "-25.00 CNY",
            ),
            (
                "2024-01-06",
                "测试",
                "还款",
                "Assets:Card:BoC",
                "Assets:Card:BoC",
                "500.00 CNY",
            ),
        ],
        entries,
    )
    # payee equals the real name and carries a known card number: transfer
    assert entries[1].meta["payee_account"] == "6222020000000001111"
    assert entries[0].meta["time"] == "10:00:00"
    assert entries[0].meta["imported_category"] == "消费"
