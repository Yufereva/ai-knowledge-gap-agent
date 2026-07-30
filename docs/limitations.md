# Limitations & Human-in-the-Loop Boundary

## What this prototype does

- Clusters recurring documentation-type support questions using sentence
  embeddings (semantic similarity), not keyword matching.
- Compares each recurring theme against a knowledge base and classifies
  coverage as good, weak, or missing based on the closest matching article.
- Validates each proposed outline before a content owner sees it: maps sections
  to supporting tickets, checks volume across accounts and time, classifies what
  kind of gap it is, compares against existing articles, reports which raised
  concepts the outline omits, and looks for articles that contradict the
  evidence.
- Drafts a content brief recommendation for any theme that survives validation,
  citing the exact evidence tickets behind it.
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

## What the validation pipeline can and cannot decide

- The "poor findability" and "agent retrieval failure" classes depend on the
  synthetic `searched` and `search_top_article` fields on each ticket. A real
  deployment would need help center search analytics or agent retrieval logs,
  and those signals are usually incomplete.
- The unique-customer rule depends on the synthetic `customer_id`. Ticket volume
  from one account is not the same finding as volume across accounts, so without
  account data this rule cannot run.
- The support threshold in the spec allows a high customer impact override. The
  synthetic dataset carries no impact or revenue signal, so `high_impact`
  defaults to false and the time-span rule decides instead.
- Outline completeness is detected with explicit phrase lists
  (`validators/completeness_validator.py`). It can miss a paraphrase, and it
  deliberately does not block review: an outline written as customer questions
  legitimately lacks procedural wording, so blocking there would reject real
  gaps. Missing concepts are reported as sections to add.
- Contradiction detection is one deterministic rule family paired with product
  version data, not general purpose entailment. It catches an article that
  claims automatic behavior while customers on a newer version report manual
  work, and it will miss other kinds of conflict.
- Confidence is a weighted blend of three signals with fixed weights, reported
  in `validators/validation_report.py`. It is a ranking aid, not a probability.
- The pipeline judges whether evidence supports documentation work. It cannot
  judge whether the resulting article would be factually correct.

## Human-in-the-loop

Every ranked gap includes the evidence tickets that produced it, and every theme
carries a validation verdict with the reasons behind it. A theme whose evidence
does not justify documentation work does not get a draft at all: it gets a
different recommendation, such as improving search metadata or asking an SME.
The content brief is a draft recommendation for a content owner to accept, edit,
or reject. Ollama output is also labeled "review required" and remains local;
the agent never assumes the generated article is correct. Publishing is never
automatic: a reviewer must click **Publish to knowledge base**, and even then
the article only lands on this app's local demo help-center page.
