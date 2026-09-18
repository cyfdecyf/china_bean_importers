import csv
from decimal import Decimal

from dateutil.parser import parse
from beancount.core import data
from beancount.core.data import D

from china_bean_importers.common import *
from china_bean_importers.importer import CsvImporter


class Importer(CsvImporter):
    def __init__(self, config) -> None:
        super().__init__(config)
        self.match_keywords = ["mername"]
        self.file_account_name = "thu_ecard"
        self.all_ids = set()

    def parse_metadata(self, filepath: str):
        if len(self.content) > 2:
            if m := common_date_pattern.search(self.content[1]):
                self.end = parse(m[1])
            if m := common_date_pattern.search(self.content[-1]):
                self.start = parse(m[1])

    def extract(self, filepath: str, existing=None):
        entries = []

        def to_yuan(fen) -> Decimal:
            return (Decimal(fen) / 100).quantize(Decimal(".01"))

        for lineno, row in enumerate(csv.reader(self.content)):
            row = [col.strip() for col in row]

            #    0         1         2        3          4          5       6       7
            # summary, posjourno, idserial, txaccno, inputuserid, pcode, poscode, accno
            #    8         9    10      11        12           13      14     15,      16
            # txcode, cardno, txdate, txname, stationcode, identityno, sts, balance, journo
            #   17        18     19    20     21        22       23
            # regdate, departid, id, txamt, meraddr, username, mername

            # skip table header and footer
            if lineno == 0:
                continue
            elif lineno == len(self.content) - 1:
                break

            # detect duplicate items by pos_journo
            pos_journo = row[1].strip()
            if pos_journo != "":
                if pos_journo in self.all_ids:
                    my_warn(f"Duplicate pos_journo detected: {pos_journo}", lineno, row)
                    continue
                self.all_ids.add(pos_journo)

            # parse data line
            metadata: dict = data.new_metadata(filepath, lineno)
            tags = set()

            # parse some basic info
            summary = row[0]
            time = parse(row[10])
            units = data.Amount(D(to_yuan(row[20])), "CNY")
            balance = data.Amount(D(to_yuan(row[15])), "CNY")
            payee = row[23]
            addr = row[21]
            tx_type = row[11]
            if summary != tx_type:
                summary = f"{summary}_{tx_type}"

            metadata["balance"] = str(balance)
            metadata["location"] = addr
            metadata["time"] = time.time().isoformat()
            metadata["payment_method"] = "清华大学校园卡"

            expense = None

            if any(k in summary for k in ("消费", "补卡")):
                expense = True
            elif any(k in summary for k in ("充值", "代发", "圈存")):
                expense = False

            my_assert(expense is not None, f"Unknown transaction type", lineno, row)

            if expense:
                units = -units

            source_config = self.config["importers"]["thu_ecard"]
            account1 = source_config["account"]
            account2 = resolve_destination(
                self.config, summary, payee, expense, metadata, tags
            )

            # create transaction
            entries.append(
                make_two_posting_txn(
                    filepath,
                    lineno,
                    time.date(),
                    payee,
                    summary,
                    tags,
                    metadata,
                    account1,
                    account2,
                    units,
                )
            )

        return entries
