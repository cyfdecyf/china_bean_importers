# Unit tests for china_bean_importers.common.

import helpers
import pymupdf

from china_bean_importers.common import (
    BillDetailMapping,
    find_account_by_card_number,
    in_blacklist,
    make_two_posting_txn,
    match_card_tail,
    match_currency_code,
    match_destination_and_metadata,
    open_pdf,
    resolve_destination,
    should_skip_by_blacklist,
    unknown_account,
)


class TestBillDetailMapping:
    def test_narration_match(self):
        m = BillDetailMapping(["京东"], [], "Expenses:JD")
        account, metadata, tags, priority = m.match("京东购物", "别的")
        assert account == "Expenses:JD"
        assert metadata == {}
        assert tags == set()

    def test_or_logic(self):
        m = BillDetailMapping(["红包"], ["京东"], "Expenses:Gift")
        account, _, _, _ = m.match("微信红包", None)
        assert account == "Expenses:Gift"
        account, _, _, _ = m.match("不相关", "京东自营")
        assert account == "Expenses:Gift"
        account, _, _, _ = m.match("不相关", "别家")
        assert account is None

    def test_and_logic(self):
        m = BillDetailMapping(["红包"], ["京东"], "Expenses:Gift", match_logic="AND")
        account, _, _, _ = m.match("微信红包", "京东自营")
        assert account == "Expenses:Gift"
        account, _, _, _ = m.match("微信红包", "别家")
        assert account is None

    def test_same_as_narration(self):
        from china_bean_importers.common import SAME_AS_NARRATION

        m = BillDetailMapping(
            narration_keywords=["美团"],
            payee_keywords=SAME_AS_NARRATION,
            destination_account="Expenses:Meituan",
        )
        # payee is matched against the narration keywords
        account, _, _, _ = m.match("其他描述", "美团外卖")
        assert account == "Expenses:Meituan"
        account, _, _, _ = m.match("美团", "别的商家")
        assert account == "Expenses:Meituan"

    def test_same_as_narration_without_narration_keywords(self):
        from china_bean_importers.common import SAME_AS_NARRATION

        # payee_keywords=SAME_AS_NARRATION with no narration_keywords must not
        # crash even though there is nothing to iterate.
        m = BillDetailMapping(payee_keywords=SAME_AS_NARRATION)
        account, _, _, _ = m.match("描述", "商家")
        assert account is None

    def test_none_arguments(self):
        m = BillDetailMapping(["京东"], ["京东"], "Expenses:JD")
        account, _, _, _ = m.match(None, None)
        assert account is None

    def test_tags_and_metadata_canonicalize(self):
        m = BillDetailMapping(
            ["京东"], [], "Expenses:JD", ["gift"], {"platform": "京东"}
        )
        account, metadata, tags, priority = m.match("京东", None)
        assert account == "Expenses:JD"
        assert metadata == {"platform": "京东"}
        assert tags == {"gift"}
        assert priority == 0


class TestMatchCardTail:
    def test_match(self):
        assert match_card_tail("招商银行(3333)") == "3333"
        assert match_card_tail("零钱通转出-到工商银行(4444)") == "4444"

    def test_no_match(self):
        assert match_card_tail("零钱") is None
        assert match_card_tail("招商银行(333)") is None


class TestFindAccountByCardNumber:
    def test_tail(self):
        config = helpers.make_config()
        assert find_account_by_card_number(config, "3333") == "Assets:Card:CMB"
        assert find_account_by_card_number(config, 3333) == "Assets:Card:CMB"

    def test_full_number(self):
        config = helpers.make_config()
        assert (
            find_account_by_card_number(config, "6222020000000001111")
            == "Assets:Card:BoC"
        )

    def test_unknown(self):
        config = helpers.make_config()
        assert find_account_by_card_number(config, "9999") == "Liabilities:Card:ICBC"
        assert find_account_by_card_number(config, "1212") is None


class TestInBlacklist:
    def test_blacklist(self):
        config = helpers.make_config()
        assert in_blacklist(config, "支付宝转账") is True
        assert in_blacklist(config, "美团支付消费") is True

    def test_whitelist_wins(self):
        config = helpers.make_config()
        # whitelist keyword present, even together with a blacklist keyword
        assert in_blacklist(config, "财付通(银联云闪付)") is False

    def test_normal(self):
        config = helpers.make_config()
        assert in_blacklist(config, "京东购物") is False


class TestCurrencyAndAccounts:
    def test_currency_code(self):
        assert match_currency_code("人民币") == "CNY"
        assert match_currency_code("美元") == "USD"
        assert match_currency_code("比特币") is None

    def test_unknown_account(self):
        config = helpers.make_config()
        assert unknown_account(config, True) == "Expenses:Unknown"
        assert unknown_account(config, False) == "Income:Unknown"


class TestMatchDestinationAndMetadata:
    def test_no_match(self):
        config = helpers.make_config()
        account, metadata, tags = match_destination_and_metadata(
            config, "随便", "随便"
        )
        assert account is None
        assert metadata == {}
        assert tags == set()

    def test_narration_match(self):
        config = helpers.make_config()
        account, metadata, tags = match_destination_and_metadata(config, "京东购物", None)
        assert account == "Expenses:JD"
        assert metadata == {"platform": "京东"}

    def test_payee_match(self):
        config = helpers.make_config()
        account, _, _ = match_destination_and_metadata(config, "吃的", "饿了么")
        assert account == "Expenses:Food:Delivery"

    def test_priority_prefers_higher(self):
        config = helpers.make_config()
        from china_bean_importers.common import BillDetailMapping as BDM

        config["detail_mappings"] = [
            BDM(["京东"], [], "Expenses:General", priority=0),
            BDM(["京东"], [], "Expenses:Specific", priority=10),
        ]
        account, _, _ = match_destination_and_metadata(config, "京东", None)
        assert account == "Expenses:Specific"

    def test_deeper_account_wins_on_tie(self):
        config = helpers.make_config()
        from china_bean_importers.common import BillDetailMapping as BDM

        config["detail_mappings"] = [
            BDM(["京东"], [], "Expenses:JD"),
            BDM(["京东"], [], "Expenses:JD:Sub"),
        ]
        account, _, _ = match_destination_and_metadata(config, "京东", None)
        assert account == "Expenses:JD:Sub"


class TestResolveDestination:
    def test_fallback_to_unknown(self):
        config = helpers.make_config()
        metadata, tags = {}, set()
        account = resolve_destination(config, "未知", None, True, metadata, tags)
        assert account == "Expenses:Unknown"
        assert metadata == {}

    def test_mapping(self):
        config = helpers.make_config()
        metadata, tags = {}, set()
        account = resolve_destination(config, "京东购物", None, True, metadata, tags)
        assert account == "Expenses:JD"
        assert metadata == {"platform": "京东"}

    def test_special_case_wins(self):
        config = helpers.make_config()
        metadata, tags = {}, set()
        account = resolve_destination(
            config, "京东购物", None, False, metadata, tags, "Income:Special"
        )
        assert account == "Income:Special"
        # metadata/tags from mappings are still merged
        assert metadata == {"platform": "京东"}


class TestMakeTwoPostingTxn:
    def test_basic(self):
        import datetime

        from beancount.core import data
        from beancount.core.data import D

        metadata = data.new_metadata("file", 1)
        tags = {"refund"}
        txn = make_two_posting_txn(
            "file",
            1,
            datetime.date(2024, 1, 5),
            "商家",
            "京东",
            tags,
            metadata,
            "Assets:A",
            "Expenses:B",
            data.Amount(D("-25.00"), "CNY"),
        )
        assert txn.payee == "商家"
        assert txn.narration == "京东"
        assert txn.tags == {"refund"}
        assert txn.flag == "*"
        assert [p.account for p in txn.postings] == ["Assets:A", "Expenses:B"]
        assert str(txn.postings[0].units) == "-25.00 CNY"
        assert txn.postings[1].units is None


class TestShouldSkipByBlacklist:
    def test_normal_not_skipped(self, capsys):
        config = helpers.make_config()
        from beancount.core import data
        from beancount.core.data import D

        units = data.Amount(D("-25.00"), "CNY")
        assert not should_skip_by_blacklist(config, "京东购物", "2024-01-05", units)
        assert capsys.readouterr().err == ""

    def test_blacklisted_expense_skipped(self, capsys):
        config = helpers.make_config()
        from beancount.core import data
        from beancount.core.data import D

        units = data.Amount(D("-25.00"), "CNY")
        assert should_skip_by_blacklist(config, "支付宝转账", "2024-01-05", units)
        err = capsys.readouterr().err
        assert "Item in blacklist" in err and "Expense skipped" in err

    def test_blacklisted_income_kept(self, capsys):
        config = helpers.make_config()
        from beancount.core import data
        from beancount.core.data import D

        units = data.Amount(D("25.00"), "CNY")
        assert not should_skip_by_blacklist(config, "支付宝退款", "2024-01-05", units)
        assert "Income kept" in capsys.readouterr().err

    def test_blacklisted_refund_skipped_when_flagged(self, capsys):
        config = helpers.make_config()
        from beancount.core import data
        from beancount.core.data import D

        units = data.Amount(D("25.00"), "CNY")
        assert should_skip_by_blacklist(
            config, "支付宝退款", "2024-01-05", units, refund=True
        )
        assert "Refund skipped" in capsys.readouterr().err


class TestOpenPdf:
    def test_plain(self, tmp_path):
        path = tmp_path / "plain.pdf"
        doc = pymupdf.open()
        doc.new_page()
        doc.save(path)
        assert open_pdf(helpers.make_config(), str(path)) is not None

    def test_password_ok(self, tmp_path):
        path = tmp_path / "encrypted.pdf"
        doc = pymupdf.open()
        doc.new_page()
        doc.save(
            path,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            user_pw="123456",
            owner_pw="123456",
        )
        config = helpers.make_config(pdf_passwords=["wrong", "123456"])
        assert open_pdf(config, str(path)) is not None

    def test_password_wrong(self, tmp_path):
        path = tmp_path / "encrypted.pdf"
        doc = pymupdf.open()
        doc.new_page()
        doc.save(
            path,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            user_pw="123456",
            owner_pw="123456",
        )
        config = helpers.make_config(pdf_passwords=["wrong"])
        assert open_pdf(config, str(path)) is None
