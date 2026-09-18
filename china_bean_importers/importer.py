import re
import sys
from datetime import datetime
from pathlib import Path

from beangulp import Importer

from china_bean_importers.common import *


class BaseImporter(Importer):
    FLAG = FLAG

    def __init__(self, config) -> None:
        super().__init__()
        self.config: dict = config
        self.match_keywords: list[str] | None = None
        self.file_account_name: str | None = None
        self.full_content: str = ""
        self.content: list[str] = []
        self.start: datetime | None = None
        self.end: datetime | None = None
        self.filetype: str | None = None

    def identify(self, filepath: str) -> bool:
        raise NotImplementedError

    def parse_metadata(self, filepath: str):
        raise NotImplementedError

    def account(self, filepath: str) -> str:
        if self.file_account_name is None:
            raise NotImplementedError("file_account_name not set")
        return self.file_account_name

    def date(self, filepath: str) -> datetime | None:
        return self.start

    def filename(self, filepath: str) -> str | None:
        assert self.filetype is not None
        if self.end:
            return f"to.{self.end.date().isoformat()}.{self.filetype}"

    # common methods for table-based import
    def extract(self, filepath: str, existing=None):
        return list(
            filter(
                lambda x: x is not None,
                [
                    self.generate_tx(r, i, filepath)
                    for i, r in enumerate(self.extract_rows())
                ],
            )
        )

    def extract_rows(self) -> list[list[str]]:
        raise NotImplementedError

    def generate_tx(self, row: list[str], lineno: int, filepath: str):
        raise NotImplementedError


def excel_to_text(filepath: str, engine_module: str) -> str | None:
    """Read an Excel file via pandas as CSV text; None if deps are missing."""
    try:
        import pandas as pd
        import importlib

        importlib.import_module(engine_module)
    except ImportError:
        print(
            f"WARNING: missing pandas or {engine_module}, cannot parse {filepath}",
            file=sys.stderr,
        )
        return None
    return pd.read_excel(filepath).to_csv(index=False)


class CsvImporter(BaseImporter):
    """Tabular importer for delimited text files (normally CSV).

    Subclasses set match_keywords; identify() fills self.full_content (raw
    text) and self.content (non-empty stripped lines) once matched.
    """

    # accepted filename suffixes; also used as the filetype in filename()
    suffixes: tuple[str, ...] = (".csv",)

    def __init__(self, config) -> None:
        super().__init__(config)
        self.encoding: str = "utf-8"
        self.filetype = "csv"

    def read_source(self, filepath: str) -> str | None:
        """Return the tabular text of the file, or None if unreadable."""
        with open(filepath, "r", encoding=self.encoding) as f:
            return f.read()

    def identify(self, filepath: str) -> bool:
        if self.match_keywords is None:
            raise NotImplementedError("match_keywords not set")
        if not filepath.lower().endswith(self.suffixes):
            return False
        try:
            content = self.read_source(filepath)
            if content is None:
                return False
            self.full_content = content
            self.content = [
                ln.strip() for ln in content.splitlines() if ln.strip() != ""
            ]
            if all(keyword in content for keyword in self.match_keywords):
                self.filetype = Path(filepath).suffix.lstrip(".")
                self.parse_metadata(filepath)
                return True
            return False
        except Exception:
            return False


class CsvOrXlsxImporter(CsvImporter):
    """CSV or xlsx files; the latter are read via pandas + openpyxl."""

    suffixes = (".csv", ".xlsx")

    def read_source(self, filepath: str) -> str | None:
        if filepath.lower().endswith(".xlsx"):
            return excel_to_text(filepath, "openpyxl")
        return super().read_source(filepath)


class XlsImporter(CsvImporter):
    """Legacy xls files, read via pandas + xlrd."""

    suffixes = (".xls",)

    def __init__(self, config) -> None:
        super().__init__(config)
        self.filetype = "xls"

    def read_source(self, filepath: str) -> str | None:
        return excel_to_text(filepath, "xlrd")


class PdfImporter(BaseImporter):
    def __init__(self, config) -> None:
        super().__init__(config)
        self.filetype = "pdf"
        self.column_offsets: list[int] | None = None
        self.content_start_keyword: str | None = None
        self.content_start_regex: re.Pattern | None = None
        self.content_end_keyword: str | None = None
        self.content_end_regex: re.Pattern | None = None

    def identify(self, filepath: str) -> bool:
        if self.match_keywords is None:
            raise NotImplementedError("match_keywords not set")

        if "pdf" not in filepath.lower():
            return False

        doc = open_pdf(self.config, filepath)
        if doc is None:
            return False

        self.full_content = ""
        self.content = []
        for page in doc:
            self.content.extend(page.get_text("words"))
            self.full_content += page.get_text("text")

        if all(map(lambda c: c in self.full_content, self.match_keywords)):
            self.parse_metadata(filepath)
            return True
        return False

    def extract_rows(self):
        assert self.column_offsets
        assert self.content_start_keyword or self.content_start_regex
        assert self.content_end_keyword or self.content_end_regex

        entries = []
        parts = []
        valid = False
        last_y0 = 0
        last_col = -1

        for x0, y0, x1, y1, content, block_no, line_no, word_no in self.content:
            content = content.strip()
            # for debugging
            # print(x0, y0, content, file=sys.stderr)

            if not valid and (
                (self.content_start_keyword and self.content_start_keyword in content)
                or (
                    self.content_start_regex and self.content_start_regex.match(content)
                )
            ):
                valid = True
            elif valid and (
                (self.content_end_keyword and self.content_end_keyword in content)
                or (self.content_end_regex and self.content_end_regex.match(content))
            ):
                valid = False
            elif valid:
                # find current column
                curr_col = -1
                for i, off in enumerate(self.column_offsets):
                    if x0 >= off:
                        curr_col = i
                if curr_col > last_col:
                    # new column in existing row
                    parts.append(content)
                elif curr_col == last_col:
                    # same column in existing row
                    if y0 == last_y0:
                        # no newline
                        parts[-1] = parts[-1] + " " + content
                    else:
                        # newline
                        parts[-1] = parts[-1] + content
                else:
                    # new row
                    if len(parts) > 0:
                        entries.append(parts)
                        parts = []
                    parts.append(content)
                last_y0 = y0
                last_col = curr_col

        if len(parts) > 0:
            entries.append(parts)
            parts = []

        return entries


class PdfTableImporter(BaseImporter):
    """PDF importer relying on pymupdf's find_tables().

    Subclasses configure header_first_cell(_regex) to skip header rows and
    may set vertical_lines for tables with known column positions.
    """

    def __init__(self, config) -> None:
        super().__init__(config)
        self.filetype = "pdf"
        self.vertical_lines: list[int] | None = None
        self.header_first_cell: str | None = None
        self.header_first_cell_regex: re.Pattern | None = None
        self.doc = None

    def identify(self, filepath: str) -> bool:
        if self.match_keywords is None:
            raise NotImplementedError("match_keywords not set")

        if "pdf" not in filepath.lower():
            return False

        doc = open_pdf(self.config, filepath)
        if doc is None:
            return False
        doc = self.preprocess_doc(doc)

        self.full_content = ""
        self.content = []
        self.doc = doc
        for page in doc:
            self.content.extend(page.get_text("words"))
            self.full_content += page.get_text("text")

        if all(keyword in self.full_content for keyword in self.match_keywords):
            self.parse_metadata(filepath)
            return True
        return False

    def preprocess_doc(self, doc):
        return doc

    def is_row_filtered(self, row):
        if len(row) == 0:
            return True
        # rows are newline-stripped; compare against a newline-stripped
        # header_first_cell so multi-line header cells also match
        if (
            self.header_first_cell is not None
            and row[0] == self.header_first_cell.replace("\n", "")
        ):
            return True
        if self.header_first_cell_regex is not None and self.header_first_cell_regex.match(
            row[0]
        ):
            return True
        return False

    def extract_rows(self):
        rows = []
        for page in self.doc:
            for tbl in page.find_tables(vertical_lines=self.vertical_lines).tables:
                # TODO: Check vertical offset
                for raw in tbl.extract():
                    row = [cell.replace("\n", "").strip() for cell in raw]
                    if not self.is_row_filtered(row):
                        rows.append(row)
        return rows
