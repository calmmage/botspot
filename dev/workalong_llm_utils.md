# LLM Utils - parse_input_into_form

## Task
"create a very basic implementation that can take input, data model, and return it parsed"

## Focus Areas
- "system prompt text"
- "how do we extract from pydantic schema info which fields are optional and which are not, and pass that to llm? Does litellm auto-extract that?"
- "Test with simple code: make a schema with optionals and generate with dummy irrelevant input"
- "how exactly we expect the llm to communicate us that info is not there?"
- "maybe we can ask llm to return back all unused text (e.g. 'from these sentences i extracted no info')"

## First step
Test if existing litellm functionality already differentiates between optional and required fields