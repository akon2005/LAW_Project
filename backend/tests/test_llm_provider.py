"""Tests for LLM provider wiring (no real network calls / keys)."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.rag_service import get_llm_client

FAKE_HF = "hf_" + "a" * 40
FAKE_OPENAI = "sk-" + "b" * 40

_CLEAR = {
    "HF_API_TOKEN": "",
    "HF_API_KEY": "",
    "OPENAI_API_KEY": "",
    "ANTHROPIC_API_KEY": "",
}


class ProviderResolutionTests(unittest.TestCase):
    def test_huggingface_env_token(self):
        env = {**_CLEAR, "LLM_PROVIDER": "huggingface", "HF_API_TOKEN": FAKE_HF}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch(
            "huggingface_hub.get_token", return_value=None
        ):
            client, model, provider = get_llm_client()
        self.assertEqual(provider, "huggingface")
        self.assertIsNotNone(client)

    def test_huggingface_cached_cli_token_fallback(self):
        env = {**_CLEAR, "LLM_PROVIDER": "huggingface"}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch(
            "huggingface_hub.get_token", return_value=FAKE_HF
        ):
            client, model, provider = get_llm_client()
        self.assertEqual(provider, "huggingface")
        self.assertIsNotNone(client)

    def test_placeholder_token_is_rejected(self):
        env = {**_CLEAR, "LLM_PROVIDER": "huggingface", "HF_API_TOKEN": "your-token-here"}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch(
            "huggingface_hub.get_token", return_value=None
        ):
            client, model, provider = get_llm_client()
        self.assertIsNone(client)
        self.assertEqual(provider, "")

    def test_openai_env_key(self):
        env = {**_CLEAR, "LLM_PROVIDER": "openai", "OPENAI_API_KEY": FAKE_OPENAI}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch(
            "huggingface_hub.get_token", return_value=None
        ):
            client, model, provider = get_llm_client()
        self.assertEqual(provider, "openai")
        self.assertIsNotNone(client)


if __name__ == "__main__":
    unittest.main()
