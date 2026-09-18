# THU ecard exports: new format (browser-captured CSV) and old format.

import helpers

from china_bean_importers import thu_ecard

# 24 columns of the browser-captured export; see decode.js. Amounts are in fen.
# rows are newest-first: content[1] holds the newest date, the footer the oldest.
HEADER = ",".join(
    [
        "summary",
        "posjourno",
        "idserial",
        "txaccno",
        "inputuserid",
        "pcode",
        "poscode",
        "accno",
        "txcode",
        "cardno",
        "txdate",
        "txname",
        "stationcode",
        "identityno",
        "sts",
        "balance",
        "journo",
        "regdate",
        "departid",
        "id",
        "txamt",
        "meraddr",
        "username",
        "mername",
    ]
)


def row(summary, posjourno, txdate, txname, balance, txamt, mername):
    cells = [""] * 24
    cells[0] = summary
    cells[1] = posjourno
    cells[10] = txdate
    cells[11] = txname
    cells[15] = str(balance)
    cells[20] = str(txamt)
    cells[21] = "清华园"
    cells[23] = mername
    return ",".join(cells)


THU_CSV = "\n".join(
    [
        HEADER,
        row("消费", "P1", "2024-01-06 08:00:00", "消费", 100000, 2500, "桃李园"),
        row("充值", "P2", "2024-01-05 12:00:00", "充值", 102500, 10000, "圈存机"),
        # duplicate posjourno is skipped
        row("消费", "P1", "2024-01-06 12:00:00", "消费", 95000, 3000, "清青快餐"),
        "导出时间,2024-01-05 00:00:00",
    ]
)


def test_thu_ecard(tmp_path, capsys):
    path = tmp_path / "thu_ecard.csv"
    path.write_text(THU_CSV, encoding="utf-8")
    imp, entries = helpers.run_importer(
        thu_ecard.Importer, helpers.make_config(), path
    )

    # duplicate posjourno P1 is dropped with a warning
    assert "Duplicate pos_journo" in capsys.readouterr().err
    assert imp.date(path).isoformat().startswith("2024-01-05")
    helpers.assert_txns(
        [
            (
                "2024-01-06",
                "桃李园",
                "消费",
                "Assets:Card:THU",
                "Expenses:Unknown",
                "-25.00 CNY",
            ),
            (
                "2024-01-05",
                "圈存机",
                "充值",
                "Assets:Card:THU",
                "Income:Unknown",
                "100.00 CNY",
            ),
        ],
        entries,
    )
    assert entries[0].meta["payment_method"] == "清华大学校园卡"
    assert entries[0].meta["location"] == "清华园"
    assert entries[0].meta["balance"] == "1000.00 CNY"
