# HSBC HK CSV exports (credit card and debit card variants).

import helpers

from china_bean_importers import hsbc_hk

# Column order for both variants comes from the real HSBC HK exports.
CREDIT_CSV = """Transaction date,Post date,Transaction status,Billing currency,Billing amount,Description,Merchant name,Country / region,Area / district
05/01/2024,06/01/2024,POSTED,HKD,-50.00,UNIONPAY TEST,MERCHANT HK,HK,
06/01/2024,07/01/2024,PENDING,HKD,-20.00,APPLEPAY TEST,MERCHANT HK,,
"""

DEBIT_CSV = """Date,Value date,Billing currency,Billing amount,Balance,Description
05/01/2024,05/01/2024,HKD,-100.00,1000.00,PAYMENT TEST
06/01/2024,06/01/2024,HKD,500.00,1500.00,ATM DEPOSIT
"""


def test_credit_card(tmp_path):
    path = tmp_path / "PULSE_202401.csv"
    path.write_text(CREDIT_CSV, encoding="utf-8")
    imp, entries = helpers.run_importer(hsbc_hk.Importer, helpers.make_config(), path)

    # entries are sorted by transaction date
    helpers.assert_txns(
        [
            (
                "2024-01-05",
                "MERCHANT HK",
                "UNIONPAY TEST",
                "Liabilities:CreditCards:HSBC:Pulse",
                "Expenses:Unknown",
                "-50.00 HKD",
            ),
            (
                "2024-01-06",
                "MERCHANT HK",
                "APPLEPAY TEST",
                "Liabilities:CreditCards:HSBC:Pulse",
                "Expenses:Unknown",
                "-20.00 HKD",
            ),
        ],
        entries,
    )
    assert entries[0].meta["payment_method"] == "云闪付"
    assert entries[1].meta["payment_method"] == "Apple Pay"
    assert entries[0].meta["country"] == "HK"
    # unposted transaction is flagged
    assert "need-confirmation" in entries[1].tags


def test_debit_card(tmp_path):
    path = tmp_path / "One_202401.csv"
    path.write_text(DEBIT_CSV, encoding="utf-8")
    imp, entries = helpers.run_importer(hsbc_hk.Importer, helpers.make_config(), path)

    helpers.assert_txns(
        [
            (
                "2024-01-05",
                "",
                "PAYMENT TEST",
                "Assets:Bank:HSBC",
                "Expenses:Unknown",
                "-100.00 HKD",
            ),
            (
                "2024-01-06",
                "",
                "ATM DEPOSIT",
                "Assets:Bank:HSBC",
                "Income:Unknown",
                "500.00 HKD",
            ),
        ],
        entries,
    )
    assert entries[0].meta["balance_after"] is not None


def test_unknown_account_mapping(tmp_path, capsys):
    path = tmp_path / "UnknownBank_202401.csv"
    path.write_text(DEBIT_CSV, encoding="utf-8")
    imp = hsbc_hk.Importer(helpers.make_config())
    assert not imp.identify(str(path))
    assert "Account mapping not found" in capsys.readouterr().err
