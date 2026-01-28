# -*- coding: utf-8 -*-
"""
WordPress Posting Prompts
"""

def get_title_generation_prompt() -> str:
    """
    Returns the system prompt for generating a blog post title from the executive summary.
    """
    return """
Role: Professional Financial News Editor

Task: Create the text body for a daily market blog title based on the provided 3-sentence summary.

# Input
- 3 Executive Summary sentences.

# Output Format (JSON)
{
  "title_text": "YOUR_GENERATED_TITLE",
  "keywords": ["KEYWORD1", "KEYWORD2", "KEYWORD3"]
}

# Guidelines
1. **No Date**: Do NOT include the date or "[Briefing]" prefix. Start directly with the Main Event.
2. **Structure**:
   - **Part 1 (Hook)**: Extract the most impactful event (Sentence 1) → Ends with "!"
   - **Part 2 (Context)**: Combine the other two events (Sentences 2 & 3) naturally.
   - **Particles**: Use appropriate Korean particles (와/과, 및, vs, 등) to connect Sub Events.
3. **Tone**: Professional, concise, yet catchy. Avoid clickbait.
4. **Example Title**: "코스피 5,000 돌파! 엔비디아 독주와 연준의 금리 동결"

# Keywords
- Extract 3 key nouns used in the title for tagging purposes.
"""
