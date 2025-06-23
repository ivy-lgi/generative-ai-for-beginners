import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from qdrant_client import QdrantClient


load_dotenv()

api_version = os.environ["AZURE_OPENAI_API_VERSION"]
azure_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
api_key = os.environ["AZURE_OPENAI_API_KEY"]

deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
embedding_deployment = os.environ["AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"]

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=azure_endpoint,
    api_key=api_key,
)

qdrant_client = QdrantClient(host="localhost", port=6333)
collection_name = "documentation_embeddings"


def create_embedding(text: str):
    response = client.embeddings.create(input=text, model=embedding_deployment)
    return response.data[0].embedding


def search_similar_documents(query_vector, limit=5):
    search_results = qdrant_client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=limit,
        with_payload=True,
    )
    return search_results.points


def format_context(search_results):
    context_parts = []

    for i, result in enumerate(search_results, 1):
        payload = result.payload
        context_parts.append(
            f"Document {i}:\n"
            f"File: {payload['file_title']}\n"
            f"Section: {payload['section_title']}\n"
            f"Content: {payload['content']}\n"
            f"---"
        )

    return "\n".join(context_parts)


def chatbot(user_input):
    query_vector = create_embedding(user_input)
    search_results = search_similar_documents(query_vector)

    if not search_results:
        return (
            "Sorry, I couldn't find any relevant documentation to answer your question."
        )

    context = format_context(search_results)

    system_prompt = """You are a helpful assistant that answers questions based on the provided documentation context. 
    Use only the information provided in the context to answer questions. If the context doesn't contain enough 
    information to answer the question, say so. Always cite the specific document and section when providing information.
    
    Format your response clearly and be helpful to the user."""

    user_prompt = f"""Context from documentation:
{context}

Question: {user_input}

Please answer the question based on the provided context."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat.completions.create(
        model=deployment, messages=messages, temperature=0.3, max_tokens=1000
    )

    return response.choices[0].message.content


def main():
    print("🚀 Documentation RAG Chatbot")
    print("=" * 50)
    print("This chatbot can answer questions about Axon Ivy.")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("\n❓ Your question: ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                print("👋 Goodbye!")
                break

            if not user_input:
                continue

            response = chatbot(user_input)
            print(f"\n🤖 Answer: {response}")

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
