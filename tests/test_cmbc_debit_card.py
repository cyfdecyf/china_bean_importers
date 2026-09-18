# CMBC debit card PDF statement (coordinate-based PdfImporter).

import pymupdf

import helpers
import pdfgen

from china_bean_importers import cmbc_debit_card


def build_cmbc_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    pdfgen.header_lines(
        page,
        [
            "中国民生银行个人账户对账单",
            "客户姓名:测试",
            "客户账号:6222020000005555",
            "起止日期:2024/01/05 - 2024/01/06",
        ],
    )
    # column_offsets = [22, 56, 97, 173, 300, 400, 448, 482, 533, 568, 696]
    y = 130
    pdfgen.insert_text(page, (24, y), "对方行名")  # content start marker
    y += 16

    def put_row(y, cells):
        xs = [24, 60, 100, 180, 305, 405, 450, 485, 535, 580, 700]
        for x, cell in zip(xs, cells):
            if cell != "":
                pdfgen.insert_text(page, (x, y), cell)

    # full 11-column row: 凭证类型 凭证号码 交易时间 摘要 金额 余额 现转 渠道 机构 对方 对方行名
    put_row(
        y,
        [
            "转账",
            "12345",
            "2024-01-05 10:00:00",
            "京东购物",
            "-25.00",
            "1000.00",
            "现",
            "手机银行",
            "北京分行",
            "张三/6222020000000001111",
            "工商银行",
        ],
    )
    y += 16
    # partial row: only columns starting from 交易时间 are present
    put_row(
        y,
        [
            "",
            "",
            "2024-01-06 11:00:00",
            "充值",
            "100.00",
            "1100.00",
            "现",
            "柜台",
            "",
            "",
            "",
        ],
    )
    y += 16
    pdfgen.insert_text(page, (24, y), "______________")  # content end marker
    doc.save(path)
    doc.close()
    return path


def test_cmbc_debit_card(tmp_path):
    path = build_cmbc_pdf(tmp_path / "cmbc.pdf")
    imp, entries = helpers.run_importer(
        cmbc_debit_card.Importer, helpers.make_config(), path
    )

    assert imp.date(path).isoformat().startswith("2024-01-05")
    helpers.assert_txns(
        [
            # payee carries a known card number: destination overridden to BoC
            (
                "2024-01-05",
                "张三",
                "京东购物",
                "Assets:Card:CMBC",
                "Assets:Card:BoC",
                "-25.00 CNY",
            ),
            (
                "2024-01-06",
                "",
                "充值",
                "Assets:Card:CMBC",
                "Income:Unknown",
                "100.00 CNY",
            ),
        ],
        entries,
    )
    assert entries[0].meta["payee_account"] == "6222020000000001111"
    assert entries[0].meta["time"] == "10:00:00"
