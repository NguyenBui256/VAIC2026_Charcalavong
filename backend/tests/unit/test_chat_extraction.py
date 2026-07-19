from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import ValidationError
from app.modules.chat.extraction import extract_text, select_attachment_context


def test_extract_txt_and_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "policy.txt"
    path.write_bytes("\ufeffHạn mức vay: 500 triệu".encode())
    assert "500 triệu" in extract_text(path, path.name, "text/plain")


def test_extract_csv_is_bounded_to_header_plus_200_rows(tmp_path: Path) -> None:
    path = tmp_path / "loans.csv"
    path.write_text(
        "id,amount\n" + "\n".join(f"{i},{i * 10}" for i in range(300)), encoding="utf-8"
    )
    result = extract_text(path, path.name, "text/csv")
    assert "id | amount" in result
    assert "199 | 1990" in result
    assert "299 | 2990" not in result


def test_extract_docx(tmp_path: Path) -> None:
    from docx import Document

    path = tmp_path / "requirements.docx"
    document = Document()
    document.add_paragraph("Bắt buộc có bước thẩm định")
    document.save(path)
    assert "thẩm định" in extract_text(
        path,
        path.name,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


def test_extract_xlsx_limits_columns_and_sheets(tmp_path: Path) -> None:
    from openpyxl import Workbook

    path = tmp_path / "fields.xlsx"
    workbook = Workbook()
    workbook.active.append(["customer_id", "income"])
    workbook.active.append(["C01", 30_000_000])
    workbook.save(path)
    result = extract_text(
        path,
        path.name,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    assert "customer_id | income" in result
    assert "C01 | 30000000" in result


def test_reject_mime_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "fake.pdf"
    path.write_text("not a pdf", encoding="utf-8")
    with pytest.raises(ValidationError, match="signature"):
        extract_text(path, path.name, "application/pdf")


def test_context_selection_prioritizes_relevant_chunks_and_marks_source() -> None:
    noise = "không liên quan " * 200
    relevant = "điều kiện thu nhập tối thiểu 20 triệu đồng"
    context = select_attachment_context(
        "thu nhập tối thiểu là bao nhiêu?",
        [("policy.txt", noise + relevant)],
    )
    assert "policy.txt" in context
    assert "20 triệu" in context
