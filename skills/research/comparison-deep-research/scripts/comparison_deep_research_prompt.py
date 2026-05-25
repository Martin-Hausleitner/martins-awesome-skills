#!/usr/bin/env python3
"""Generate strict Deep Research prompts for product/tool comparisons."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_prompt(
    topic: str,
    use_case: str,
    candidate_count: int,
    minimum_candidates: int,
    language: str,
    market_depth: str = "standard",
    context_files: list[str] | None = None,
) -> str:
    candidate_count = max(candidate_count, minimum_candidates)
    context_files = context_files or []
    exhaustive = market_depth == "exhaustive"
    market_scope_en = (
        f"- Exhaust the market as far as reasonable: discover as many relevant candidates as can be verified, target at least {candidate_count}, include long-tail and adjacent-category options, then produce a ranked shortlist."
        if exhaustive
        else f"- Find and compare ideally {candidate_count} relevant candidates."
    )
    market_scope_de = (
        f"- Reize den Markt so weit wie sinnvoll aus: finde so viele relevante Kandidaten wie verifizierbar, Ziel mindestens {candidate_count}, inklusive Long-Tail- und angrenzender Kategorien, und erstelle danach eine gerankte Shortlist."
        if exhaustive
        else f"- Finde und vergleiche idealerweise {candidate_count} relevante Kandidaten."
    )
    context_section_en = build_context_section(context_files, language="en")
    context_section_de = build_context_section(context_files, language="de")
    if not language.lower().startswith("de"):
        return f"""Run a Deep Research task as a rigorous comparison scorecard.

Final report language: English.

Topic:
{topic}

Use case / decision goal:
{use_case}

Candidate scope:
{market_scope_en}
- If the market is smaller, compare at least {minimum_candidates} solid candidates.
- Candidates can be products, GitHub repositories, packages, frameworks, guides, plugins, platforms, or commercial tools.
- Name important excluded candidates with a short reason.
{context_section_en}

Hard output requirements:
1. Start with an Executive Verdict Box:
   - Overall winner
   - Top 3
   - Best budget/self-hosted/open-source/production choice, where relevant
   - When the winner is NOT the best choice

2. Create a large comparison table.
   Required columns:
   - Rank
   - Candidate: Markdown link to official website or docs
   - GitHub: Markdown link to the repository if available, otherwise "N/A" plus reason
   - Website/Docs: Markdown link to official website or documentation
   - Type
   - License / Pricing
   - Last Activity / Release Freshness
   - Category 1 Score
   - Category 2 Score
   - Category 3 Score
   - Category 4 Score
   - Category 5 Score
   - Total /100
   - Best For
   - Key Caveat

3. If market depth is exhaustive, add a Market Map before the scorecard:
   - Discovery queries and source types used
   - Longlist count
   - Shortlist criteria
   - Excluded-but-notable candidates
   - Gaps where the market appears sparse or unverifiable

4. Define exactly five major scoring categories tailored to the use case.
   Rules:
   - The five categories must sum to exactly 100 points.
   - Each category needs 3-6 subcriteria.
   - Every candidate score must be justified.
   - The total score must be the weighted sum of the categories.
   - Do not use decorative categories; each one must matter for the decision.

5. Verify links and evidence.
   - Do not guess GitHub URLs.
   - Check GitHub stars, license, releases/commits/last activity, and maintainer signals when a repository exists.
   - Check official website, docs, pricing, security/privacy, and changelog/roadmap when a product exists.
   - If something cannot be verified, write "Unverified" and reduce confidence/score.

6. Include at least one Mermaid diagram.
   Choose what fits best:
   - Decision tree for "which tool should I pick?"
   - Architecture/adoption flow
   - Quadrant diagram as a text/Mermaid approximation

7. Add a "Best by Scenario" table:
   - Best overall
   - Best for MVP
   - Best for production
   - Best open-source/self-hosted
   - Best managed/commercial
   - Best privacy/security
   - Best developer experience
   - Best team workflow

8. Add detailed candidate notes.
   For each candidate:
   - Short description
   - Important links
   - Why the scores were assigned
   - Risks and integration effort
   - Concrete recommendation: adopt / pilot / watch / avoid

9. Close with a concrete implementation plan:
   - MVP in 1-2 weeks
   - Production hardening
   - Risks
   - Cost model
   - Next tests or proofs of concept

Quality bar:
- No generic tables without sources.
- No invented GitHub links.
- Do not count candidates twice.
- If fewer than {minimum_candidates} candidates make sense, explain why.
- Prioritize current, active, well-documented solutions.
- Use clear, comparable scores, not only prose.
- Use attached files as supporting context, but verify public facts independently when possible.
"""

    lang_instruction = "German"
    return f"""Führe ein Deep Research im Format einer belastbaren Vergleichs-Scorecard durch.

Sprache des finalen Reports: {lang_instruction}.

Thema:
{topic}

Use Case / Entscheidungsziel:
{use_case}

Kandidatenumfang:
{market_scope_de}
- Wenn der Markt kleiner ist, vergleiche mindestens {minimum_candidates} belastbare Kandidaten.
- Kandidaten können Produkte, GitHub-Repositories, Packages, Frameworks, Guides, Plugins, Plattformen oder kommerzielle Tools sein.
- Nenne wichtige ausgeschlossene Kandidaten mit kurzem Grund.
{context_section_de}

Harte Ausgabeanforderungen:
1. Starte mit einer Executive Verdict Box:
   - Gesamtsieger
   - Top 3
   - Best budget/self-hosted/open-source/production choice, falls passend
   - Wann der Sieger NICHT die beste Wahl ist

2. Erstelle eine große Vergleichstabelle.
   Pflichtspalten:
   - Rank
   - Candidate: Markdown-Link auf offizielle Website oder Docs
   - GitHub: Markdown-Link auf das Repository, falls vorhanden, sonst "N/A" plus Grund
   - Website/Docs: Markdown-Link auf offizielle Website oder Dokumentation
   - Type
   - License / Pricing
   - Last Activity / Release Freshness
   - Category 1 Score
   - Category 2 Score
   - Category 3 Score
   - Category 4 Score
   - Category 5 Score
   - Total /100
   - Best For
   - Key Caveat

3. Wenn Market Depth auf exhaustive steht, füge vor der Scorecard eine Market Map ein:
   - Genutzte Discovery-Queries und Quellentypen
   - Anzahl der gefundenen Longlist-Kandidaten
   - Shortlist-Kriterien
   - Ausgeschlossene, aber relevante Kandidaten
   - Lücken, in denen der Markt dünn oder nicht verifizierbar wirkt

4. Definiere genau fünf große Bewertungskategorien, angepasst an den Use Case.
   Regeln:
   - Die fünf Kategorien müssen zusammen exakt 100 Punkte ergeben.
   - Jede Kategorie braucht 3-6 Subkriterien.
   - Jede Kandidatenbewertung muss begründet sein.
   - Der Total Score muss die gewichtete Summe der Kategorien sein.
   - Verwende keine Kategorie, die nur dekorativ ist; jede muss für die Entscheidung wichtig sein.

5. Verifiziere Links und Evidenz.
   - GitHub-URLs dürfen nicht geraten werden.
   - Prüfe GitHub-Sterne, Lizenz, Releases/Commits/Last Activity und Maintainer-Signale, wenn es ein Repo gibt.
   - Prüfe offizielle Website, Docs, Pricing, Security/Privacy und Changelog/Roadmap, wenn es ein Produkt gibt.
   - Wenn etwas nicht verifizierbar ist, schreibe "Unverified" und reduziere Confidence/Score.

6. Baue mindestens ein Mermaid-Diagramm ein.
   Wähle passend:
   - Entscheidungsbaum für "welches Tool soll ich nehmen?"
   - Architektur-/Adoptionsflow
   - Quadrant-Diagramm als Text/Mermaid-Annäherung

7. Füge eine "Best by Scenario" Tabelle ein:
   - Best overall
   - Best for MVP
   - Best for production
   - Best open-source/self-hosted
   - Best managed/commercial
   - Best privacy/security
   - Best developer experience
   - Best team workflow

8. Füge detaillierte Kandidatennotizen hinzu.
   Pro Kandidat:
   - Kurzbeschreibung
   - Wichtige Links
   - Warum die Scores so vergeben wurden
   - Risiken und Integrationsaufwand
   - Konkrete Empfehlung: adopt / pilot / watch / avoid

9. Schließe mit einem konkreten Umsetzungsplan:
   - MVP in 1-2 Wochen
   - Production-Hardening
   - Risiken
   - Kostenmodell
   - Nächste Tests oder Proof-of-Concepts

Qualitätslatte:
- Keine generischen Tabellen ohne Quellen.
- Keine erfundenen GitHub-Links.
- Keine Kandidaten doppelt zählen.
- Wenn weniger als {minimum_candidates} Kandidaten sinnvoll sind, erkläre warum.
- Priorisiere aktuelle, aktive, gut dokumentierte Lösungen.
- Verwende klare, vergleichbare Scores, nicht nur Fließtext.
- Nutze angehängte Dateien als Kontext, verifiziere öffentliche Fakten aber nach Möglichkeit unabhängig.
"""


def build_context_section(context_files: list[str], *, language: str) -> str:
    if not context_files:
        if language == "en":
            return """Context handling:
- Keep the prompt compact. Use uploaded files, source lists, or notes for large context instead of pasting long text."""
        return """Kontextverarbeitung:
- Halte den Prompt kompakt. Nutze hochgeladene Dateien, Quellenlisten oder Notizen für großen Kontext statt lange Texte einzufügen."""

    bullet_lines = "\n".join(f"  - {Path(file).name}" for file in context_files)
    if language == "en":
        return f"""Attached context files:
{bullet_lines}

Use these files as a context package:
- Extract user preferences, known candidates, constraints, scoring hints, and must-check links from the files.
- Treat files as supporting context, not as automatically verified truth.
- If a file conflicts with current public sources, mention the conflict and prefer current verified sources."""

    return f"""Angehängte Kontextdateien:
{bullet_lines}

Nutze diese Dateien als Kontextpaket:
- Extrahiere User-Präferenzen, bekannte Kandidaten, Constraints, Scoring-Hinweise und Pflichtlinks aus den Dateien.
- Behandle Dateien als unterstützenden Kontext, nicht automatisch als verifizierte Wahrheit.
- Wenn eine Datei aktuellen öffentlichen Quellen widerspricht, erwähne den Konflikt und bevorzuge aktuelle verifizierte Quellen."""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", required=True, help="Comparison topic or product category.")
    parser.add_argument("--use-case", default="Find the best overall option for the user's stated workflow.")
    parser.add_argument("--candidate-count", type=int, default=50)
    parser.add_argument("--minimum-candidates", type=int, default=10)
    parser.add_argument("--language", default="de", choices=["de", "en"])
    parser.add_argument("--market-depth", default="standard", choices=["standard", "exhaustive"])
    parser.add_argument("--context-file", action="append", default=[], help="Context file that will be attached to the Deep Research run.")
    parser.add_argument("--output", help="Write prompt to this file instead of stdout.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv or sys.argv[1:]))
    prompt = build_prompt(
        topic=args.topic,
        use_case=args.use_case,
        candidate_count=args.candidate_count,
        minimum_candidates=args.minimum_candidates,
        language=args.language,
        market_depth=args.market_depth,
        context_files=args.context_file,
    )
    if args.output:
        Path(args.output).write_text(prompt, encoding="utf-8")
    else:
        sys.stdout.write(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
