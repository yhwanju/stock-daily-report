from __future__ import annotations

import json
from pathlib import Path

import requests


class DiscordWebhookClient:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send_text(self, content: str) -> None:
        self._send_text_chunks(content)

    def send_text_with_files(self, content: str, file_paths: list[Path]) -> None:
        if not file_paths:
            self._send_text_chunks(content)
            return

        self._send_file_batches(file_paths)

        summary, links = _split_summary_and_links(content)
        self._send_text_chunks(summary)
        self._send_text_chunks(links)

    def _send_text_chunks(self, content: str) -> None:
        if not content.strip():
            return

        for chunk in _split_for_discord(content):
            response = requests.post(
                self.webhook_url,
                json={"content": chunk},
                timeout=15,
            )
            response.raise_for_status()

    def _send_file_batches(self, file_paths: list[Path]) -> None:
        for batch in _chunks(file_paths, 10):
            payload = {"content": ""}
            files = []
            handles = []
            try:
                for index, path in enumerate(batch):
                    handle = path.open("rb")
                    handles.append(handle)
                    files.append((f"files[{index}]", (path.name, handle, "image/png")))

                response = requests.post(
                    self.webhook_url,
                    data={"payload_json": json.dumps(payload, ensure_ascii=False)},
                    files=files,
                    timeout=60,
                )
                response.raise_for_status()
            finally:
                for handle in handles:
                    handle.close()


def _split_summary_and_links(content: str) -> tuple[str, str]:
    marker = "🔗 기사 원문 링크"
    marker_index = content.find(marker)
    if marker_index == -1:
        return content.strip(), ""

    summary = content[:marker_index].strip()
    links = content[marker_index:].strip()
    return summary, links


def _split_for_discord(content: str, limit: int = 1900) -> list[str]:
    if len(content) <= limit:
        return [content]

    chunks: list[str] = []
    current: list[str] = []
    current_size = 0

    for line in content.splitlines():
        line_size = len(line) + 1
        if current and current_size + line_size > limit:
            chunks.append("\n".join(current))
            current = []
            current_size = 0
        current.append(line)
        current_size += line_size

    if current:
        chunks.append("\n".join(current))

    return chunks


def _chunks(values: list[Path], size: int) -> list[list[Path]]:
    return [values[index : index + size] for index in range(0, len(values), size)]
