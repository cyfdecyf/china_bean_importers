# Shared test configuration and assertion helpers.

from china_bean_importers.common import BillDetailMapping as BDM

# Card number tails used by fixtures. Debit cards live under Assets:Card,
# credit cards under Liabilities:Card. Fixture card numbers always end with
# these tails.
CARD_ACCOUNTS = {
    "Assets:Card": {
        "BoC": ["1111"],
        "CCB": ["2222"],
        "CMB": ["3333"],
        "ICBC": ["4444"],
        "CMBC": ["5555"],
        "SPDB": ["6666"],
    },
    "Liabilities:Card": {
        "BoC": ["7777"],
        "CMBC": ["8888"],
        "ICBC": ["9999"],
        "CCB": ["0000"],
    },
}


def make_config(**overrides):
    config = {
        "importers": {
            "alipay": {
                "account": "Assets:Alipay",
                "huabei_account": "Liabilities:Alipay:HuaBei",
                "douyin_monthly_payment_account": "Liabilities:DouyinMonthlyPayment",
                "yuebao_account": "Assets:Alipay:YuEBao",
                "red_packet_income_account": "Income:Alipay:RedPacket",
                "red_packet_expense_account": "Expenses:Alipay:RedPacket",
                "xiaohebao_account": "Assets:Alipay:XiaoHeBao",
                "category_mapping": {
                    "交通出行": "Expenses:Travel",
                },
            },
            "wechat": {
                "account": "Assets:WeChat",
                "lingqiantong_account": "Assets:WeChat:LingQianTong",
                "red_packet_income_account": "Income:WeChat:RedPacket",
                "red_packet_expense_account": "Expenses:WeChat:RedPacket",
                "family_card_expense_account": "Expenses:WeChat:FamilyCard",
                "group_payment_expense_account": "Expenses:WeChat:Group",
                "group_payment_income_account": "Income:WeChat:Group",
                "transfer_expense_account": "Expenses:WeChat:Transfer",
                "transfer_income_account": "Income:WeChat:Transfer",
            },
            "thu_ecard": {
                "account": "Assets:Card:THU",
            },
            "hsbc_hk": {
                "account_mapping": {
                    "One": "Assets:Bank:HSBC",
                    "PULSE": "Liabilities:CreditCards:HSBC:Pulse",
                },
            },
            "boc": {
                "credit": {
                    "extract_repayment_rate": False,
                    "repayment_tag": None,
                },
            },
            "card_narration_whitelist": ["财付通(银联云闪付)"],
            "card_narration_blacklist": ["支付宝", "美团支付"],
        },
        "card_accounts": CARD_ACCOUNTS,
        "pdf_passwords": [],
        "unknown_expense_account": "Expenses:Unknown",
        "unknown_income_account": "Income:Unknown",
        "detail_mappings": [
            BDM(["京东"], [], "Expenses:JD", [], {"platform": "京东"}),
            BDM([], ["饿了么"], "Expenses:Food:Delivery", [], {}),
        ],
    }
    config.update(overrides)
    return config


def run_importer(importer_cls, config, path):
    """identify + extract, asserting identification succeeds."""
    imp = importer_cls(config)
    assert imp.identify(str(path)), f"{importer_cls} failed to identify {path}"
    return imp, imp.extract(str(path))


def assert_txns(expected, entries):
    """Compare a list of (date, payee, narration, account1, account2, units)
    tuples against extracted transactions, in order."""
    assert len(entries) == len(expected), (
        f"expected {len(expected)} entries, got {len(entries)}: "
        + "; ".join(str(e.narration) for e in entries)
    )
    for exp, e in zip(expected, entries):
        date, payee, narration, account1, account2, units = exp
        assert e.date.isoformat() == date
        assert e.payee == payee
        assert e.narration == narration
        assert [p.account for p in e.postings] == [account1, account2]
        assert str(e.postings[0].units) == units
