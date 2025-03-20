# LLM Utils Planning - 2025-03-18

## Current State Analysis

The botspot LLM Provider component (`llm_provider.py`) currently offers these utilities:

- Core query functions: `query_llm`, `aquery_llm`
- Structured output: `query_llm_structured`, `aquery_llm_structured`
- Streaming: `query_llm_stream`, `astream_llm`
- Usage tracking and permissions

From calmlib, we've identified these additional utilities:

- `query_llm_structured_stream`, `aquery_llm_structured_stream` (streaming structured
  output)
- Langfuse integration support

## Implementation Plan

### Architecture Decision

- Keep the LLM Provider component focused on core query functionality
- Add simple utility functions in `botspot/utils/llm_utils.py` (no classes/settings)
- Add Langfuse tracing in LLM Provider settings

### Implementation Priorities

1. **Media Processing**
    - Process images with vision models
    - Handle file uploads from Telegram
    - Extract text from images if needed

2. **Smart Form Handling**
    - Fill Pydantic models from user text
    - Validate and identify missing fields
    - Re-ask for missing required information

3. **Message Parsing**
    - Extract entities (contacts, dates, links)
    - Parse unified format for chat messages
    - Process forwarded message batches

4. **Validation & Quality**
    - Check text against guidelines
    - Verify naming patterns or content quality
    - Offer suggestions for improvements

5. **Langfuse Integration**
    - Add tracing to LLM Provider settings
    - Track prompts, completions, and tokens
    - Calculate costs and usage patterns

## Usage Examples

```python
# Example: Image processing
image_description = await process_image_for_llm(image_data)

# Example: Form filling
user_data, missing_fields = await smart_form_fill(UserSchema, message_text)

# Example: Text validation
validation = await validate_text(article, guidelines)

# Example: Entity extraction
entities = await extract_entities_from_message(message, ["email", "phone"])
```

## Future Considerations

- Multi-user chat context management
- Self-aware command assistant (with command registry)
- Integration with context builder for richer prompts
- Specialized prompt templates library