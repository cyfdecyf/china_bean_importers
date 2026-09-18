# alipay mobile app CSV export (GBK encoded).

import helpers

from china_bean_importers import alipay_mobile

ALIPAY_CSV = """支付宝电子客户回单,,,,,,,,,,,,
起始时间：[2024-01-01 00:00:00],终止时间：[2024-02-01 00:00:00],,,,,,,,,,,
------------------------支付宝(中国)网络技术有限公司  电子客户回单--------------------------
交易时间,交易分类,交易对方,对方账号,商品说明,收/支,金额,收/付款方式,交易状态,交易订单号,商家订单号,备注,
2024-01-05 10:00:00,日用百货,京东,,京东购物,支出,25.00,余额,交易成功,10001,20001,/,
2024-01-06 11:00:00,日用百货,京东,,京东购物,支出,30.00,招商银行(3333),交易成功,10002,20002,/,
2024-01-07 12:00:00,转账红包,张三,,转账,收入,88.88,余额,交易成功,10003,0,/,
2024-01-08 13:00:00,投资理财,余额宝,,余额宝-收益发放,不计收支,1.23,余额宝,交易成功,10004,0,/,
2024-01-09 14:00:00,服饰装扮,淘宝店铺,,衣服退款,不计收支,59.90,余额,退款成功,10005,0,/,
2024-01-10 15:00:00,日用百货,美团,美团外卖,交易关闭,支出,20.00,余额,交易关闭,10006,0,/,
------------------------交易记录结束------------------------
"""


def test_alipay_mobile(tmp_path):
    path = tmp_path / "alipay_record.csv"
    path.write_text(ALIPAY_CSV, encoding="gbk")
    imp, entries = helpers.run_importer(
        alipay_mobile.Importer, helpers.make_config(), path
    )

    assert imp.date(path).isoformat().startswith("2024-01-01")
    # the closed transaction (交易关闭) is skipped
    helpers.assert_txns(
        [
            (
                "2024-01-05",
                "京东",
                "京东购物",
                "Assets:Alipay",
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
                "转账",
                "Assets:Alipay",
                "Income:Alipay:RedPacket",
                "88.88 CNY",
            ),
            (
                "2024-01-08",
                "余额宝",
                "余额宝-收益发放",
                "Assets:Alipay:YuEBao",
                "Income:Unknown",
                "1.23 CNY",
            ),
            (
                "2024-01-09",
                "淘宝店铺",
                "衣服退款",
                "Assets:Alipay",
                "Income:Unknown",
                "59.90 CNY",
            ),
        ],
        entries,
    )

    assert entries[0].meta["payment_method"] == "支付宝"
    assert entries[0].meta["platform"] == "京东"
    assert "refund" in entries[4].tags
