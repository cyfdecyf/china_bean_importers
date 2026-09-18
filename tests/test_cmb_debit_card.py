# PDF bank statements: coordinate-based (PdfImporter) and table-based
# (PdfTableImporter). PDFs are synthesized with pymupdf.

import pymupdf

import helpers
import pdfgen

from china_bean_importers import cmb_debit_card


def build_cmb_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    pdfgen.header_lines(
        page,
        [
            "招商银行交易流水",
            "客户名：测试",
            "6225880000003333",
        ],
    )
    # column_offsets = [30, 50, 100, 200, 280, 350, 400]
    # words: x=32 date | x=55 currency | x=105 amount | x=205 balance
    #        x=285 summary | x=355 party | x=410 customer summary
    y = 120
    pdfgen.insert_text(page, (32, y), "Party")  # content start marker
    y += 16

    def put_row(y, date, amount, balance, summary, party, customer=None):
        pdfgen.insert_text(page, (32, y), date)
        pdfgen.insert_text(page, (55, y), "RMB")
        pdfgen.insert_text(page, (105, y), amount)
        pdfgen.insert_text(page, (205, y), balance)
        pdfgen.insert_text(page, (285, y), summary)
        pdfgen.insert_text(page, (355, y), party)
        if customer is not None:
            pdfgen.insert_text(page, (410, y), customer)

    put_row(y, "2024-01-05", "-25.00", "1000.00", "消费", "京东", "京东购物")
    y += 16
    put_row(y, "2024-01-06", "500.00", "1500.00", "还款", "测试6222020000000001111")
    y += 16
    pdfgen.insert_text(page, (32, y), "————")  # content end marker
    doc.save(path)
    doc.close()
    return path


def test_cmb_debit_card(tmp_path):
    path = build_cmb_pdf(tmp_path / "cmb.pdf")
    imp, entries = helpers.run_importer(
        cmb_debit_card.Importer, helpers.make_config(), path
    )

    assert imp.date(path) is None  # CMB statement has no date range in text
    helpers.assert_txns(
        [
            # 7-column row: narration comes from the customer summary column
            (
                "2024-01-05",
                "京东",
                "京东购物",
                "Assets:Card:CMB",
                "Expenses:JD",
                "-25.00 CNY",
            ),
            # 6-column row: narration from the summary column; party carries a
            # card number that maps to a known account
            (
                "2024-01-06",
                "测试",
                "还款",
                "Assets:Card:CMB",
                "Assets:Card:BoC",
                "500.00 CNY",
            ),
        ],
        entries,
    )
    assert entries[1].meta["payee_account"] == "6222020000000001111"
    assert entries[1].meta["balance"] == "1500.00 CNY"
