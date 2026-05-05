# Script Notes

This document keeps a slightly more detailed view of important scripts so that the homepage README can stay short and easy to scan.

## Core Pipelines
| Script | Purpose | Notes |
|---|---|---|
| `run_pipeline.py` | Unified entrypoint for dry-run checks and major module launches | Supports `check`, `rag`, `reference`, and `idea` subcommands |
| `Review_db/main_review.py` | End-to-end review-database construction | Runs section split, chunk split, statement extraction, theme extraction, and database build |
| `Reference/scripts/ref_main.py` | Reference fetching and consolidation pipeline | Uses `Reference/scripts/config.yaml` |
| `ref_db_match/script/ra_main.py` | Reference index to DOI/metadata matching pipeline | Uses `ref_db_match/script/config.yaml` |
| `RAG/rag_core/main.py` | Main retrieval pipeline | Uses configured review/reference spreadsheets and retrieval artifacts |

## Retrieval Utilities
| Script | Purpose | Typical outputs |
|---|---|---|
| `RAG/rag_core/embedding.py` | Generate embedding columns for selected fields | JSONL and Excel with `*_embedding` columns |
| `RAG/rag_core/BM25_con.py` | Build BM25 models for chunk/theme retrieval | `bm25_chunk.pkl`, `bm25_theme.pkl` |
| `RAG/rag_core/faiss_con.py` | Build FAISS indexes for review embeddings | `*_faiss.index`, `*_mapping.csv` |
| `RAG/rag_core/ref_BM25.py` | Build BM25 model for abstract retrieval | `ref_bm25_model.pkl` |
| `RAG/rag_core/ref_FAISS.py` | Build FAISS index for abstract embeddings | `abstract_embedding_faiss.index`, mapping CSV |

## Evaluation Scripts
| Script | Purpose | Required input |
|---|---|---|
| `RAG/evaluation/CHUNK_SEARCH.py` | Hybrid retrieval batch evaluation | Excel with a `query` column |
| `RAG/evaluation/chunk_only.py` | Chunk-only retrieval batch evaluation | Excel with a `query` column |
| `RAG/evaluation/theme_only.py` | Theme-only retrieval batch evaluation | Excel with a `query` column |

## Idea Workflow
| Script | Purpose | Typical outputs |
|---|---|---|
| `Reaearch_Idea/code/background.py` | Generate background text from retrieved review content | `background_<workspace>.txt` |
| `Reaearch_Idea/code/inspiration_generation.py` | Select and extract inspirations from abstracts | `inspirations_all.txt`, `inspirations_all.json` |
| `Reaearch_Idea/code/hypothesis_generation.py` | Generate hypotheses from extracted inspirations | `combined_inspirations_hypothesis.txt`, `.json` |
| `Reaearch_Idea/code/novelty_evaluate.py` | Assess novelty and feasibility | `novelty_judgement_results_round*.json` |
| `Reaearch_Idea/code/idea_updata.py` | Generate next-round updated ideas | `update_ideas*.json` |
