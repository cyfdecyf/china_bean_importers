from dateutil.parser import parse
from beangulp import Importer
from beancount.core import data
from beancount.core.data import D

from china_bean_importers.common import *


class Importer(Importer):
    FLAG = FLAG

    def __init__(self, config) -> None:
        super().__init__()
        self.config = config
        self.match_keywords = ["中国建设银行", "信用卡对账单"]

    def identify(self, filepath: str):
        if filepath.upper().endswith(".EML"):
            self.type = "email"
            from bs4 import BeautifulSoup
            import email
            from email import policy
            import base64
            from html import unescape

            try:
                raw_email = email.message_from_file(
                    open(filepath), policy=policy.default
                )
                raw_body_html = unescape(
                    base64.b64decode(
                        raw_email.get_body().get_payload()
                    ).decode("utf-8")
                )
                raw_body_html = raw_body_html.replace("\xa0", " ")
                soup = BeautifulSoup(raw_body_html, features="lxml")
                self.body = soup.body
                # find 本期账单日
                stmtDateCell = self.body.find("font", string="本期账单日").parent.parent.parent.find_all("font")[2].text
                self.stmt_date = parse(stmtDateCell)
                return "中国建设银行信用卡" in raw_email["Subject"]
            except Exception:
                return False

    def account(self, filepath: str):
        return "ccb_credit_card"

    def date(self, filepath: str):
        return self.stmt_date

    def extract(self, filepath: str, existing=None):
        entries = []
        for ele in self.body.find_all("font", string="上期账单余额(Previous Balance)"):
            table = ele.parent.parent.parent
            for i, row in enumerate(table.find_all("tr")):
                cols = [col.text for col in row.find_all("td")]
                # skip headers/end
                if cols[0] in ["【交易明细】", "交易日", "T-Date", "[人民币账户] RMB Account", "*** 结束 The End ***"]:
                    continue

                # parse data line
                metadata: dict = data.new_metadata(filepath, i)
                tags = set()

                # parse some basic info
                (
                    t_date,
                    p_date,
                    card_number,
                    narration,
                    trans_curr,
                    trans_amount,
                    sett_curr,
                    sett_amount
                ) = cols[:8]
                time = parse(t_date)

                payee = ""

                narration = narration.strip()
                if "-" in narration:
                    # 支付宝 / 财付通 / etc
                    hypen_idx = narration.index("-")
                    narration, payee = (
                        narration[:hypen_idx].strip(),
                        narration[hypen_idx + 1 :].strip(),
                    )

                units = -data.Amount(D(sett_amount), sett_curr.strip())

                # fill metadata
                if trans_curr != sett_curr:
                    metadata["trans"] = trans_amount.strip() + " " + trans_curr.strip()
                if p_date != "":
                    metadata["post_date"] = p_date.strip()

                expense = True # TODO
                account1 = find_account_by_card_number(self.config, card_number)
                my_assert(account1, f"Unknown card number {card_number}", i, cols)
                account2 = resolve_destination(
                    self.config, narration, payee, expense, metadata, tags
                )

                # create transaction
                entries.append(
                    make_two_posting_txn(
                        filepath,
                        i,
                        time.date(),
                        payee,
                        narration,
                        tags,
                        metadata,
                        account1,
                        account2,
                        units,
                    )
                )

        return entries
