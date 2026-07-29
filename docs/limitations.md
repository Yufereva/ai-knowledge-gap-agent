# Limitations & Human-in-the-Loop Boundary

## What this prototype does

- Clusters recurring documentation-type support questions using sentence
  embeddings (semantic similarity), not keyword matching.
- Compares each recurring theme against a knowledge base and classifies
  coverage as good, weak, or missing based on the closest matching article.
- Drafts a content brief recommendation for any theme that is not well
  covered, citing the exact evidence tickets behind it.
- Optionally uses a local Ollama model to turn the brief into a fuller
  customer-facing article draft.
- Lets a reviewer publish an approved draft to a local demo knowledge base
  page, then edit or unpublish that local copy.

## What this prototype does not do

- It does not touch any real documentation system. The **Publish to knowledge
  base** action writes to a local demo help-center page inside this app
  (`data/runtime/published_articles.json`); **Edit** and **Unpublish** only
  change that local copy. Nothing is sent to a real help center.
- A generated article can contain unsupported product details even when the
  prompt asks the model not to invent them. UI labels, procedures, limits,
  and policy must be verified by a product or content owner.
- It does not know whether an article is factually correct, only whether it
  is semantically close to the recurring question.
- It does not distinguish "the answer is missing" from "the answer exists in
  a format the model doesn't recognize" (e.g. a screenshot-only article).
- The "documentation gap vs. product defect" split relies on ticket type
  (`question`/`how-to` vs. `bug`/`complaint`). In a real deployment this
  would come from the helpdesk's own ticket categorization, and
  misclassified tickets on the support side would propagate here.
- Clustering is a simple greedy similarity threshold, not a tuned production
  clustering algorithm. On the bundled synthetic dataset it correctly
  separates all nine documentation themes, with two tickets landing in an
  adjacent theme due to overlapping vocabulary (see `tests/test_knowledge_gap.py`
  for what is verified).
- Thresholds (`CLUSTER_THRESHOLD`, `GOOD_COVERAGE_THRESHOLD`,
  `WEAK_COVERAGE_THRESHOLD` in `knowledge_gap.py`) were calibrated by hand
  against this synthetic dataset and the `all-MiniLM-L6-v2` embedding model.
  They are not validated against real support or KB data.

## Human-in-the-loop

Every ranked gap includes the evidence tickets that produced it. The content
brief is a draft recommendation for a content owner to accept, edit, or
reject. Ollama output is also labeled "review required" and remains local;
the agent never assumes the generated article is correct. Publishing is never
automatic: a reviewer must click **Publish to knowledge base**, and even then
the article only lands on this app's local demo help-center page.
