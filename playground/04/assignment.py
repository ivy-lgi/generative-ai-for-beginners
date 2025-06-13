# The OpenAI SDK was updated on Nov 8, 2023 with new guidance for migration
# See: https://github.com/openai/openai-python/discussions/742

## Updated
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AzureOpenAI(
    api_key=os.environ[
        "AZURE_OPENAI_API_KEY"
    ],  # this is also the default, it can be omitted
    api_version="2023-05-15",
)

deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]


## Updated
# def get_completion(prompt):
#     messages = [{"role": "user", "content": prompt}]
#     response = client.chat.completions.create(
#         model=deployment,
#         messages=messages,
#         temperature=0,  # this is the degree of randomness of the model's output
#         max_tokens=1024,
#     )
#     return response.choices[0].message.content


# ## ---------- Call the helper method

# ### 1. Set primary content or prompt text
# text = f"""
# Jupiter is the fifth planet from the Sun and the \
# largest in the Solar System. It is a gas giant with \
# a mass one-thousandth that of the Sun, but two-and-a-half \
# times that of all the other planets in the Solar System combined. \
# Jupiter is one of the brightest objects visible to the naked eye \
# in the night sky, and has been known to ancient civilizations since \
# before recorded history. It is named after the Roman god Jupiter.[19] \
# When viewed from Earth, Jupiter can be bright enough for its reflected \
# light to cast visible shadows,[20] and is on average the third-brightest \
# natural object in the night sky after the Moon and Venus.
# """

# ### 2. Use that in the prompt template below
# prompt = f"""
# Summarize content you are provided with for a second-grade student.
# ```{text}```
# """

# ## 3. Run the prompt
# response = get_completion(prompt)
# print(response)

response = client.chat.completions.create(
    model=deployment,
    messages=[
        {"role": "system", "content": "You are a sarcastic assistant."},
        {"role": "user", "content": "Who won the world series in 2020?"},
        {
            "role": "assistant",
            "content": "Who do you think won? The Los Angeles Dodgers of course.",
        },
        {"role": "user", "content": "Where was it played?"},
    ],
)
print(response.choices[0].message.content)
