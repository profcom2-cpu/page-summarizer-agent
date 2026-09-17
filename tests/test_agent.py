from io import BytesIO

from docx import Document

from page_summarizer.agent import PageSummarizerAgent, split_sentences
from page_summarizer.exceptions import ExtractionError, FetchError, ValidationError
from page_summarizer.extractor import extract_from_bytes, fetch_page_html, normalize_text


def test_split_sentences_handles_common_punctuation() -> None:
    text = "Первое предложение. Второе предложение! Третье предложение?"
    assert split_sentences(text) == [
        "Первое предложение.",
        "Второе предложение!",
        "Третье предложение?",
    ]


def test_enforce_max_sentences_cuts_to_five() -> None:
    agent = PageSummarizerAgent.__new__(PageSummarizerAgent)
    text = " ".join(f"Предложение {i}." for i in range(1, 8))
    result = agent._enforce_max_sentences(text)
    assert len(split_sentences(result)) == 5
    assert result.startswith("Предложение 1.")
    assert result.endswith("Предложение 5.")


def test_clean_summary_strips_markdown_and_labels() -> None:
    agent = PageSummarizerAgent.__new__(PageSummarizerAgent)
    raw = "```text\nРезюме: Сайт описывает продукт. Он объясняет условия.\n```"
    cleaned = agent._clean_summary(raw)
    assert not cleaned.startswith("```")
    assert not cleaned.lower().startswith("резюме")


def test_parse_analysis_json_extracts_fields() -> None:
    agent = PageSummarizerAgent.__new__(PageSummarizerAgent)
    raw = """
    {
      "court": "Арбитражный суд города Москвы",
      "case_number": "А40-111331/25",
      "parties": "заявитель — финансовый управляющий, должник — Кулиев Т.Э.",
      "operative_part": "признать требования обоснованными",
      "norms": "ст. 213.9 Федерального закона № 127-ФЗ",
      "summary": "Суд рассмотрел заявление финансового управляющего. Требования признаны обоснованными. Судебные расходы распределены."
    }
    """
    parsed = agent._parse_analysis(raw)
    assert parsed["court"] == "Арбитражный суд города Москвы"
    assert parsed["case_number"] == "А40-111331/25"
    assert "127-ФЗ" in parsed["norms"]
    assert len(split_sentences(parsed["summary"])) == 3


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("  Привет\n\n  мир  \r\n") == "Привет\nмир"


def test_fetch_rejects_non_http_url() -> None:
    try:
        fetch_page_html(
            "ftp://example.com",
            timeout=1,
            max_retries=1,
            user_agent="test",
        )
    except FetchError as exc:
        assert "http://" in str(exc)
    else:
        raise AssertionError("Ожидалась FetchError")


def test_extract_from_bytes_txt() -> None:
    payload = ("Арбитражный суд города Москвы рассмотрел дело о банкротстве. " * 8).encode(
        "utf-8"
    )
    text = extract_from_bytes(payload, filename="act.txt")
    assert "Арбитражный суд города Москвы" in text


def test_extract_from_bytes_docx() -> None:
    document = Document()
    document.add_paragraph(
        "Арбитражный суд города Москвы. Дело № А40-1/2026. "
        "Истец — общество, ответчик — должник. "
        "Руководствуясь статьёй 213.9 Федерального закона № 127-ФЗ, "
        "суд постановил ввести процедуру реализации имущества."
    )
    buffer = BytesIO()
    document.save(buffer)
    text = extract_from_bytes(buffer.getvalue(), filename="act.docx")
    assert "А40-1/2026" in text
    assert "реализации имущества" in text


def test_extract_rejects_doc_extension() -> None:
    try:
        extract_from_bytes(b"legacy", filename="act.doc")
    except ExtractionError as exc:
        assert ".doc" in str(exc)
    else:
        raise AssertionError("Ожидалась ExtractionError")


def test_analyze_requires_source() -> None:
    agent = PageSummarizerAgent.__new__(PageSummarizerAgent)
    try:
        agent._load_source_text(
            url="",
            text="",
            file_path="",
            file_bytes=None,
            filename="",
        )
    except ValidationError as exc:
        assert "судебный акт" in str(exc).lower()
    else:
        raise AssertionError("Ожидалась ValidationError")
