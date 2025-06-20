import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

api_version = os.environ["AZURE_OPENAI_API_VERSION"]
azure_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
api_key = os.environ["AZURE_OPENAI_API_KEY"]

deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=azure_endpoint,
    api_key=api_key,
)

prompt = "Product description: A home milkshake maker\nSeed words: fast, healthy, compact.\nProduct names: HomeShaker, Fit Shaker, QuickShake, Shake Maker\n\nProduct description: A pair of shoes that can fit any foot size.\nSeed words: adaptable, fit, omni-fit."

response = client.chat.completions.create(
    model=deployment,
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ],
    temperature=1.8,
)

print(response.choices[0].message.content)
