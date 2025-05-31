"""LLM Utilities for Botspot
   2
This module provides utility functions for working with LLMs in Botspot.
It complements the LLM Provider component with higher-level functions.
"""
import json
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union

from aiogram.types import Document, Message, PhotoSize
from pydantic import BaseModel, ValidationError

from botspot.components.new.llm_provider import aquery_llm, aquery_llm_structured
from botspot.utils.internal import get_logger
from botspot.utils.user_ops import UserLike

logger = get_logger()

# Type variable for Pydantic models
T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------
# region Media Processing
# ---------------------------------------------

# todo: nonono, this is
async def process_image_for_llm(
        photo: Union[PhotoSize, List[PhotoSize], Document, str, bytes],
        *,
        prompt: Optional[str] = None,
        user: Optional[UserLike] = None,
        model: str = "claude-3.7",
) -> str:
    """
    Process an image with a vision-capable LLM and return the description.

    Args:
        photo: Image data, can be PhotoSize object, Document, file_id string, or raw bytes
        prompt: Optional prompt to guide the image analysis (defaults to generic descriptio
        user: User identifier for permissions and tracking
        model: Model to use (must support vision capabilities)

    Returns:
        Text description of the image from the LLM
    """
    raise NotImplemented("This is garbage - redo. This is not what I meant")
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    bot = deps.bot

    # Default prompt if none provided
    if prompt is None:
        prompt = "Describe this image in detail."

    # Process different input types
    file_id = None
    image_bytes = None

    if isinstance(photo, list) and photo:
        # PhotoSize list, get the largest one
        photo = sorted(photo, key=lambda p: p.width * p.height, reverse=True)[0]
        file_id = photo.file_id
    elif isinstance(photo, PhotoSize):
        # Single PhotoSize
        file_id = photo.file_id
    elif isinstance(photo, Document) and photo.mime_type and photo.mime_type.startswith("image/"):
        # Document that's an image
        file_id = photo.file_id
    elif isinstance(photo, str):
        # Assume it's a file_id
        file_id = photo
    elif isinstance(photo, bytes):
        # Raw image bytes
        image_bytes = photo
    else:
        raise ValueError("Unsupported photo type")

    # Get file data if we have a file_id
    if file_id:
        try:
            file = await bot.get_file(file_id)
            file_path = file.file_path
            image_bytes = await bot.download_file(file_path)
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            raise

    # Call vision model
    try:
        provider = deps.llm_provider

        # Add image to messages
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image", "image_bytes": {"data": image_bytes}}
            ]}
        ]

        # Call LLM with vision capabilities
        response = await provider.aquery_llm_raw(
            prompt="",  # Empty because we provide messages directly
            user=user,
            model=model,
            messages=messages,  # type: ignore
        )

        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error processing image with LLM: {e}")
        raise


async def extract_text_from_image(
        photo: Union[PhotoSize, List[PhotoSize], Document, str, bytes],
        *,
        user: Optional[UserLike] = None,
        model: str = "claude-3.7",
    ) -> str:
    """
    Extract text from an image using a vision-capable LLM.

    Args:
        photo: Image data, can be PhotoSize object, Document, file_id string, or raw bytes
        user: User identifier for permissions and tracking
        model: Model to use (must support vision capabilities)

    Returns:
        Extracted text from the image
    """
    prompt = (
        "This image may contain text. Please extract and transcribe ALL text "
        "visible in the image. Maintain the original formatting as much as possible. "
        "If there are multiple sections, preserve the structure. If there is no text "
        "in the image, just say 'No text detected in the image.'"
    )

    return await process_image_for_llm(photo, prompt=prompt, user=user, model=model)


# ---------------------------------------------
# endregion Media Processing
# ---------------------------------------------


# ---------------------------------------------
# region Smart Form Handling
# ---------------------------------------------

async def smart_form_fill(
        model_class: Type[T],
        user_text: str,
        *,
        user: Optional[UserLike] = None,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
) -> Tuple[Optional[T], Dict[str, str]]:
    """
    Intelligently fill a Pydantic model from user text.

    Args:
        model_class: The Pydantic model class to fill
        user_text: The user text to extract information from
        user: User identifier for tracking and permissions
        system_message: Optional system message to guide extraction
        model: Optional LLM model to use

    Returns:
        Tuple of (filled model or None, dict of missing fields with explanations)
    """
    # Get model schema for field information
    model_schema = model_class.model_json_schema()
    required_fields = model_schema.get("required", [])
    properties = model_schema.get("properties", {})

    # Build extraction prompt
    base_prompt = f"""
Extract information from the user message to fill this form schema:
```json
{json.dumps(model_schema, indent=2)}
```

User message:
{user_text}

Only extract what's explicitly mentioned. For fields that aren't clearly provided, 
leave them null or empty. Return the filled form as a valid JSON object that matches 
the schema exactly.
"""

    # Build optional system message enhancement
    if system_message is None:
        system_message = (
            "You are a form extraction assistant. Your task is to accurately extract "
            "structured information from unstructured text. Be precise and don't invent "
            "information that isn't clearly stated in the user's message."
        )

    try:
        # Query LLM for structured output
        result = await aquery_llm_structured(
            prompt=base_prompt,
            output_schema=model_class,
            user=user,
            system_message=system_message,
            model=model,
        )

        # Check for missing required fields
        missing_fields = {}
        for field in required_fields:
            field_value = getattr(result, field, None)
            if field_value is None or (isinstance(field_value, str) and not field_value.strip()):
                field_info = properties.get(field, {})
            description = field_info.get("description", f"The {field} field")
            missing_fields[field] = description

            return result, missing_fields

    except ValidationError as e:
        logger.error(f"Validation error in smart_form_fill: {e}")
        # Extract information about what fields failed validation
        missing_fields = {}
        for error in e.errors():
            field = error["loc"][0] if error["loc"] else "unknown"
            missing_fields[field] = error["msg"]
        return None, missing_fields

    except Exception as e:
        logger.error(f"Error in smart_form_fill: {e}")
        return None, {"error": str(e)}


async def validate_form_completion(
        model_class: Type[T],
        partial_data: Dict[str, Any],
        *,
        user: Optional[UserLike] = None,
        model: Optional[str] = None,
) -> Dict[str, str]:
    """
    Validate partial form data and provide guidance on completing it.

    Args:
        model_class: The Pydantic model class to validate against
        partial_data: Dictionary of partially filled form data
        user: User identifier for tracking and permissions
        model: Optional LLM model to use

    Returns:
        Dictionary of field guidance with field names as keys and guidance as values
    """
    # Get model schema
    model_schema = model_class.model_json_schema()
    required_fields = model_schema.get("required", [])
    properties = model_schema.get("properties", {})

    # Check which required fields are missing
    missing_fields = []
    for field in required_fields:
        if field not in partial_data or partial_data[field] is None:
            missing_fields.append(field)

    if not missing_fields:
        return {}  # No missing required fields

    # Build prompt for LLM to generate guidance
    missing_field_details = "\n".join([
        f"- {field}: {properties.get(field, {}).get('description', '')}"
        for field in missing_fields
    ])

    prompt = f"""
I'm filling out a form and need help completing these missing required fields:

{missing_field_details}

Current form data:
```json
{json.dumps(partial_data, indent=2)}
```

For each missing field, provide:
1. A clear, conversational question to ask the user
2. What format the answer should be in
3. An example of a valid response

Format your response as a JSON object with field names as keys and guidance objects as valu

"""

    system_message = (
        "You are a helpful form completion assistant. Your goal is to help users complete "
        "forms by providing clear guidance on what information is needed and how to "
        "provide it correctly."
    )

    try:
        # Define the schema for the structured output
        class FieldGuidance(BaseModel):
            question: str
            format: str
            example: str

        class FormGuidance(BaseModel):
            __root__: Dict[str, FieldGuidance]

        # Query LLM for structured guidance
        result = await aquery_llm_structured(
            prompt=prompt,
            output_schema=FormGuidance,
            user=user,
            system_message=system_message,
            model=model,
        )

        # Convert to simpler format for the caller
        guidance = {}
        for field, field_guidance in result.__root__.items():
            guidance[field] = (
                f"{field_guidance.question}\n"
                f"Format: {field_guidance.format}\n"
                f"Example: {field_guidance.example}"
            )

        return guidance

    except Exception as e:
        logger.error(f"Error generating form guidance: {e}")
        # Fallback to simpler guidance
        guidance = {}
        for field in missing_fields:
            description = properties.get(field, {}).get("description", f"the {field}")
            guidance[field] = f"Please provide {description}"

        return guidance


# ---------------------------------------------
# endregion Smart Form Handling
# ---------------------------------------------


# ---------------------------------------------
# region Message Parsing
# ---------------------------------------------

async def extract_entities_from_message(
        message_text: str,
        entity_types: List[str],
        *,
        user: Optional[UserLike] = None,
        model: Optional[str] = None,
) -> Dict[str, List[str]]:
    """
    Extract specific types of entities from a message.

    Args:
        message_text: The message text to extract entities from
        entity_types: List of entity types to extract (e.g., "email", "phone", "date", "url
        user: User identifier for tracking and permissions
        model: Optional LLM model to use

    Returns:
        Dictionary mapping entity types to lists of extracted entities
    """
    # Build the type schema for the structured output
    entity_schema = {
        "type": "object",
        "properties": {}
    }

    for entity_type in entity_types:
        entity_schema["properties"][entity_type] = {
            "type": "array",
            "items": {"type": "string"},
            "description": f"List of {entity_type} entities found in the text"
        }

    # Create dynamic Pydantic model for the response
    class EntityExtraction(BaseModel):
        pass

    for entity_type in entity_types:
        setattr(EntityExtraction, entity_type, List[str])

    # Build prompt
    entity_list = ", ".join(entity_types)
    prompt = f"""
Extract the following entities from this message: {entity_list}

Message:
{message_text}

Only extract entities that are explicitly mentioned in the message. 
Return a JSON object with each entity type as a key, and a list of extracted entities as va
s.
If no entities of a particular type are found, return an empty list for that type.
"""

    system_message = (
        "You are an entity extraction assistant. Extract requested entities precisely "
        "without guessing or inferring information not explicitly stated."
    )

    try:
        result = await aquery_llm_structured(
            prompt=prompt,
            output_schema=EntityExtraction,
            user=user,
            system_message=system_message,
            model=model,
        )

        # Convert to dictionary
        extraction = {}
        for entity_type in entity_types:
            extraction[entity_type] = getattr(result, entity_type, [])

        return extraction

    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        # Return empty lists for all entity types
        return {entity_type: [] for entity_type in entity_types}


async def parse_message_intent(
        message_text: str,
        possible_intents: List[str],
        *,
        user: Optional[UserLike] = None,
        model: Optional[str] = None,
) -> Tuple[str, float]:
    """
    Parse the intent of a message from a predefined list of possible intents.

    Args:
        message_text: The message text to parse
        possible_intents: List of possible intent categories
        user: User identifier for tracking and permissions
        model: Optional LLM model to use

    Returns:
        Tuple of (most likely intent, confidence score 0-1)
    """
    class IntentClassification(BaseModel):
        intent: str
        confidence: float
        explanation: str

    # Format the list of possible intents
    intent_list = "\n".join([f"- {intent}" for intent in possible_intents])

    prompt = f"""
Classify the user's message into one of the following intent categories:

{intent_list}

User message:
{message_text}

Analyze the message and determine which intent category best matches. 
Return a JSON object with:
1. The intent (must be one from the list)
2. A confidence score between 0 and 1 (where 1 is completely confident)
3. A brief explanation of why you chose this intent
"""

    system_message = (
        "You are an intent classification assistant. Your task is to accurately classify "
        "user messages into predefined intent categories."
    )

    try:
        result = await aquery_llm_structured(
            prompt=prompt,
            output_schema=IntentClassification,
            user=user,
            system_message=system_message,
            model=model,
        )

        # Validate that the returned intent is in the possible intents
        if result.intent not in possible_intents:
            logger.warning(f"LLM returned intent '{result.intent}' not in possible intents")
            # Find the closest match
            return (possible_intents[0], 0.5)

        return (result.intent, result.confidence)

    except Exception as e:
        logger.error(f"Error classifying message intent: {e}")
        # Return first intent with low confidence as fallback
        return (possible_intents[0], 0.5)


async def process_forwarded_messages(
        messages: List[Message],
        *,
        user: Optional[UserLike] = None,
        model: Optional[str] = None,
) -> str:
    """
    Process a batch of forwarded messages and provide a summary.

    Args:
        messages: List of Message objects representing forwarded messages
        user: User identifier for tracking and permissions
        model: Optional LLM model to use

    Returns:
        Summary of the forwarded messages
    """
    if not messages:
        return "No messages to process"

    # Extract text from messages
    message_texts = []
    for i, msg in enumerate(messages):
        sender = msg.forward_from.full_name if msg.forward_from else "Unknown sender"
        text = msg.text or msg.caption or "[Non-text content]"
        message_texts.append(f"Message {i+1} from {sender}:\n{text}")

    all_messages = "\n\n".join(message_texts)

    prompt = f"""
I've received these forwarded messages:

{all_messages}

Please provide:
1. A concise summary of the conversation
2. Key points or requests
3. Any action items or questions that need responses

Keep the summary focused and brief, highlighting only the most important information.
"""

    try:
        result = await aquery_llm(
            prompt=prompt,
            user=user,
            model=model,
        )
        return result

    except Exception as e:
        logger.error(f"Error processing forwarded messages: {e}")
        return "Error processing messages"


# ---------------------------------------------
# endregion Message Parsing
# ---------------------------------------------


# ---------------------------------------------
# region Validation & Quality
# ---------------------------------------------

async def validate_text(
        text: str,
        guidelines: Union[str, List[str]],
        *,
        user: Optional[UserLike] = None,
        model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate text against provided guidelines or quality criteria.

    Args:
        text: The text to validate
        guidelines: Guidelines or criteria for validation (string or list of strings)
        user: User identifier for tracking and permissions
        model: Optional LLM model to use

    Returns:
        Validation results with suggestions for improvement
    """
    class ValidationResult(BaseModel):
        meets_guidelines: bool
        score: float  # 0-1 score
        issues: List[str]
        suggestions: List[str]

    # Format guidelines
    if isinstance(guidelines, list):
        guidelines_text = "\n".join([f"- {guideline}" for guideline in guidelines])
    else:
        guidelines_text = guidelines

    prompt = dedent(f"""
        Validate the following text against these guidelines:
        
        GUIDELINES:
        {guidelines_text}
        
        TEXT TO VALIDATE:
        {text}
        
        Analyze the text and check if it meets all the guidelines. 
        Return a JSON object with:
        1. Whether the text meets the guidelines (boolean)
        2. A score between 0 and 1 indicating overall compliance
        3. A list of specific issues found
        4. A list of suggestions to improve compliance
        """)

    system_message = (
        "You are a text validation assistant. Your task is to objectively assess "
        "whether text meets specified guidelines and provide constructive feedback."
    )

    try:
        result = await aquery_llm_structured(
            prompt=prompt,
            output_schema=ValidationResult,
            user=user,
            system_message=system_message,
            model=model,
        )

        return {
            "meets_guidelines": result.meets_guidelines,
            "score": result.score,
            "issues": result.issues,
            "suggestions": result.suggestions,
        }

    except Exception as e:
        logger.error(f"Error validating text: {e}")
        return {
            "meets_guidelines": False,
            "score": 0.0,
            "issues": [f"Error during validation: {str(e)}"],
            "suggestions": ["Try again later"],
        }


async def improve_text(
        text: str,
        improvement_type: str,
        *,
        user: Optional[UserLike] = None,
        model: Optional[str] = None,
) -> str:
    """
     Improve text based on specified improvement type.

     Args:
         text: The text to improve
         improvement_type: Type of improvement (e.g., "grammar", "conciseness", "clarity")
         user: User identifier for tracking and permissions
         model: Optional LLM model to use

     Returns:
         Improved version of the text
     """
    prompt = f"""
Improve the following text for {improvement_type}:

{text}

Please maintain the original meaning and information while improving the {improvement_type}
.
Return only the improved text without explanations or additional commentary.
"""

    system_message = (
        f"You are a text improvement assistant specializing in {improvement_type}. "
        f"Your task is to improve text for {improvement_type} while preserving its "
        "original meaning and information."
    )

    try:
        result = await aquery_llm(
            prompt=prompt,
            user=user,
            system_message=system_message,
            model=model,
        )
        return result

    except Exception as e:
        logger.error(f"Error improving text: {e}")
        return text  # Return original text on error


# ---------------------------------------------
# endregion Validation & Quality
# ---------------------------------------------