# SPDB debit card PDF statement (table-based PdfTableImporter with a
# two-line header cell).

import pymupdf

import helpers
import pdfgen

from china_bean_importers import spdb_debit_card

# Header cells drawn manually: the first cell has two lines ("交易日期" over
# "Date") which find_tables joins with a newline.


def build_spdb_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page(width=1200, height=842)
    pdfgen.header_lines(
        page,
        [
            "上海浦东发展银行个人客户交易流水专用回单",
            "起止日期:20240105-20240201",
            "户名:测试",
            "账号:6222010000006666",
            "Currency:CNY",
        ],
    )
    headers = ["交易日期\nDate", "交易时间", "交易账号", "交易名称", "交易金额", "账户余额", "对手姓名", "对手账号", "交易摘要"]
    rows = [headers]
    rows.append(["2024-01-05", "100000", "6222010000006666", "京东购物", "-25.00", "1000.00", "张三", "6222020000000001111", "网上支付"])
    rows.append(["2024-01-06", "110000", "6222010000006666", "充值", "100.00", "1100.00", "李四", "------", "柜台充值"])
    pdfgen.draw_table(page, 50, 130, rows)
    doc.save(path)
    doc.close()
    return path


def test_spdb_debit_card(tmp_path):
    path = build_spdb_pdf(tmp_path / "spdb.pdf")
    imp, entries = helpers.run_importer(
        spdb_debit_card.Importer, helpers.make_config(), path
    )

    assert imp.date(path).isoformat().startswith("2024-01-05")
    helpers.assert_txns(
        [
            (
                "2024-01-05",
                "张三",
                "京东购物",
                "Assets:Card:SPDB",
                "Assets:Card:BoC",
                "-25.00 CNY",
            ),
            (
                "2024-01-06",
                "李四",
                "充值",
                "Assets:Card:SPDB",
                "Income:Unknown",
                "100.00 CNY",
            ),
        ],
        entries,
    )
    assert entries[0].meta["time"] == "10:00:00"
    assert entries[0].meta["balance"] == "1000.00"
    assert entries[0].meta["payee_account"] == "6222020000000001111"
