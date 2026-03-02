"""Groq LLM wrapper — all prompts in European Portuguese."""
import os
import json
import time
import streamlit as st
from groq import Groq
from src.config import LLM_REASONING, LLM_QUALITY, LLM_FAST, LLM_VISION

_SYSTEM = (
    "Responde SEMPRE em português de Portugal (PT-PT). NUNCA uses português do Brasil (PT-BR). "
    "Diferenças obrigatórias PT-PT vs PT-BR: "
    "usa 'neurónio' (NÃO 'neurônio'), 'autónomo' (NÃO 'autônomo'), 'órgão' (igual), "
    "'síndrome' (masculino em PT-PT: 'o síndrome'), 'abdómen' (NÃO 'abdômen'), "
    "'pneumonia' (igual), 'fármaco' (igual), 'infeção' (NÃO 'infecção' pós-AO), "
    "'direção' (NÃO 'direcção' pós-AO), 'você' raramente — prefere 'tu' ou omite. "
    "Vocabulário PT-PT: 'medicamento' (não 'remédio'), 'análises' (não 'exames de sangue' isolado), "
    "'internamento' (não 'internação'), 'consulta' (não 'consulta médica' repetido). "
    "És um assistente especializado para estudantes de medicina. "
    "Sê preciso, cita as fontes e usa terminologia médica correcta."
)


@st.cache_resource(show_spinner=False)
def _client() -> Groq:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        st.error("GROQ_API_KEY não definida no ficheiro .env")
        st.stop()
    return Groq(api_key=key)


def _chat(model: str, messages: list, json_mode: bool = False, max_tokens: int = 2048) -> str:
    kwargs = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = _client().chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


# ── Q&A with citations ────────────────────────────────────────────────────────

def answer_question(chunks: list[dict], question: str) -> str:
    context = ""
    for i, c in enumerate(chunks, 1):
        m = c["metadata"]
        context += f"[{i}] {c['text']}\n(Fonte: {m['file']}, Pág. {m['page']})\n\n"

    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"Com base nos seguintes excertos médicos, responde à pergunta em detalhe.\n"
            f"Usa citações inline [1], [2], etc. sempre que usares informação dos excertos.\n"
            f"No final lista as fontes como:\n"
            f"**Fontes:**\n[1] ficheiro.pdf, Pág. X\n\n"
            f"EXCERTOS:\n{context}\n"
            f"PERGUNTA: {question}"
        )},
    ]
    return _chat(LLM_REASONING, messages, max_tokens=2048)


# ── Flashcards ────────────────────────────────────────────────────────────────

def generate_flashcards(chunks: list[dict], topic: str, n: int) -> list[dict]:
    context = "\n\n".join(
        f"{c['text']}\n(Fonte: {c['metadata']['file']}, Pág. {c['metadata']['page']})"
        for c in chunks
    )
    n_cloze = max(1, n // 3)
    n_basic = n - n_cloze
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"Cria exatamente {n} flashcards de estudo sobre: \"{topic}\".\n"
            f"Usa APENAS o texto médico abaixo como fonte.\n\n"
            f"Tipos a criar:\n"
            f"- {n_basic} cartões BÁSICOS: pergunta clínica ou de mecanismo na frente, resposta completa no verso. card_type='basic'\n"
            f"- {n_cloze} cartões CLOZE: frase com lacuna {{{{c1::termo}}}} na frente, frase completa no verso. card_type='cloze'\n"
            f"  Ex. cloze — frente: 'A {{{{c1::insulina}}}} é produzida pelas células beta.'\n"
            f"              verso:  'A insulina é produzida pelas células beta.'\n\n"
            f"JSON obrigatório:\n"
            f"{{\"flashcards\": [{{\"frente\": \"...\", \"verso\": \"...\", \"fonte\": \"ficheiro.pdf, Pág. X\", \"card_type\": \"basic|cloze\"}}]}}\n\n"
            f"TEXTO:\n{context}"
        )},
    ]
    raw = _chat(LLM_QUALITY, messages, json_mode=True, max_tokens=4000)
    try:
        return json.loads(raw).get("flashcards", [])
    except Exception:
        return []


# ── Quiz ──────────────────────────────────────────────────────────────────────

_QUIZ_DIFFICULTY = {
    "Fácil": (
        "Nível FÁCIL: questões de memória direta e definições. "
        "Cada questão deve testar um único facto isolado (ex: 'Qual é o agente causador de...?', "
        "'Qual o fármaco de primeira linha para...?'). "
        "Os distratores devem ser claramente diferentes da resposta correcta."
    ),
    "Médio": (
        "Nível MÉDIO: questões de compreensão e aplicação. "
        "Cada questão deve relacionar dois conceitos ou pedir ao estudante que aplique um princípio "
        "(ex: 'Um doente com X apresenta Y — qual o mecanismo?', 'Qual a diferença entre A e B?'). "
        "Os distratores devem ser plausíveis mas distinguíveis com conhecimento sólido."
    ),
    "Difícil": (
        "Nível DIFÍCIL: questões de raciocínio clínico e diagnóstico diferencial. "
        "Cada questão deve apresentar um caso clínico curto (2-3 frases: idade, sexo, sintomas, sinais) "
        "e perguntar diagnóstico, próximo passo ou tratamento. "
        "Os distratores devem ser condições que partilham características sobreponíveis — "
        "apenas o estudante que domina os critérios de distinção acerta."
    ),
}

def generate_quiz(chunks: list[dict], topic: str, n: int, difficulty: str) -> list[dict]:
    context = "\n\n".join(
        f"{c['text']}\n(Fonte: {c['metadata']['file']}, Pág. {c['metadata']['page']})"
        for c in chunks
    )
    diff_instructions = _QUIZ_DIFFICULTY.get(difficulty, _QUIZ_DIFFICULTY["Médio"])
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"Cria exatamente {n} questões de escolha múltipla sobre \"{topic}\".\n"
            f"{diff_instructions}\n\n"
            f"Baseia-te apenas no texto médico abaixo.\n"
            f"Formato JSON obrigatório:\n"
            f"{{\"questoes\": [{{\"pergunta\": \"...\", \"opcoes\": [\"A) ...\", \"B) ...\", \"C) ...\", \"D) ...\"], "
            f"\"correta\": 0, \"explicacao\": \"explicação detalhada de porquê a resposta é correcta e os outros estão errados\", "
            f"\"fonte\": \"ficheiro.pdf, Pág. X\"}}]}}\n"
            f"(\"correta\" é o índice 0-3 da opção correcta)\n\n"
            f"TEXTO:\n{context}"
        )},
    ]
    raw = _chat(LLM_QUALITY, messages, json_mode=True, max_tokens=3000)
    try:
        return json.loads(raw).get("questoes", [])
    except Exception:
        return []


# ── Follow-up question suggestions ───────────────────────────────────────────

def suggest_followups(question: str, answer: str) -> list[str]:
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"Com base nesta pergunta e resposta médica, sugere exactamente 3 perguntas de "
            f"follow-up que um estudante de medicina poderia querer aprofundar.\n"
            f"Formato JSON: {{\"perguntas\": [\"pergunta 1\", \"pergunta 2\", \"pergunta 3\"]}}\n\n"
            f"PERGUNTA: {question}\n"
            f"RESPOSTA (resumo): {answer[:600]}"
        )},
    ]
    raw = _chat(LLM_FAST, messages, json_mode=True, max_tokens=300)
    try:
        return json.loads(raw).get("perguntas", [])
    except Exception:
        return []


# ── HyDE — Hypothetical Document Embedding ────────────────────────────────────

def hypothetical_answer(question: str, topic: str | None = None) -> str:
    """
    Generate a short hypothetical textbook passage that would answer the question.
    Embedding this instead of the raw question puts the query vector in 'answer space',
    which is much closer to stored chunk embeddings (textbook language).
    Returns empty string on failure so the caller can fall back to the raw question.
    """
    topic_hint = f" no contexto de {topic}" if topic else ""
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"Escreve 2-3 frases de um manual médico{topic_hint} que responderia directamente "
            f"a esta pergunta. Usa linguagem técnica de textbook, sem introdução.\n\n"
            f"PERGUNTA: {question}"
        )},
    ]
    try:
        return _chat(LLM_FAST, messages, max_tokens=200)
    except Exception:
        return ""


# ── Topic extraction ──────────────────────────────────────────────────────────

def extract_topics(sample_text: str) -> list[str]:
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"Analisa o texto abaixo e extrai entre 10 e 15 TÓPICOS PRINCIPAIS de alto nível "
            f"(como capítulos ou entradas de índice de um livro médico).\n"
            f"IMPORTANTE: extrai temas amplos (ex: 'Epilepsia', 'Doença de Parkinson', 'Acidente Vascular Cerebral'), "
            f"NÃO sub-detalhes clínicos específicos.\n"
            f"Formato JSON: {{\"topicos\": [\"tópico 1\", \"tópico 2\", ...]}}\n\n"
            f"TEXTO:\n{sample_text[:3000]}"
        )},
    ]
    raw = _chat(LLM_FAST, messages, json_mode=True, max_tokens=500)
    try:
        return json.loads(raw).get("topicos", [])
    except Exception:
        return []


# ── Document summary ──────────────────────────────────────────────────────────

def generate_summary(sample_text: str, topics: list[str] | None = None) -> str:
    topics_hint = (
        f"Os capítulos/temas deste documento incluem: {', '.join(topics)}.\n\n"
        if topics else ""
    )
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": (
            f"Analisa o texto médico abaixo e cria um resumo estruturado em português de Portugal.\n"
            f"{topics_hint}"
            f"Segue EXACTAMENTE este formato (três secções, nada mais):\n\n"
            f"**Introdução:**\n"
            f"Escreve 2-3 frases que expliquem o PROPÓSITO e ÂMBITO do documento: "
            f"o que é (ex: manual clínico, apontamentos de aula, guia prático), "
            f"para quem se destina (ex: estudantes de medicina, internos) e "
            f"que área médica abrange. NÃO enumeres os tópicos — descreve o documento como um todo.\n\n"
            f"**Pontos-chave:**\n"
            f"Lista 6-10 bullet points com os CONCEITOS E PRINCÍPIOS mais importantes. "
            f"Cada bullet deve ser uma frase útil que transmita um conceito (ex: «A distinção entre NMS e NMI "
            f"é essencial para localizar a lesão neurológica»), NÃO apenas um nome de tópico.\n\n"
            f"**Pérolas Clínicas:**\n"
            f"Lista 3-5 bullet points com factos práticos concretos, valores específicos ou "
            f"regras clínicas que um estudante deve memorizar (ex: critérios, doses, sinais patognomónicos).\n\n"
            f"TEXTO:\n{sample_text[:8000]}"
        )},
    ]
    try:
        return _chat(LLM_QUALITY, messages, max_tokens=1200)
    except Exception as e:
        return ""  # Caller will skip saving on empty string


# ── Image captioning (vision) ─────────────────────────────────────────────────

def caption_image(b64_data: str, ext: str) -> str:
    try:
        resp = _client().chat.completions.create(
            model=LLM_VISION,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{ext};base64,{b64_data}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Descreve esta imagem médica em português de Portugal. "
                            "Sê específico sobre estruturas anatómicas, gráficos, "
                            "tabelas ou esquemas visíveis. Máximo 2 frases."
                        ),
                    },
                ],
            }],
            max_tokens=150,
            temperature=0.1,
        )
        return resp.choices[0].message.content or ""
    except Exception:
        return ""
