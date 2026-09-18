# Email-based credit card statements (EML).

from email import policy
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import helpers

from china_bean_importers import boc_credit_card, ccb_credit_card, cmbc_credit_card, icbc_credit_card


def qp_html_eml(subject, html):
    msg = EmailMessage(policy=policy.default)
    msg["Subject"] = subject
    msg["From"] = "bank@example.com"
    msg["To"] = "me@example.com"
    msg.set_content(html, subtype="html", cte="quoted-printable")
    return msg


def b64_related_eml(subject, html, encoding):
    # mixed { related { html } } encapsulation, as produced by some banks
    related = MIMEMultipart("related")
    related.attach(MIMEText(html, "html", encoding))
    mixed = MIMEMultipart("mixed")
    mixed.attach(related)
    mixed["Subject"] = subject
    return mixed


def write(path, msg):
    path.write_text(msg.as_string(), encoding="utf-8")
    return path


BOC_HTML = """<html><head><title>中国银行电子帐单</title></head><body>
<table class="bill_sum_detail_table"><tr><td>账单日</td><td>2024-01-28</td></tr></table>
<div class="bill_card_detail">
<div class="bill_card_des">信用卡(卡号:7777)</div>
<div class="bill_card_des">人民币交易明细</div>
<table>
<tr><td>交易日</td><td>银行记账日</td><td>卡号末四位</td><td>交易描述</td><td>存入</td><td>支出</td></tr>
<tr><td>2024-01-05</td><td>2024-01-06</td><td>7777</td><td>京东-京东购物</td><td></td><td>25.00</td></tr>
<tr><td>2024-01-07</td><td>2024-01-08</td><td>7777</td><td>支付宝转账</td><td></td><td>30.00</td></tr>
<tr><td>2024-01-09</td><td>2024-01-10</td><td>7777</td><td>还款-自动还款</td><td>500.00</td><td></td></tr>
</table>
</div>
</body></html>"""


def test_boc_credit_card(tmp_path, capsys):
    path = write(tmp_path / "boc.eml", qp_html_eml("中国银行信用卡账单", BOC_HTML))
    imp, entries = helpers.run_importer(
        boc_credit_card.Importer, helpers.make_config(), path
    )

    assert imp.date(path).isoformat().startswith("2024-01-28")
    # 支付宝转账 hits the card narration blacklist and is skipped
    assert "blacklist" in capsys.readouterr().err
    helpers.assert_txns(
        [
            (
                "2024-01-05",
                "京东购物",
                "京东",
                "Liabilities:Card:BoC",
                "Expenses:JD",
                "-25.00 CNY",
            ),
            (
                "2024-01-09",
                "自动还款",
                "还款",
                "Liabilities:Card:BoC",
                "Income:Unknown",
                "500.00 CNY",
            ),
        ],
        entries,
    )
    assert entries[0].meta["post_date"] == "2024-01-06"


CCB_HTML = """<html><body>
<table><tr><td><font>本期账单日</font></td><td><font>备注</font><font>2024-01-10</font></td></tr></table>
<table>
<tr><td>【交易明细】</td></tr>
<tr><td>交易日</td><td><font>上期账单余额(Previous Balance)</font></td></tr>
<tr><td>2024-01-05</td><td>2024-01-06</td><td>0000</td><td>京东-京东购物</td><td>CNY</td><td>25.00</td><td>CNY</td><td>25.00</td></tr>
<tr><td>2024-01-07</td><td>2024-01-08</td><td>0000</td><td>境外消费-AMAZON</td><td>USD</td><td>3.50</td><td>CNY</td><td>25.00</td></tr>
</table>
</body></html>"""


def test_ccb_credit_card(tmp_path):
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText(CCB_HTML, "html", "utf-8"))
    msg["Subject"] = "中国建设银行信用卡账单"
    path = write(tmp_path / "ccb.eml", msg)
    imp, entries = helpers.run_importer(
        ccb_credit_card.Importer, helpers.make_config(), path
    )

    assert imp.date(path).isoformat().startswith("2024-01-10")
    helpers.assert_txns(
        [
            (
                "2024-01-05",
                "京东购物",
                "京东",
                "Liabilities:Card:CCB",
                "Expenses:JD",
                "-25.00 CNY",
            ),
            (
                "2024-01-07",
                "AMAZON",
                "境外消费",
                "Liabilities:Card:CCB",
                "Expenses:Unknown",
                "-25.00 CNY",
            ),
        ],
        entries,
    )
    # foreign currency transaction keeps the original amount in metadata
    assert entries[1].meta["trans"] == "3.50 USD"
    assert entries[1].meta["post_date"] == "2024-01-08"


CMBC_HTML = """<html><body>
<table><tr><td><span id="fixBand36">账单日</span></td><td><font>2024-01-10</font></td></tr></table>
<span id="fixBand29"><font>人民币 RMB</font></span>
<span id="fixBand29"><font>placeholder</font></span>
<span id="loopBand3"><table>
<tr><td><font>01/05</font></td><td><font>01/06</font></td><td><font>京东-京东购物</font></td><td><font>25.00</font></td><td><font>8888</font></td></tr>
<tr><td><font>01/07</font></td><td><font>01/08</font></td><td><font>美团支付订餐</font></td><td><font>20.00</font></td><td><font>8888</font></td></tr>
</table></span>
</body></html>"""


def test_cmbc_credit_card_eml(tmp_path, capsys):
    path = write(
        tmp_path / "cmbc.eml", b64_related_eml("民生信用卡账单", CMBC_HTML, "gbk")
    )
    imp, entries = helpers.run_importer(
        cmbc_credit_card.Importer, helpers.make_config(), path
    )

    assert imp.date(path).isoformat().startswith("2024-01-10")
    # 美团支付 is in the card narration blacklist and skipped unconditionally
    assert "blacklist" in capsys.readouterr().err
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
        ],
        entries,
    )
    assert entries[0].meta["post_date"].isoformat() == "2024-01-06"


ICBC_HTML = """<html><body>
<table><tr><td>对账单生成日：2024年01月10日</td></tr></table>
<table>
<tr><td>卡号后四位</td><td>交易日</td><td>交易类型</td><td>商户名称/城市</td><td>交易金额/币种</td><td>记账金额/币种</td></tr>
<tr><td>9999</td><td>2024-01-05</td><td>消费</td><td>京东</td><td>25.00/CNY</td><td>25.00/CNY(支出)</td></tr>
<tr><td>9999</td><td>2024-01-07</td><td>消费</td><td>AMAZON</td><td>3.50/USD</td><td>25.00/CNY(支出)</td></tr>
</table>
</body></html>"""


def test_icbc_credit_card(tmp_path, capsys):
    path = write(tmp_path / "icbc.eml", qp_html_eml("中国工商银行客户对账单", ICBC_HTML))
    imp, entries = helpers.run_importer(
        icbc_credit_card.Importer, helpers.make_config(), path
    )

    assert imp.date(path).isoformat().startswith("2024-01-10")
    # the "Discovered fields" message goes to stderr
    assert "Discovered fields" in capsys.readouterr().err
    helpers.assert_txns(
        [
            (
                "2024-01-05",
                "京东",
                "消费",
                "Liabilities:Card:ICBC",
                "Expenses:Unknown",
                "-25.00 CNY",
            ),
            (
                "2024-01-07",
                "AMAZON",
                "消费",
                "Liabilities:Card:ICBC",
                "Expenses:Unknown",
                "-25.00 CNY",
            ),
        ],
        entries,
    )
    assert entries[1].meta["original_amount"] == "3.50 USD"
