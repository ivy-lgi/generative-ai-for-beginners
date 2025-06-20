import os
from openai import AzureOpenAI
from dotenv import load_dotenv
import numpy

load_dotenv()

api_version = os.environ["AZURE_OPENAI_API_VERSION"]
azure_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
api_key = os.environ["AZURE_OPENAI_API_KEY"]

embeddings_deployment = os.environ["AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"]

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=azure_endpoint,
    api_key=api_key,
)


def cosine_similarity(a, b):
    return numpy.dot(a, b) / (numpy.linalg.norm(a) * numpy.linalg.norm(b))


automobile_embedding = (
    client.embeddings.create(input="automobile", model=embeddings_deployment)
    .data[0]
    .embedding
)
vehicle_embedding = (
    client.embeddings.create(input="vehicle", model=embeddings_deployment)
    .data[0]
    .embedding
)
dinosaur_embedding = (
    client.embeddings.create(input="dinosaur", model=embeddings_deployment)
    .data[0]
    .embedding
)
stick_embedding = (
    client.embeddings.create(input="stick", model=embeddings_deployment)
    .data[0]
    .embedding
)

print(cosine_similarity(automobile_embedding, vehicle_embedding))
print(cosine_similarity(automobile_embedding, dinosaur_embedding))
print(cosine_similarity(automobile_embedding, stick_embedding))
