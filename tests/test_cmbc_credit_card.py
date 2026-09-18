# CMBC credit card CSV export and CCB debit card XLS export.

import helpers

from china_bean_importers import cmbc_credit_card

CMBC_CSV = """卡号末四位,交易日,记账日,授权码,摘要,金额
0105,20240106,8888,000001,京东-京东购物,25.00
0107,20240108,8888,000002,外卖-饿了么,20.00
"""


def test_cmbc_credit_card_csv(tmp_path):
    path = tmp_path / "cmbc_credit.csv"
    path.write_text(CMBC_CSV, encoding="utf-8")
    imp, entries = helpers.run_importer(
        cmbc_credit_card.Importer, helpers.make_config(), path
    )

    # note the fixture columns are
    # 交易日(MMDD), 记账日(YYYYMMDD), 卡号末四位, 授权码, 摘要, 金额
    helpers.assert_txns(
        [
            (
                "2024-01-05",
                "京东购物",
                "京东",
                "Liabilities:Card:CMBC",
                "Expenses:JD",
                "-25.00 CNY",
            ),
            (
                "2024-01-07",
                "饿了么",
                "外卖",
                "Liabilities:Card:CMBC",
                "Expenses:Food:Delivery",
                "-20.00 CNY",
            ),
        ],
        entries,
    )
    assert entries[0].meta["post_date"].isoformat() == "2024-01-06"


def test_cmbc_credit_card_rejects_other_csv(tmp_path):
    path = tmp_path / "other.csv"
    path.write_text("不相关的csv\n", encoding="utf-8")
    imp = cmbc_credit_card.Importer(helpers.make_config())
    assert not imp.identify(str(path))
