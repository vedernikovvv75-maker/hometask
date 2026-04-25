from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sys
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


@dataclass
class TextAgent:
    use_thinking_mode: bool = True
    system_prompt: str = "Вы полезный ассистент, отвечайте на русском языке."
    timeout: int = 60
    conversation: list[dict[str, str]] = field(default_factory=list)
    history_file: str = "history.json"

    def __post_init__(self) -> None:
        self._validate_required_env()
        self.openai_client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1"),
            timeout=self.timeout,
        )
        self.anthropic_client = Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.proxyapi.ru/anthropic"),
            timeout=self.timeout,
        )
        self.openai_model = os.getenv("OPENAI_MODEL", "grok-code-fast-1")
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
        self.thinking_budget = int(os.getenv("ANTHROPIC_THINKING_BUDGET", "1500"))
        configured_max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", "2200"))
        self.anthropic_max_tokens = max(configured_max_tokens, self.thinking_budget + 1)
        self.history_path = Path(os.getenv("CHAT_HISTORY_FILE", self.history_file))
        self._load_history()

    def _validate_required_env(self) -> None:
        required_env = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
        missing = [key for key in required_env if not os.getenv(key)]
        if missing:
            missing_keys = ", ".join(missing)
            raise ValueError(
                f"Не найдены обязательные переменные окружения: {missing_keys}. "
                "Заполните .env на основе EnvExample."
            )

    def generate_response(self, user_message: str) -> str:
        self.conversation.append({"role": "user", "content": user_message})
        if self.use_thinking_mode:
            answer = self._generate_claude_thinking()
        else:
            answer = self._generate_openai_chat()
        self.conversation.append({"role": "assistant", "content": answer})
        self._save_history()
        return answer

    def _generate_openai_chat(self) -> str:
        messages = [{"role": "system", "content": self.system_prompt}, *self.conversation]
        response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content or ""

    def _generate_claude_thinking(self) -> str:
        response = self.anthropic_client.messages.create(
            model=self.anthropic_model,
            max_tokens=self.anthropic_max_tokens,
            system=self.system_prompt,
            messages=self.conversation,
            thinking={"type": "enabled", "budget_tokens": self.thinking_budget},
        )
        self._print_reasoning_stats(response)
        return self._extract_text_content(response.content)

    @staticmethod
    def _extract_text_content(content_blocks: list[Any]) -> str:
        parts: list[str] = []
        for block in content_blocks:
            block_type = getattr(block, "type", "")
            if block_type == "text":
                text_value = getattr(block, "text", "")
                if text_value:
                    parts.append(text_value)
        return "\n".join(parts).strip()

    @staticmethod
    def _print_reasoning_stats(response: Any) -> None:
        usage = getattr(response, "usage", None)
        if not usage:
            return
        thinking_tokens = getattr(usage, "thinking_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        if thinking_tokens is None and output_tokens is None:
            return

        print("\n=== Reasoning Stats ===")
        if thinking_tokens is not None:
            print(f"Thinking tokens: {thinking_tokens}")
        if output_tokens is not None:
            print(f"Output tokens:   {output_tokens}")
        print("=======================\n")

    def _load_history(self) -> None:
        if not self.history_path.exists():
            return
        try:
            raw_data = self.history_path.read_text(encoding="utf-8")
            payload = json.loads(raw_data)
            if isinstance(payload, list):
                safe_items = []
                for item in payload:
                    if isinstance(item, dict) and {"role", "content"} <= item.keys():
                        safe_items.append(
                            {"role": str(item["role"]), "content": str(item["content"])}
                        )
                self.conversation = safe_items
        except (OSError, json.JSONDecodeError) as error:
            print(f"Не удалось загрузить историю ({self.history_path}): {error}")

    def _save_history(self) -> None:
        try:
            self.history_path.write_text(
                json.dumps(self.conversation, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as error:
            print(f"Не удалось сохранить историю ({self.history_path}): {error}")


def choose_mode() -> bool:
    print("Выберите режим работы:")
    print("1 - Думающая модель (Claude) [по умолчанию]")
    print("2 - Обычная модель (OpenAI Chat Completions)")
    choice = input("Введите 1 или 2: ").strip()
    return choice != "2"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    use_thinking_mode = choose_mode()
    try:
        agent = TextAgent(use_thinking_mode=use_thinking_mode)
    except ValueError as error:
        print(f"Ошибка конфигурации: {error}")
        return

    mode_name = "Claude thinking mode" if use_thinking_mode else "OpenAI chat mode"
    selected_model = agent.anthropic_model if use_thinking_mode else agent.openai_model
    selected_base_url = (
        os.getenv("ANTHROPIC_BASE_URL", "https://api.proxyapi.ru/anthropic")
        if use_thinking_mode
        else os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1")
    )

    print("\n=== Конфигурация запуска ===")
    print(f"Режим:           {mode_name}")
    print(f"Модель:          {selected_model}")
    print(f"Base URL:        {selected_base_url}")
    print(f"Таймаут (сек):   {agent.timeout}")
    print(f"Файл истории:    {agent.history_path}")
    print(f"Сообщений в кэше:{len(agent.conversation)}")
    print("============================")
    print("Введите 'exit' для завершения.\n")

    while True:
        user_input = input("Вы: ").strip()
        if user_input.lower() == "exit":
            break
        if not user_input:
            continue
        try:
            answer = agent.generate_response(user_input)
            print(f"Агент: {answer}\n")
        except TimeoutError:
            print("Ошибка: превышен таймаут запроса. Попробуйте повторить.\n")
        except Exception as error:
            print(f"Ошибка запроса: {error}\n")

    print("\nИстория диалога:")
    for message in agent.conversation:
        print(f"- {message['role']}: {message['content']}")


if __name__ == "__main__":
    main()
