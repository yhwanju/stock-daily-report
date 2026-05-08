from __future__ import annotations

import json
from pathlib import Path

import requests


class DiscordWebhookClient:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send_text(self, content: str) -> None:
        for chunk in _split_for_discord(content):
            response = requests.post(
                self.webhook_url,
                json={"content": chunk},
                timeout=15,
            )
            response.raise_for_status()

    def send_text_with_files(self, content: str, file_paths: list[Path]) -> None:
        chunks = _split_for_discord(content)
        for chunk in chunks[:-1]:
            response = requests.post(
                self.webhook_url,
                json={"content": chunk},
                timeout=15,
            )
            response.raise_for_status()

        for batch_index, batch in enumerate(_chunks(file_paths, 10)):
            payload = {"content": chunks[-1] if batch_index == 0 else ""}
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
