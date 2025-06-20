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

prompt = "Classify the following inquiry into one of the following: categories: [Pricing, Hardware Support, Software Support]\n\ninquiry: Hello, one of the keys on my laptop keyboard broke recently and I'll need a replacement:\n\nClassified category:"

response = client.chat.completions.create(
    model=deployment,
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ],
)

print(response.choices[0].message.content)
