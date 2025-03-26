# Ask User Handler Design Notes

## Core Functionality

- Allows asking user questions and waiting for responses
- Uses FSM (Finite State Machine) for state management
- Implements timeout mechanism using asyncio.Event
- Supports multiple concurrent requests per user

## Implementation Details

1. Uses event-based signaling instead of polling for better performance
2. Handles timeouts gracefully
3. Maintains request queue per chat
4. Supports cleanup of expired/completed requests

## Future Enhancements Discussed

1. Callback Support
    - Add support for button-based responses
    - Create universal decorator for easy button creation
    - Allow mixing text and button responses

2. Response Validation
    - Add input validation
    - Support retry logic
    - Custom error messages

3. Advanced Use Cases
    - Timezone/location collection
    - Fallback input collection
    - Multi-step dialogs

## Design Considerations

- Keep core functionality simple and extensible
- Maintain backward compatibility
- Focus on user experience (quick responses, clear messages)
- Support both simple and complex use cases

## Original Requirements/Discussion

[Include relevant discussion points from chat history]

- Need for event-based signaling vs polling
- Importance of proper timeout handling
- Request for reply-to-message functionality
- Interest in callback button support
