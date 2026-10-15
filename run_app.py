import uvicorn


def main() -> None:
    print("=" * 60)
    print("🚀 AI Repricer для Prom.ua успішно запущено!")
    print("👉 Відкрийте у браузері: http://127.0.0.1:8000")
    print("📱 Підтримується встановлення як PWA додаток на робочий стіл")
    print("=" * 60)

    uvicorn.run("src.api.app:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
