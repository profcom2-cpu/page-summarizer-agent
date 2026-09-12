from page_summarizer.agent import PageSummarizerAgent, split_sentences
from page_summarizer.extractor import normalize_text
from page_summarizer.exceptions import FetchError
from page_summarizer.extractor import fetch_page_html


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
