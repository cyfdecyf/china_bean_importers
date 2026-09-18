# THU ecard old-format export (6 columns).

import helpers

from china_bean_importers import thu_ecard_old

THU_OLD_CSV = """序号,交易地点,交易类型,终端编号,交易时间,交易金额
1,桃李园,消费,T001,2024-01-06 08:00:00,25.00
2,圈存机,支付宝充值,T002,2024-01-05 12:00:00,100.00
汇总,共2笔,,,,2024-01-06
"""


def test_thu_ecard_old(tmp_path):
    path = tmp_path / "thu_ecard_old.csv"
    path.write_text(THU_OLD_CSV, encoding="utf-8")
    imp, entries = helpers.run_importer(
        thu_ecard_old.Importer, helpers.make_config(), path
    )

    assert imp.date(path).isoformat().startswith("2024-01-06")
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
                "支付宝充值",
                "Assets:Card:THU",
                "Income:Unknown",
                "100.00 CNY",
            ),
        ],
        entries,
    )
    assert entries[0].meta["terminal"] == "T001"
