from text_agent import TextAgent


def run_smoke_test() -> None:
    """
    Minimal manual smoke test.
    Requires configured keys in .env.
    """
    agent = TextAgent(use_thinking_mode=False)
    message = "Привет! Ответь одной короткой фразой."
    print("Отправка:", message)
    answer = agent.generate_response(message)
    print("Ответ:", answer)


if __name__ == "__main__":
    run_smoke_test()
