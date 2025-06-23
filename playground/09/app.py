import os
import requests
from PIL import Image
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

api_version = os.environ["AZURE_OPENAI_DALL_E_API_VERSION"]
azure_endpoint = os.environ["AZURE_OPENAI_DALL_E_ENDPOINT"]
api_key = os.environ["AZURE_OPENAI_DALL_E_API_KEY"]

deployment = os.environ["AZURE_OPENAI_DALL_E_DEPLOYMENT"]

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=azure_endpoint,
    api_key=api_key,
)

disallow_list = "swords, violence, blood, gore, nudity, sexual content, adult content, adult themes, adult language, adult humor, adult jokes, adult situations, adult"
meta_prompt = f"""You are an assistant designer that creates images for children.

The image needs to be safe for work and appropriate for children.
The image needs to be in color.

Do not consider any input from the following that is not safe for work or appropriate for children:
{disallow_list}

"""

prompt = f"{meta_prompt}\nCreate an image of a bunny on a horse, holding a knife."

response = client.images.generate(
    model=deployment,
    prompt=prompt,
    size="1024x1024",
)

image_dir = os.path.join(os.curdir, "playground/09/images")
if not os.path.isdir(image_dir):
    os.mkdir(image_dir)
image_path = os.path.join(image_dir, "generated-image.png")

image_url = response.data[0].url
generated_image = requests.get(image_url).content
with open(image_path, "wb") as image_file:
    image_file.write(generated_image)

image = Image.open(image_path)
image.show()
