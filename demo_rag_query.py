#!/usr/bin/env python3
"""
Demo script to test RAG pipeline with LLM response generation.

This demonstrates the full workflow:
1. User asks a question in Ukrainian
2. RAG retrieves relevant documents
3. LLM generates a human-readable answer using the context
4. User sees a helpful, accurate response with sources

Usage:
    python demo_rag_query.py "ваше питання тут"
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.rag.retriever import RAGRetriever
from src.utils.logger import get_logger
import ollama

logger = get_logger()


def generate_answer(query: str, context: str, model: str = None) -> str:
    """
    Generate answer using LLM with retrieved context.

    Args:
        query: User's question
        context: Retrieved context from RAG
        model: Ollama model to use

    Returns:
        Generated answer in Ukrainian
    """
    system_prompt = """Ти - помічник для українських біженців у Великій Британії.

ВАЖЛИВІ ПРАВИЛА:
1. Відповідай ТІЛЬКИ українською мовою
2. Використовуй ТІЛЬКИ інформацію з наданого контексту - НЕ ДОДАВАЙ нічого від себе
3. Якщо в контексті немає відповіді - скажи це чесно
4. Завжди вказуй джерела (gov.uk або opora.uk)
5. НІКОЛИ не вигадуй юридичну інформацію, кроки, процедури чи факти
6. Якщо контекст каже "дивіться інструкцію за посиланням" - просто направ користувача до посилання, НЕ ВИГАДУЙ кроки
7. Додай відмову відповідальності: "Це не юридична консультація. Для точної інформації зверніться до спеціаліста."

ПРАВИЛА РОБОТИ З ПОСИЛАННЯМИ:
8. ЗАВЖДИ включай повні URL-посилання з контексту, якщо вони є доступні
9. Якщо у контексті є "Посилання: https://..." - ОБОВ'ЯЗКОВО додай це посилання у відповідь
10. Якщо посилання є у самому тексті документа - збережи його у відповіді
11. НІКОЛИ не вигадуй і не створюй посилання самостійно
12. Використовуй ТІЛЬКИ ті URL, які явно вказані у наданому контексті
13. Якщо посилання немає у контексті - не додавай його взагалі

Відповідай простою мовою, коротко і по суті. Якщо контекст направляє до посилання - просто дай посилання, не додавай зайвого.

ПРИКЛАД ПРАВИЛЬНОЇ ВІДПОВІДІ З ПОСИЛАННЯМ:
Питання: "Як зареєструватися для оплати газу?"
Контекст містить: "Посилання: https://ua.opora.uk/guide"
Твоя відповідь повинна включати:
"Для реєстрації перегляньте детальну інструкцію за посиланням: https://ua.opora.uk/guide

Джерело: opora.uk"
"""

    user_prompt = f"""Питання користувача: {query}

Релевантна інформація з офіційних джерел:
{context}

ВАЖЛИВО: Дай чітку, корисну відповідь українською мовою на основі ТІЛЬКИ цієї інформації.
Якщо у контексті є посилання (Посилання: https://...) - ОБОВ'ЯЗКОВО включи його у відповідь."""

    try:
        from src.utils.config import get_settings
        settings = get_settings()

        # Use model from config if not specified
        if model is None:
            model = settings.ollama_model_name

        client = ollama.Client(host=settings.ollama_base_url)

        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            options={
                "temperature": 0.3,
                "num_ctx": 2048,
            }
        )

        return response['message']['content']

    except Exception as e:
        logger.error(f"Failed to generate answer: {e}")
        return f"Помилка при генерації відповіді: {e}"


def main():
    """Main demo function."""

    # Get query from command line or use default
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "Підкажіть мені що потрібно для роботи, я щойно приїхав до Великої Британії?"

    print("=" * 80)
    print("  ДЕМО: RAG + LLM Pipeline для українського бота")
    print("=" * 80)
    print()

    # Step 1: Initialize retriever
    print("📚 Крок 1: Ініціалізація RAG системи...")
    retriever = RAGRetriever()

    if not retriever.initialize():
        print("❌ Не вдалося підключитися до векторної бази даних")
        return 1

    print("✅ RAG система готова")
    print()

    # Step 2: Show user query
    print("❓ ПИТАННЯ КОРИСТУВАЧА:")
    print(f"   {query}")
    print()

    # Step 3: Retrieve relevant documents
    print("🔍 Крок 2: Пошук релевантних документів...")
    result = retriever.retrieve(query, top_k=3)

    if result.found_documents == 0:
        print("❌ Не знайдено релевантних документів")
        return 1

    print(f"✅ Знайдено {result.found_documents} релевантних документів")
    print()

    # Step 4: Show retrieved documents
    print("📄 ЗНАЙДЕНІ ДОКУМЕНТИ:")
    print("-" * 80)
    for i, source in enumerate(result.sources, 1):
        metadata = source.get('metadata', {})
        print(f"\n{i}. Джерело: {metadata.get('source', 'N/A')}")
        print(f"   Категорія: {metadata.get('category', 'N/A')}")
        print(f"   Релевантність: {source['score']:.2%}")
        print(f"   Текст: {source['text']}")

    print()
    print("-" * 80)
    print()

    # Step 5: Show context that will be sent to LLM
    print("📋 КОНТЕКСТ ДЛЯ LLM:")
    print("-" * 80)
    print(result.context[:500] + "..." if len(result.context) > 500 else result.context)
    print("-" * 80)
    print()

    # Step 6: Generate answer with LLM
    print("🤖 Крок 3: Генерація відповіді через LLM...")
    print()

    answer = generate_answer(query, result.context)

    # Step 7: Show final answer (what user sees)
    print("=" * 80)
    print("  💬 ВІДПОВІДЬ БОТА (що побачить користувач):")
    print("=" * 80)
    print()
    print(answer)
    print()
    print("=" * 80)
    print()

    # Summary
    print("✅ PIPELINE ЗАВЕРШЕНО:")
    print(f"   • Знайдено документів: {result.found_documents}")
    print(f"   • Довжина контексту: {len(result.context)} символів")
    print(f"   • Довжина відповіді: {len(answer)} символів")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
