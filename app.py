"""Milestone 5: minimal Gradio query UI over the full RAG pipeline.

    .venv/bin/python app.py   # then open the printed local URL
"""

from __future__ import annotations

import gradio as gr

import generation
import retrieval


def ask(query: str) -> tuple[str, str]:
    """Query -> (answer markdown, retrieved-chunks markdown)."""
    if not query or not query.strip():
        return "Ask a question first.", ""
    try:
        out = generation.generate_answer(query.strip())
    except Exception as e:  # surface API/auth problems instead of a blank toast
        return (
            f"**Generation failed:** `{type(e).__name__}` — check that "
            f"`GROQ_API_KEY` in `.env` is a real key (console.groq.com).",
            "",
        )

    answer_md = out["answer"]
    if out["sources"]:
        answer_md += "\n\n**Sources**\n" + generation.format_sources_md(out["sources"])

    chunks_md = "\n\n".join(
        f"**[{n}]** `{r['metadata']['post_id']}` — similarity {r['similarity']:.3f}\n\n"
        f"> {r['text'].replace(chr(10), chr(10) + '> ')}"
        for n, r in enumerate(out["results"], 1)
    )
    return answer_md, chunks_md


with gr.Blocks(title="The Unofficial Guide — r/SJSU CS courses & professors") as demo:
    gr.Markdown(
        "# The Unofficial Guide\n"
        "What SJSU students *actually* say about CS/SE courses and professors, "
        "answered only from collected r/SJSU threads — with sources. "
        "If the corpus doesn't cover it, the system says so instead of guessing."
    )
    query = gr.Textbox(
        label="Question",
        placeholder="e.g. Should I take CS 157A with Professor Ezzat?",
    )
    ask_btn = gr.Button("Ask", variant="primary")
    answer = gr.Markdown()
    with gr.Accordion("Retrieved excerpts (what the answer is grounded in)", open=False):
        chunks = gr.Markdown()
    gr.Examples(
        examples=[[q["question"]] for q in retrieval.EVAL_QUESTIONS],
        inputs=[query],
    )
    ask_btn.click(ask, inputs=query, outputs=[answer, chunks])
    query.submit(ask, inputs=query, outputs=[answer, chunks])


if __name__ == "__main__":
    demo.launch()
