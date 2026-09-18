import re
import sys
from typing import NamedTuple

from beancount.core import data

card_tail_pattern = re.compile(r".*银行.*\(([0-9]{4})\)")
common_date_pattern = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2})")

# Flag used for all imported transactions.
FLAG = "*"

# a map from currency name(chinese) to currency code(ISO 4217)
currency_code_map = {
    "人民币": "CNY",
    "港币": "HKD",
    "澳门元": "MOP",
    "美元": "USD",
    "日元": "JPY",
    "韩元": "KRW",
    "欧元": "EUR",
    "英镑": "GBP",
    "加拿大元": "CAD",
    "澳大利亚元": "AUD",
}

SAME_AS_NARRATION = object()


class BillDetailMapping(NamedTuple):
    # used to match an item's narration
    narration_keywords: list[str] | None = None
    # used to match an item's payee
    payee_keywords: list[str] | None = None
    # destination account (None means not specified)
    destination_account: str | None = None
    # tags to append in bill item
    additional_tags: list[str] | None = None
    # other metadata to append in bill
    additional_metadata: dict[str, object] | None = None
    # priority (larger means higher priority, 0 means lowest)
    priority: int = 0
    # match logic ("OR" or "AND")
    match_logic: str = "OR"

    def canonicalize(self):
        tags = set(self.additional_tags) if self.additional_tags else set()
        metadata = self.additional_metadata.copy() if self.additional_metadata else {}
        return self.destination_account, metadata, tags, self.priority

    def match(
        self, desc: str, payee: str
    ) -> tuple[str | None, dict[str, object], set[str], int]:
        assert self.match_logic in ("OR", "AND")

        # match narration first
        narration_match = False
        if desc is not None and self.narration_keywords is not None:
            for keyword in self.narration_keywords:
                if keyword in desc:
                    narration_match = True
                    break

        # then try payee
        payee_match = False
        if payee is not None and self.payee_keywords is not None:
            keywords = (
                self.narration_keywords
                if self.payee_keywords is SAME_AS_NARRATION
                else self.payee_keywords
            )
            # keywords is None when payee_keywords is SAME_AS_NARRATION but no
            # narration keywords are configured: nothing to match against
            if keywords is not None:
                for keyword in keywords:
                    if keyword in payee:
                        payee_match = True
                        break

        if self.match_logic == "OR" and (narration_match or payee_match):
            return self.canonicalize()
        elif self.match_logic == "AND" and narration_match and payee_match:
            return self.canonicalize()
        return None, {}, set(), 0


def match_card_tail(src):
    assert isinstance(src, str)
    m = card_tail_pattern.match(src)
    return m[1] if m else None


def read_eml_html(
    filepath: str,
    *,
    encoding: str = "utf-8",
    b64: bool = False,
    unwrap_nested: bool = False,
) -> tuple[str, str]:
    """Parse an HTML email statement; returns (subject, html).

    b64 selects base64 transfer encoding instead of quoted-printable;
    unwrap_nested expects the HTML part wrapped in a container multipart
    (as produced by some banks); encoding is the charset of the body.
    """
    import base64
    import email
    import quopri
    from email import policy
    from html import unescape

    with open(filepath, encoding="utf-8") as f:
        raw_email = email.message_from_file(f, policy=policy.default)
    payload = raw_email.get_body().get_payload()
    if unwrap_nested:
        payload = payload[0].get_body().get_payload()
    if b64:
        html = base64.b64decode(payload).decode(encoding)
    else:
        html = quopri.decodestring(payload).decode(encoding)
    return raw_email["Subject"], unescape(html).replace("\xa0", " ")


def open_pdf(config, name):
    import fitz

    doc = fitz.open(name)
    if doc.is_encrypted:
        for password in config.get("pdf_passwords", []):
            doc.authenticate(password)
        if doc.is_encrypted:
            return None
    return doc


def find_account_by_card_number(config, card_number):
    if isinstance(card_number, int):
        card_number = str(card_number)
    for prefix, accounts in config["card_accounts"].items():
        for bank, numbers in accounts.items():
            # Match either the configured tail number itself, or a complete
            # card number ending with it, at the bank level.
            for num in numbers:
                if card_number.endswith(num):
                    return f"{prefix}:{bank}"

    return None


def match_destination_and_metadata(config, desc, payee):
    account = None
    mapping = None
    priority = 0
    metadata = {}
    tags = set()

    # merge all possible results
    for m in config["detail_mappings"]:
        _mapping: BillDetailMapping = m
        new_account, new_metadata, new_tags, new_priority = _mapping.match(desc, payee)
        # check compatibility
        if account is None or new_priority > priority:
            account, mapping, priority = new_account, m, new_priority
        elif new_account is not None and new_priority == priority:
            if new_account.startswith(account):
                # new account is deeper than or equal to current account
                account, mapping = new_account, m
            elif not account.startswith(new_account):
                my_warn(
                    f"""Conflict destination accounts found for narration {desc} and payee {payee}:
Old account {account} from {mapping}
New account {new_account} from {m}

""",
                    0,
                    "",
                )

        metadata.update(new_metadata)
        tags.update(new_tags)

    return account, metadata, tags


def match_currency_code(currency_name):
    return (
        currency_code_map[currency_name] if currency_name in currency_code_map else None
    )


def resolve_destination(
    config, narration, payee, expense, metadata, tags, account=None
) -> str:
    """Resolve the destination account for one bill item.

    Matches detail_mappings (merging their metadata/tags into the passed
    metadata dict and tags set), then falls back to `account` if given (an
    importer-specific special case), then to the configured unknown account.
    """
    new_account, new_meta, new_tags = match_destination_and_metadata(
        config, narration, payee
    )
    metadata.update(new_meta)
    tags.update(new_tags)
    if account is None:
        account = new_account
    if account is None:
        account = unknown_account(config, expense)
    return account


def make_two_posting_txn(
    filepath,
    lineno,
    date,
    payee,
    narration,
    tags,
    metadata,
    account1,
    account2,
    units,
    price=None,
    flag=FLAG,
) -> data.Transaction:
    """Build a simple transaction: one posting with units and one without."""
    return data.Transaction(
        meta=metadata,
        date=date,
        flag=flag,
        payee=payee,
        narration=narration,
        tags=tags,
        links=data.EMPTY_SET,
        postings=[
            data.Posting(
                account=account1,
                units=units,
                cost=None,
                price=price,
                flag=None,
                meta=None,
            ),
            data.Posting(
                account=account2,
                units=None,
                cost=None,
                price=None,
                flag=None,
                meta=None,
            ),
        ],
    )


def should_skip_by_blacklist(config, narration, date, units, refund=False) -> bool:
    """Shared blacklist handling for bank statement importers.

    Blacklisted expenses are always skipped; blacklisted refunds are skipped
    when `refund` is true; blacklisted income is kept (it would otherwise be
    missing from the ledger, unlike an expense which is duplicated by the
    wechat/alipay importers).
    """
    if not in_blacklist(config, narration):
        return False
    print(
        f"Item in blacklist: {date} {narration} [{units}]",
        file=sys.stderr,
        end=" -- ",
    )
    if units.number < 0:
        print("Expense skipped", file=sys.stderr)
        return True
    if refund:
        print("Refund skipped", file=sys.stderr)
        return True
    print("Income kept in record", file=sys.stderr)
    return False


def unknown_account(config, expense) -> str:
    return (
        config["unknown_expense_account"]
        if expense
        else config["unknown_income_account"]
    )


def in_blacklist(config, narration):
    for b in config["importers"]["card_narration_whitelist"]:
        if b in narration:
            return False
    for b in config["importers"]["card_narration_blacklist"]:
        if b in narration:
            return True
    return False


def my_assert(cond, msg, lineno, row):
    assert cond, f"{msg} on line {lineno}:\n{row}"


def my_warn(msg, lineno, row):
    print(f"WARNING: {msg} on line {lineno}:\n{row}\n", file=sys.stderr)
