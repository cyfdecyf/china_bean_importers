from __future__ import annotations

import re
import sys

from dateutil.parser import parse
from beancount.core import amount, data
from beancount.core.data import D

from china_bean_importers.common import *
from china_bean_importers.beangulp.importer import PdfTableImporter


def gen_txn(config, filepath, parts, lineno, flag, card_acc, currency_code):
    my_assert(len(parts) == 9, "Cannot parse line in PDF", lineno, parts)
    #    0       1        2        3       4       5         6        7      8
    # 交易日期, 交易时间, 交易账号, 交易名称, 交易金额, 账户余额, 对手姓名, 对手账号, 交易摘要
    date = parse(parts[0]).date()
    time_raw = parts[1]
    time = f"{time_raw[:2]}:{time_raw[2:4]}:{time_raw[4:6]}"
    # self_account = parts[2]
    narration = parts[3]
    amount_ = parts[4]
    balance = parts[5]
    payee = parts[6]
    payee_account = parts[7]

    units1 = amount.Amount(D(amount_), currency_code)
    is_expense = amount_.startswith('-')
    # check blacklist
    if in_blacklist(config, narration):
        print(
            f"Item in blacklist: {date} {narration} [{units1}]",
            file=sys.stderr,
            end=" -- ",
        )
        if is_expense:
            print("Expense skipped", file=sys.stderr)
            return None
        print("Income kept in record", file=sys.stderr)

    metadata = data.new_metadata(filepath, lineno)
    metadata["time"] = time
    metadata["balance"] = balance
    if payee_account != '':
        metadata["payee_account"] = payee_account

    tags = set()

    account2 = None
    if m := match_destination_and_metadata(config, narration, payee):
        (account2, new_meta, new_tags) = m
        metadata.update(new_meta)
        tags = tags.union(new_tags)
    if account2 is None:
        account2 = unknown_account(config, is_expense)

    # Handle transfer to credit/debit cards
    if payee_account:
        new_account = find_account_by_card_number(config, payee_account)
        if new_account is not None:
            account2 = new_account

    if "退款" in narration or "退款" in parts[8]:
        tags.add("refund")

    txn = data.Transaction(
        meta=metadata,
        date=date,
        flag=flag,
        payee=payee,
        narration=narration,
        tags=tags,
        links=data.EMPTY_SET,
        postings=[
            data.Posting(
                account=card_acc,
                units=units1,
                cost=None,
                price=None,
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
    return txn


class Importer(PdfTableImporter):
    def __init__(self, config) -> None:
        super().__init__(config)
        self.match_keywords = ["上海浦东发展银行个人客户交易流水专用回单"]
        self.file_account_name = "spdb_debit_card"
        self.header_first_cell = "交易日期\nDate"

    def search_header(self, pattern) -> re.Match | None:
        rexp = re.compile(pattern)
        return rexp.search(self.full_content[0:2000])

    def parse_metadata(self, filepath: str):
        match = self.search_header(r"起止日期:\s*([0-9]{8})-([0-9]{8})")
        assert match
        self.start = parse(match[1])
        self.end = parse(match[2])

        match = self.search_header(r"户名:\s*(\w+)")
        assert match
        self.real_name = match[1]

        match = self.search_header(r"账号:\s*([0-9]{16})")
        assert match
        card_number = match[1]
        self.card_acc = find_account_by_card_number(self.config, card_number[-4:])
        my_assert(self.card_acc, f"Unknown card number {card_number}", 0, 0)

        match = self.search_header(r"Currency:\s*([A-Z]{3})")
        assert match
        self.currency_code = match[1]

    def generate_tx(self, row: list[str], lineno: int, filepath: str):
        return gen_txn(
            self.config,
            filepath,
            row,
            lineno,
            self.FLAG,
            self.card_acc,
            self.currency_code,
        )
