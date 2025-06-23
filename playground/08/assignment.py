import os
from openai import AzureOpenAI
from dotenv import load_dotenv
import numpy
import pandas

load_dotenv()

api_version = os.environ["AZURE_OPENAI_API_VERSION"]
azure_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
api_key = os.environ["AZURE_OPENAI_API_KEY"]

deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
embeddings_deployment = os.environ["AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"]

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=azure_endpoint,
    api_key=api_key,
)

SIMILARITIES_RESULTS_THRESHOLD = 0.75
DATASET_NAME = "playground/08/embedding_index_3m.json"


def load_dataset(source: str) -> pandas.core.frame.DataFrame:
    pd_vectors = pandas.read_json(source)
    return pd_vectors.drop(columns=["text"], errors="ignore").fillna("")


def cosine_similarity(a, b):
    if len(a) > len(b):
        b = numpy.pad(b, (0, len(a) - len(b)), "constant")
    elif len(b) > len(a):
        a = numpy.pad(a, (0, len(b) - len(a)), "constant")
    return numpy.dot(a, b) / (numpy.linalg.norm(a) * numpy.linalg.norm(b))


def get_videos(
    query: str, dataset: pandas.core.frame.DataFrame, rows: int
) -> pandas.core.frame.DataFrame:
    video_vectors = dataset.copy()
    query_embeddings = (
        client.embeddings.create(input=query, model=embeddings_deployment)
        .data[0]
        .embedding
    )
    video_vectors["similarity"] = video_vectors["ada_v2"].apply(
        lambda x: cosine_similarity(numpy.array(query_embeddings), numpy.array(x))
    )
    mask = video_vectors["similarity"] >= SIMILARITIES_RESULTS_THRESHOLD
    video_vectors = video_vectors[mask].copy()
    video_vectors = video_vectors.sort_values(by="similarity", ascending=False).head(
        rows
    )
    return video_vectors.head(rows)


def display_results(videos: pandas.core.frame.DataFrame, query: str):
    def _gen_yt_url(video_id: str, seconds: int) -> str:
        return f"https://youtu.be/{video_id}?t={seconds}"

    print(f"\nVideos similar to '{query}':")
    for _, row in videos.iterrows():
        youtube_url = _gen_yt_url(row["videoId"], row["seconds"])
        print(f" - {row['title']}")
        print(f"   Summary: {' '.join(row['summary'].split()[:15])}...")
        print(f"   YouTube: {youtube_url}")
        print(f"   Similarity: {row['similarity']}")
        print(f"   Speakers: {row['speaker']}")


pd_vectors = load_dataset(DATASET_NAME)

while True:
    query = input("Enter a query: ")
    if query == "exit":
        break
    videos = get_videos(query, pd_vectors, 5)
    display_results(videos, query)
