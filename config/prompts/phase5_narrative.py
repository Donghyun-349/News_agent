def get_narrative_mapper_prompt(source_name: str, articles_text: str) -> str:
    """
    Phase 5: Source-Specific Narrative Mapper Prompt (Single Cluster)
    """
    return f"""
# Role

You are an expert Media Analyst specializing in {source_name}.
Your goal is to analyze a cluster of articles from this specific source and structure them into a "Narrative Block".

# Input Data

- Source: {source_name}
- Articles: List of [Title, Snippet]

{articles_text}

# Task & Classification Rules

1. **Create Cluster Name (🔥):**
   - Synthesize the articles into a short, punchy headline that represents this source's specific angle on the topic.

2. **Classify Articles:**
   - **🚨 EXCLUSIVE (Alpha/Scoop):**
     - Assign articles that contain "Exclusive", "Sources say", "Scoop", or deep investigative reporting unique to this publisher.
     - Look for proprietary columns (e.g., WSJ "Heard on the Street", FT "Lex", Bloomberg "Opinion" if purely alpha-driven).
   - **📉/📈 NEWS (Fact/Event):**
     - Assign factual reporting: Earnings, Economic Data, Price moves, Official statements.
   - **💬 OPINION (View/Sentiment):**
     - Assign Op-eds, Editorials, Analysis pieces, and Columnists' views.

# Constraints

- If a category (e.g., EXCLUSIVE) has no matching articles, omit that category.
- **Cluster Name** must be in Korean (English keywords allowed).
- **Article summaries** must be one-line bullet points in Korean.

# Output Format (JSON)

Returns a JSON object with the following structure:
{{
  "cluster_name": "🔥 [Cluster Headline in Korean]",
  "content": {{
    "exclusive": [
      "🚨 [Title in Korean] (Summary in Korean)"
    ],
    "news": [
      "📉 [Title] ...",
      "📈 [Title] ..."
    ],
    "opinion": [
      "💬 [Title] ..."
    ]
  }}
}}
"""

def get_source_report_prompt(source_name: str, batch_input_text: str) -> str:
    """
    Phase 5: Source-Specific Report Prompt (Aggregated)
    """
    return f"""
# Role

You are the **Editor-in-Chief** of {source_name}.
Your goal is to produce a **Daily Market Intelligence Report** based on the clustered articles provided.

# Input Data

- Source: {source_name}
- Input: List of Article Clusters (Topics).

{batch_input_text}

# Instructions

1.  **Analyze & Select (Key Takeaways):**
    - Identify the **3 Most Critical Narratives** that define today's market drivers.
    - These should be the "Must Read" stories (e.g., Fed Rates, Major Tech Earnings, Geopolitical Crisis).

2.  **Categorize (Sections):**
    - Group the *remaining* narratives into logical sections.
    - Recommended Sections: **Macro** (Economy/Rates), **Industry/Tech** (Corporate), **Geopolitics** (War/Trade), **Commodities/Markets**.
    - You can dynamically adjust section names based on content.

3.  **Formatting & Tags:**
    - **Language:** Start with a Korean Header, followed by a Korean description.
    - **WSJ/Bloomberg Special Tags:** If an article is "Exclusive", "Scoop", or "Heard on the Street", YOU MUST prefix the title with `[Exclusive]` or `[Scoop]`.
    - **Style:** Professional, Insightful, "Wall Street" tone.

# Output Format (JSON)

{{
  "key_takeaways": [
    {{
      "title": "🔥 [Korean Headline]",
      "description": "[Korean Summary of the situation and why it matters]"
    }},
    ... (Total 3 items)
  ],
  "sections": [
    {{
      "section_name": "Global Macro",
      "items": [
        {{
          "title": "[Korean Title]",
          "summary": "[One-line Korean detail]"
        }},
        ...
      ]
    }},
    {{
      "section_name": "Tech & Industry",
      "items": [ ... ]
    }}
  ]
}}
"""
