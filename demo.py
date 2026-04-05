from dotenv import load_dotenv
import os
from nomic import embed

load_dotenv()

result = embed.text(
    texts=["test api working"],
    model="nomic-embed-text-v1"
)

print(result)