import json
from unittest.mock import Mock, patch

import pytest

_youtube_transcript_api = pytest.importorskip("youtube_transcript_api")
FetchedTranscriptSnippet = _youtube_transcript_api.FetchedTranscriptSnippet
IpBlocked = _youtube_transcript_api.IpBlocked
TranscriptsDisabled = _youtube_transcript_api.TranscriptsDisabled

import tools


def _snippets(*texts):
    return [
        FetchedTranscriptSnippet(text=text, start=index, duration=1.0)
        for index, text in enumerate(texts)
    ]


def _transcript(language_code, *, is_generated=False, is_translatable=False):
    transcript = Mock()
    transcript.language_code = language_code
    transcript.is_generated = is_generated
    transcript.is_translatable = is_translatable
    return transcript


@patch.object(tools, "YTDLP_AVAILABLE", False)
@patch.object(tools, "YouTubeTranscriptApi")
def test_fetch_url_content_uses_instance_list_and_snippet_text(api_class):
    japanese_manual = _transcript("ja")
    japanese_manual.fetch.return_value = _snippets("日本語", "字幕")
    english_generated = _transcript("en", is_generated=True)
    english_generated.fetch.return_value = _snippets("English", "captions")
    api = api_class.return_value
    api.list.return_value = [english_generated, japanese_manual]

    result = tools.fetch_url_content("https://www.youtube.com/watch?v=video-id")

    assert result == {
        "status": "success",
        "content": "日本語 字幕",
        "url": "https://www.youtube.com/watch?v=video-id",
    }
    api_class.assert_called_once_with()
    api.list.assert_called_once_with("video-id")
    japanese_manual.fetch.assert_called_once_with()
    english_generated.fetch.assert_not_called()
    api.fetch.assert_not_called()


@patch.object(tools, "YTDLP_AVAILABLE", False)
@patch.object(tools, "YouTubeTranscriptApi")
def test_generated_transcript_translation_remains_final_list_fallback(api_class):
    manual = _transcript("ja")
    manual.fetch.side_effect = TranscriptsDisabled("video-id")
    generated = _transcript("de", is_generated=True, is_translatable=True)
    generated.fetch.side_effect = TranscriptsDisabled("video-id")
    translated = generated.translate.return_value
    translated.fetch.return_value = _snippets("translated", "English")
    api = api_class.return_value
    api.list.return_value = [generated, manual]

    result = tools._fetch_youtube_transcript("video-id", max_retries=1)

    assert result == "translated English"
    generated.translate.assert_called_once_with("en")
    api.fetch.assert_not_called()


@patch.object(tools, "YTDLP_AVAILABLE", False)
@patch.object(tools, "YouTubeTranscriptApi")
def test_direct_fetch_fallback_uses_same_instance_and_snippet_text(api_class):
    api = api_class.return_value
    api.list.side_effect = TranscriptsDisabled("video-id")
    api.fetch.return_value = _snippets("direct", "English")

    result = tools._fetch_youtube_transcript("video-id", max_retries=1)

    assert result == "direct English"
    api.list.assert_called_once_with("video-id")
    api.fetch.assert_called_once_with("video-id")


@patch.object(tools, "_fetch_with_ytdlp", return_value="yt-dlp fallback")
@patch.object(tools, "YTDLP_AVAILABLE", True)
@patch.object(tools, "YouTubeTranscriptApi")
def test_json_decode_failures_reach_direct_fetch_and_ytdlp(
    api_class, fetch_with_ytdlp
):
    api = api_class.return_value
    api.list.side_effect = json.JSONDecodeError("invalid", "", 0)
    api.fetch.side_effect = json.JSONDecodeError("invalid", "", 0)

    result = tools._fetch_youtube_transcript("video-id", max_retries=1)

    assert result == "yt-dlp fallback"
    api.fetch.assert_called_once_with("video-id")
    fetch_with_ytdlp.assert_called_once_with("video-id")


@patch.object(tools, "_fetch_with_ytdlp", return_value="yt-dlp fallback")
@patch.object(tools, "YTDLP_AVAILABLE", True)
@patch.object(tools, "YouTubeTranscriptApi")
def test_expected_api_failures_fall_back_to_ytdlp(api_class, fetch_with_ytdlp):
    api = api_class.return_value
    api.list.side_effect = TranscriptsDisabled("video-id")
    api.fetch.side_effect = TranscriptsDisabled("video-id")

    result = tools._fetch_youtube_transcript("video-id", max_retries=1)

    assert result == "yt-dlp fallback"
    fetch_with_ytdlp.assert_called_once_with("video-id")


@patch.object(tools, "YTDLP_AVAILABLE", True)
@patch.object(tools, "_fetch_with_ytdlp")
@patch.object(tools, "YouTubeTranscriptApi")
def test_request_blocked_raises_rate_limit_error(api_class, fetch_with_ytdlp):
    api_class.return_value.list.side_effect = IpBlocked("video-id")

    try:
        tools._fetch_youtube_transcript("video-id", max_retries=1)
    except tools.YouTubeRateLimitError:
        pass
    else:
        raise AssertionError("blocked request did not stop transcript fallbacks")

    fetch_with_ytdlp.assert_not_called()


@patch.object(tools, "YTDLP_AVAILABLE", True)
@patch.object(tools, "_fetch_with_ytdlp")
@patch.object(tools, "YouTubeTranscriptApi")
def test_unexpected_programming_error_is_not_hidden_by_fallback(
    api_class, fetch_with_ytdlp
):
    api_class.return_value.list.side_effect = AttributeError("API changed")

    try:
        tools._fetch_youtube_transcript("video-id", max_retries=1)
    except AttributeError as error:
        assert str(error) == "API changed"
    else:
        raise AssertionError("unexpected programming error was swallowed")

    fetch_with_ytdlp.assert_not_called()
