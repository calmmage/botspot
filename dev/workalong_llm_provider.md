# LLM Provider Implementation - 2025-03-17

## Task (COMPLETED)

Implement the LLM Provider component in botspot with the following features:

- ✅ Basic query_llm function (prompt -> text response)
- ✅ Async version (aquery_llm)
- ✅ Similar interface to calmlib: query_llm_base, query_llm_str, query_llm_raw,
  query_llm_structured
- ✅ Use litellm as backend
- ✅ Support model name shortcuts (e.g., claude-3.7 -> proper litellm keys)

## Implementation Plan (COMPLETED)

1. ✅ Define the model name mapping for shortcuts
2. ✅ Implement the base LLMProvider class with required methods
3. ✅ Create the query functions with appropriate interfaces
4. ✅ Add async equivalents
5. ✅ Implement proper initialization and dependency management

## Implementation Details

1. Created a comprehensive LLM Provider component that:
    - Uses litellm for multi-provider support
    - Supports shortcuts for model names (claude-3.7, gpt-4o, etc.)
    - Provides both synchronous and asynchronous interfaces
    - Offers structured output with Pydantic models
    - Includes streaming capabilities

2. Integrated the LLM Provider into the botspot dependency system:
    - Added to dependency manager
    - Added to botspot settings
    - Added proper initialization in bot_manager

3. Created an example bot (examples/components_examples/llm_provider_demo) that
   demonstrates:
    - Basic text generation
    - Structured output
    - Streaming responses

4. Updated documentation and environment settings

## Future Improvements

- Add more advanced features like vision models support
- Add more usage examples and documentation
- Consider adding rate limiting and quotas
- Add custom providers beyond what litellm offers

## References Used

- calmlib/utils/llm_utils/gpt_utils.py - For interface design
- register-146-meetup-2025-bot/app/routers/admin.py - For litellm usage example

## LLM Provider Enhancements - 2025-03-17

1. Add user_id as optional arg to query llm methods
2. If in single_user_mode, assume user_id is our user; if not provided and not in
   single_user_mode, raise exception
3. Check botspot admins list and botspot friends list
4. Use compare_users util from user_ops.py
5. Add flag
   `allow_everyone: bool = False  # If False, only friends and admins can use LLM features`
   to LLMProviderSettings
6. If flag not enabled, check if user is friend or admin; if not, send_safe a message
   that they're not allowed but can ask to be added as friend
7. Track per-user usage stats in MongoDB if enabled, otherwise in memory
8. Add admin-only command to view usage statistics