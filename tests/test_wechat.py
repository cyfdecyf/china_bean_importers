# wechat bill CSV export.

import helpers

from china_bean_importers import wechat

WECHAT_CSV = """微信支付账单明细,,,,,,,,,,,
微信昵称：[测试],,,,,,,,,,,
起始时间：[2024-01-01 00:00:00],终止时间：[2024-02-01 00:00:00],,,,,,,,,,
导出类型：[全部],导出时间：[2024-03-01 00:00:00],,,,,,,,,,
共6笔记录,,,,,,,,,,,
----------------------微信支付账单明细列表--------------------,,,,,,,,,,,
交易时间,交易类型,交易对方,商品,收/支,金额(元),支付方式,当前状态,交易单号,商户单号,备注
2024-01-05 10:00:00,商户消费,京东,京东购物,支出,¥25.00,零钱,支付成功,10001,20001,/
2024-01-06 11:00:00,商户消费,京东,京东购物,支出,¥30.00,招商银行(3333),支付成功,10002,20002,/
2024-01-07 12:00:00,微信红包,发给张三,,支出,¥8.88,零钱,已存入零钱,10003,0,/
2024-01-08 13:00:00,微信红包,李四,,收入,¥6.66,零钱,已存入零钱,10004,0,/
2024-01-09 14:00:00,转账,王五,转账,收入,¥100.00,零钱,已收钱,10005,0,/
2024-01-10 15:00:00,商户消费,美团外卖,美团订餐,支出,¥20.00,零钱,退款成功,10006,20003,/
"""


def test_wechat(tmp_path):
    path = tmp_path / "wechat.csv"
    path.write_text(WECHAT_CSV, encoding="utf-8")
    imp, entries = helpers.run_importer(wechat.Importer, helpers.make_config(), path)

    assert imp.date(path).isoformat().startswith("2024-01-01")
    helpers.assert_txns(
        [
            (
                "2024-01-05",
                "京东",
                "京东购物",
                "Assets:WeChat",
                "Expenses:JD",
                "-25.00 CNY",
            ),
            (
                "2024-01-06",
                "京东",
                "京东购物",
                "Assets:Card:CMB",
                "Expenses:JD",
                "-30.00 CNY",
            ),
            (
                "2024-01-07",
                "张三",
                "发微信红包",
                "Assets:WeChat",
                "Expenses:WeChat:RedPacket",
                "-8.88 CNY",
            ),
            (
                "2024-01-08",
                "李四",
                "收微信红包",
                "Assets:WeChat",
                "Income:WeChat:RedPacket",
                "6.66 CNY",
            ),
            (
                "2024-01-09",
                "王五",
                "转账",
                "Assets:WeChat",
                "Income:WeChat:Transfer",
                "100.00 CNY",
            ),
            (
                "2024-01-10",
                "美团外卖",
                "美团订餐",
                "Assets:WeChat",
                "Expenses:Unknown",
                "-20.00 CNY",
            ),
        ],
        entries,
    )

    # metadata filled from the bill
    assert entries[0].meta["payment_method"] == "微信支付"
    assert entries[0].meta["platform"] == "京东"  # from detail mapping
    assert entries[0].meta["time"] == "10:00:00"
    assert entries[0].meta["serial"] == "10001"

    # the last row was refunded
    assert "refund" in entries[5].tags


def test_wechat_rejects_other_files(tmp_path):
    path = tmp_path / "unrelated.csv"
    path.write_text("一些其他内容\n", encoding="utf-8")
    imp = wechat.Importer(helpers.make_config())
    assert not imp.identify(str(path))
