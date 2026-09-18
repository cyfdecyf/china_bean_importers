# read_eml_html helper (shared by the EML credit card importers).

from email import policy
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import helpers

from china_bean_importers.common import read_eml_html

HTML = "<html><body><p>京东&nbsp;购物</p></body></html>"


def make_qp(path):
    msg = EmailMessage(policy=policy.default)
    msg["Subject"] = "账单"
    msg.set_content(HTML, subtype="html", cte="quoted-printable")
    path.write_text(msg.as_string(), encoding="utf-8")
    return path


def make_b64(path, encoding="utf-8", nested=False):
    html = HTML
    if nested:
        related = MIMEMultipart("related")
        related.attach(MIMEText(html, "html", encoding))
        msg = MIMEMultipart("mixed")
        msg.attach(related)
    else:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(html, "html", encoding))
    msg["Subject"] = "账单"
    path.write_text(msg.as_string(), encoding="utf-8")
    return path


def test_quoted_printable(tmp_path):
    path = make_qp(tmp_path / "qp.eml")
    subject, html = read_eml_html(str(path))
    assert subject == "账单"
    # &nbsp; is unescaped to a plain space
    assert "京东 购物" in html


def test_base64(tmp_path):
    path = make_b64(tmp_path / "b64.eml")
    subject, html = read_eml_html(str(path), b64=True)
    assert subject == "账单"
    assert "京东 购物" in html


def test_base64_gbk_nested(tmp_path):
    path = make_b64(tmp_path / "nested.eml", encoding="gbk", nested=True)
    subject, html = read_eml_html(
        str(path), encoding="gbk", b64=True, unwrap_nested=True
    )
    assert subject == "账单"
    assert "京东 购物" in html
