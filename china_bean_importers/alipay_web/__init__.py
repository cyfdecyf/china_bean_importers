from dateutil.parser import parse
from beangulp import Importer
from beancount.core import data
from beancount.core.data import D
import csv
import re

from china_bean_importers.common import *


class Importer(Importer):
    FLAG = FLAG

    def __init__(self, config) -> None:
        super().__init__()
        self.config = config

    def identify(self, filepath: str):
        return "txt" in filepath and "支付宝交易记录明细查询" in open(filepath, "r", encoding="gbk").read(1024)

    def account(self, filepath: str):
        return "alipay_web"

    def date(self, filepath: str):
        with open(filepath, "r", encoding="gbk") as f:
            for row in csv.reader(f):
                m = re.search(r"起始日期:\[([0-9 :-]+)\]", row[0])
                if m:
                    date = parse(m[1])
                    return date
        return super().date(filepath)

    def filename(self, filepath: str):
        with open(filepath, "r", encoding="gbk") as f:
            for row in csv.reader(f):
                m = re.search(r"终止日期:\[([0-9 :-]+)\]", row[0])
                if m:
                    date = parse(m[1])
                    return "to." + date.date().isoformat() + ".txt"
        return super().filename(filepath)

    def extract(self, filepath: str, existing=None):
        entries = []
        begin = False
        with open(filepath, "r", encoding="gbk") as f:
            for lineno, row in enumerate(csv.reader(f)):
                row = [col.strip() for col in row]
                if row[0] == "交易号" and row[1] == "商家订单号":
                    begin = True
                elif begin and row[0].startswith("------"):
                    break
                elif begin:
                    metadata = data.new_metadata(filepath, lineno)
                    date = parse(row[2]).date()
                    units = data.Amount(D(row[9]), "CNY")
                    payee = row[7]
                    narration = row[8]

                    account1 = self.config["importers"]["alipay"]["account"]
                    tags = set()
                    account2 = resolve_destination(
                        self.config, narration, payee, row[10] == "支出", metadata, tags
                    )

                    if row[10] == "支出":
                        units1 = -units
                    elif row[10] == "收入" or row[10] == "其他":
                        units1 = units
                    else:
                        assert False

                    txn = make_two_posting_txn(
                        filepath,
                        lineno,
                        date,
                        payee,
                        narration,
                        tags,
                        metadata,
                        account1,
                        account2,
                        units1,
                    )
                    entries.append(txn)
        return entries
