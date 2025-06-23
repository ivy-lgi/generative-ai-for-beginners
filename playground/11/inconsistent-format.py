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

student_1_description = "Emily Johnson is a sophomore majoring in computer science at Duke University. She has a 3.7 GPA. Emily is an active member of the university's Chess Club and Debate Team. She hopes to pursue a career in software engineering after graduating."
student_2_description = "Michael Lee is a sophomore majoring in computer science at Stanford University. He has a 3.8 GPA. Michael is known for his programming skills and is an active member of the university's Robotics Club. He hopes to pursue a career in artificial intelligence after finishing his studies."

meta_prompt = f"""
Please extract the following information from the given text and return it as a JSON object:

name
major
school
grades
club

This is the body of text to extract the information from:
"""

prompt1 = f"""
{meta_prompt}
{student_1_description}
"""

prompt2 = f"""
{meta_prompt}
{student_2_description}
"""

response1 = client.chat.completions.create(
    model=deployment, messages=[{"role": "user", "content": prompt1}]
)
response2 = client.chat.completions.create(
    model=deployment, messages=[{"role": "user", "content": prompt2}]
)

print(response1.choices[0].message.content)
print(response2.choices[0].message.content)
