# CCB debit card XLS export (XlsImporter, needs pandas + xlrd, fixture
# generated with xlwt).

import pytest

import helpers

from china_bean_importers import ccb_debit_card

ROWS = [
    ["中国建设银行交易明细", "", "", "", "", "", "", "", ""],
    ["起始日期:20240101", "结束日期:20240201", "", "", "", "", "", ""],
    ["卡号/账号:6222020000000002222", "", "", "", "", "", "", ""],
    ["客户名称: 测试", "", "", "", "", "", "", ""],
    [
        "序号",
        "摘要",
        "币别",
        "钞汇",
        "交易日期",
        "交易金额",
        "账户余额",
        "交易地点/附言",
        "对方账号与户名",
    ],
    [
        "1",
        "京东购物",
        "人民币元",
        "",
        "2024-01-05",
        "-25.00",
        "1000.00",
        "网上支付",
        "6222020000000001111/测试",
    ],
    [
        "2",
        "工资",
        "人民币元",
        "",
        "2024-01-06",
        "500.00",
        "1500.00",
        "",
        "某公司",
    ],
]


@pytest.fixture
def xls_path(tmp_path):
    xlwt = pytest.importorskip("xlwt")
    wb = xlwt.Workbook()
    ws = wb.add_sheet("明细")
    for r, row in enumerate(ROWS):
        for c, v in enumerate(row):
            ws.write(r, c, v)
    path = tmp_path / "ccb.xls"
    wb.save(path)
    return path


def test_ccb_debit_card(xls_path):
    pytest.importorskip("xlrd")
    imp, entries = helpers.run_importer(
        ccb_debit_card.Importer, helpers.make_config(), xls_path
    )

    assert imp.date(xls_path).isoformat().startswith("2024-01-01")
    helpers.assert_txns(
        [
            (
                "2024-01-05",
                "6222020000000001111/测试",
                "京东购物 网上支付",
                "Assets:Card:CCB",
                "Assets:Card:BoC",
                "-25.00 CNY",
            ),
            (
                "2024-01-06",
                "某公司",
                "工资",
                "Assets:Card:CCB",
                "Income:Unknown",
                "500.00 CNY",
            ),
        ],
        entries,
    )
    # payee carries a known card number and the real name: the destination
    # account is overridden to the BoC card account
    assert entries[0].meta["balance"] == "1000.00 CNY"
