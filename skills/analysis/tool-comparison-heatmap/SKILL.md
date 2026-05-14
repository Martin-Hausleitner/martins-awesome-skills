---
name: tool-comparison-heatmap
description: "Create interactive feature-comparison heatmaps that score, rank, and crown winners across multiple tools, repos, or products. Use this skill whenever the user asks to compare tools, software, GitHub repos, frameworks, extensions, or any set of alternatives across multiple features or criteria — especially when they want a visual matrix, heatmap, scorecard, ranking, or 'who wins' analysis. Also trigger when the user says things like 'compare features', 'which is the best', 'feature matrix', 'score them 1-100', 'rank these tools', 'Vergleich', 'Heatmap', 'wer gewinnt', or 'Gewinner küren'. The output is always an interactive React (.jsx) artifact with clickable GitHub/repo links, last-update dates, color-coded scores, sorting, and an automatic winner badge."
---

# Tool Comparison Heatmap Skill

Create a polished, interactive React heatmap that compares tools/repos across user-defined features, scores each 0–100, links to repositories, shows last-update dates, and automatically crowns the winner(s).

## When to Use

- User wants to compare multiple tools, repos, frameworks, extensions, or products
- User asks for a feature matrix, heatmap, scorecard, or ranking
- User wants to know "which is the best" across several criteria
- User mentions "Gewinner küren", "wer gewinnt", "score them", "rank", "compare features"

## Research Phase

Before building the heatmap, gather accurate data:

1. Identify the tools the user wants to compare (aim for 5–30)
2. Define feature categories — ask the user or derive from context. Typical categories:
 - Technical capabilities (e.g., multi-tab, parallel agents, self-healing)
 - Ecosystem (e.g., BYOK, open source, MCP support, Chrome extension)
 - Usability (e.g., no-code, voice, memory/persistence)
 - Trust (e.g., privacy, license, community size)
3. Research each tool using web search:
 - GitHub URL (exact, verified)
 - GitHub stars (current count)
 - Last meaningful update date (check releases page or recent commits)
 - Feature support level per category
4. Score each feature 0–100 based on research:
 - 85–100: Excellent / native support / best-in-class
 - 65–84: Good / solid support with minor gaps
 - 45–64: Partial / workaround needed / experimental
 - 25–44: Weak / very limited
 - 0–24: Missing / not applicable

## Output Requirements

Generate a single .jsx React artifact with ALL of the following:

### 1. Data Structure

```jsx
const tools = [
 {
 name: "Tool Name",
 github: "https://github.com/org/repo", // MUST be a real, verified URL
 stars: "~12.6k", // Current star count
 lastUpdate: "Apr 2026", // Last significant update
 type: "Chrome Extension / Framework / etc.",
 // Feature scores (0-100):
 feature1: 85,
 feature2: 40,
 // ... one key per feature
 // Notes per feature (optional, shown on click):
 notes: {
 feature1: "Detailed explanation of why this score...",
 },
 },
 // ... more tools
];

const features = [
 { key: "feature1", label: "Display Name", desc: "Tooltip description" },
 // ... more features
];
```

### 2. Interactive Table

- Sticky first column with tool name, type, stars, and last-update date
- Tool name is a clickable link → opens the GitHub repo in a new tab (`target="_blank"`)
- Last update shown as subtle text below the name (e.g., "Letztes Update: Apr 2026")
- Stars shown as `⭐ ~12.6k`
- Color-coded score cells: green (85+), teal (65-84), amber (45-64), red (0-44)
- Sortable columns: click any header to sort ascending/descending
- Click any cell → shows detail panel below with the note/explanation

### 3. Winner Badge

- Calculate average score (`total`) across all features for each tool
- Display a 🏆 trophy column or winner row at the top
- The tool with the highest average gets a visible `🏆 Gewinner` badge
- If user asked for category winners, also show per-feature winners

### 4. Styling

- Use CSS variables for theming (works in light/dark mode)
- Font: import a distinctive Google Font (e.g., DM Sans, Plus Jakarta Sans)
- Monospace font for scores (e.g., JetBrains Mono)
- Alternating row backgrounds for readability
- Responsive horizontal scroll for many columns
- Frosted/blurred detail panel on cell click

### 5. Winner Summary Box

Below the table, add a colored summary box:
- `🏆 Gesamtsieger: [Tool Name] mit Ø [Score]/100`
- List top 3 tools with their average scores
- Per-category leaders: `Bester bei [Feature]: [Tool] ([Score])`
- If the user's question had a specific focus (e.g., `wer kann parallele Tab-Gruppen`), highlight that category winner prominently

## Template Code Structure

```jsx
import { useState } from "react";

// 1. Data: tools[] and features[]
// 2. Calculate totals and winners
// 3. Render:
// - Header with title
// - Legend (color scale)
// - Sortable table with sticky column
// - Detail panel (on cell click)
// - Winner summary box

export default function ToolComparisonHeatmap() {
 const [sortKey, setSortKey] = useState("total");
 const [sortDir, setSortDir] = useState(-1);
 const [selected, setSelected] = useState(null);

 // ... sorting logic
 // ... render table with ScoreCell components
 // ... winner calculation and display
}
```

## Critical Rules

1. Every GitHub link must be verified — search the web to confirm the URL exists. Never guess.
2. Last update date must be researched — check the repo's releases or commit history.
3. Stars must be current — use web search to find the latest count.
4. Tool names must be clickable links — use `<a href={tool.github} target="_blank" rel="noopener noreferrer">`.
5. Winner must be automatically calculated — not hardcoded.
6. The artifact must be a single `.jsx` file — no separate CSS files.
7. All text in the user's language — if user speaks German, labels/descriptions in German.

## Example Invocations

- `Vergleiche die 10 besten Browser-Extensions mit einer Heatmap`
- `Score these 5 AI coding tools across speed, accuracy, and cost`
- `Wer gewinnt bei Multi-Tab-Steuerung? Mach eine Vergleichstabelle`
- `Create a feature matrix of React state management libraries`
- `Rank these databases 1-100 on performance, scalability, and ease of use`
