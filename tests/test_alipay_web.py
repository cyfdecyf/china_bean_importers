# alipay web portal txt export (GBK encoded).

import helpers

from china_bean_importers import alipay_web

ALIPAY_WEB_TXT = """支付宝交易记录明细查询
账号:[test@example.com]
起始日期:[2024-01-01 00:00:00]    终止日期:[2024-02-01 00:00:00]
---------------------------------交易记录明细列表------------------------------------
交易号,商家订单号,交易创建时间,付款时间,最近修改时间,交易来源地,类型,交易对方,商品名称,金额（元）,收/支,交易状态
202401050001,200001,2024-01-05 10:00:00,2024-01-05 10:00:00,2024-01-05 10:00:00,地都,即时到账交易,京东,京东购物,25.00,支出,交易成功
202401100002,200002,2024-01-10 11:00:00,2024-01-10 11:00:00,2024-01-10 11:00:00,地都,收款,张三,转账,100.00,收入,交易成功
---------------------------------结束------------------------------------
"""


def test_alipay_web(tmp_path):
    path = tmp_path / "alipay_web.txt"
    path.write_text(ALIPAY_WEB_TXT, encoding="gbk")
    imp, entries = helpers.run_importer(
        alipay_web.Importer, helpers.make_config(), path
    )

    assert imp.date(path).isoformat().startswith("2024-01-01")
    assert imp.filename(path) == "to.2024-02-01.txt"
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
                "2024-01-10",
                "张三",
                "转账",
                "Assets:Alipay",
                "Income:Unknown",
                "100.00 CNY",
            ),
        ],
        entries,
    )
    assert entries[0].meta["platform"] == "京东"
