import os
import json
import requests
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

messages = [
    {
        "role": "user",
        "content": "Find me a good course for a beginner student to learn Azure.",
    }
]

functions = [
    {
        "name": "search_courses",
        "description": "Retrieves courses from the search index based on the parameters provided",
        "parameters": {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "description": "The role of the learner (i.e. developer, data scientist, student, etc.)",
                },
                "product": {
                    "type": "string",
                    "description": "The product that the lesson is covering (i.e. Azure, Power BI, etc.)",
                },
                "level": {
                    "type": "string",
                    "description": "The level of experience the learner has prior to taking the course (i.e. beginner, intermediate, advanced)",
                },
            },
            "required": ["role"],
        },
    }
]

response = client.chat.completions.create(
    model=deployment, messages=messages, functions=functions, function_call="auto"
)
message = response.choices[0].message


def search_courses(role, product, level):
    url = "https://learn.microsoft.com/api/catalog/"
    params = {"role": role, "product": product, "level": level}
    response = requests.get(url, params=params)
    modules = response.json()["modules"]
    results = []
    for module in modules[:5]:
        title = module["title"]
        url = module["url"]
        results.append({"title": title, "url": url})
    return str(results)


if message.function_call.name:
    function_name = message.function_call.name
    available_functions = {
        "search_courses": search_courses,
    }
    function_to_call = available_functions[function_name]
    function_args = json.loads(message.function_call.arguments)
    function_response = function_to_call(**function_args)
    messages.append(message)
    messages.append(
        {
            "role": "function",
            "name": function_name,
            "content": function_response,
        }
    )

response = client.chat.completions.create(
    messages=messages,
    model=deployment,
    function_call="auto",
    functions=functions,
)

print(response.choices[0].message.content)
