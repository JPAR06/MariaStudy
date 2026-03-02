"""Local sentence-transformers embedder (no API cost)."""
import streamlit as st
from sentence_transformers import SentenceTransformer
from src.config import EMBED_MODEL


@st.cache_resource(show_spinner="A carregar modelo de embeddings...")
def get_embedder() -> SentenceTransformer:
    return SentenceTransformer(EMBED_MODEL)


def embed(texts: list[str]) -> list[list[float]]:
    model = get_embedder()
    return model.encode(texts, show_progress_bar=False).tolist()
