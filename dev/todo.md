# Todos from 06 Jan

- [ ] Add timezone scheduling code from simple cat feeding reminder bot

# Todos from 04 Jan

- [ ] add enum support for
- [ ] find example of timezone handling
    - [ ] add timezone handling to scheduler component

- [x] add user data support
  - [x] add mongodb support - with motor
    - [ ] add data models


- [ ] add mongo example
  - [ ] user db
  - [ ] store messages
  - [ ] store and recover event schedule
- [ ] auto-register users with middleware
  - [ ] alternative: just start command

- [ ] better start command: some kind of super() mechanic to avoid disabling key
  functionality. Or just middleware? - with filter on start
- [ ] better help command. Show all available commands (even not in main menu)

# Todos from 27 Dec

- [x] rework of notify_on_timeout and default_choice in ask_user component

Systems that I have
- BotManager
- Deps
- BotSettings
- utils (have access to deps, not registered)
- components

# Todos

## TDD-like Example Development
- [ ] Create a new folder `dev/examples`
- [ ] Develop example scenarios:
  - [ ] Basic bot setup
  - [ ] Error handling
  - [ ] User input handling
  - [ ] Multi-message processing
  - [ ] File handling (upload/download)
  - [ ] Inline keyboard example
  - [ ] Conversation flow example
  - [ ] Plugin integration example
- [ ] For each example:
  - [ ] Write the desired usage code
  - [ ] Identify missing components/utils
  - [ ] Implement necessary components/utils
  - [ ] Refactor and optimize as needed

## Component Development
- [ ] Improve error handling component
- [ ] Develop user input handling utility
- [ ] Create a multi-message processing component
- [ ] Implement file handling utilities
- [ ] Develop a conversation flow manager
- [ ] Create a plugin system for easy extensions

## Utils and Helpers
- [ ] Implement a flexible command parser
- [ ] Create a message formatting utility
- [ ] Develop a config management system
- [ ] Implement logging utilities

## Testing and Documentation
- [ ] Set up unit tests for each component
- [ ] Write integration tests for examples
- [ ] Create comprehensive documentation for each component
- [ ] Develop a quick start guide

## Optimization and Refactoring
- [ ] Review and optimize BotManager
- [ ] Refactor Dependency management system
- [ ] Improve overall project structure

## Extra Features
- [ ] MongoDB integration
- [ ] RocksDB integration
- [ ] User data management system
- [ ] Timezone / Location handling
- [ ] Config system (per user)
- [ ] Admin page (for bot owner)
- [ ] Trial mode implementation

## Future Considerations
- [ ] Explore integration with teletalk
- [ ] Consider implementing a web interface for bot management

Remember to prioritize tasks and tackle them incrementally. Start with the most critical examples and components, then build upon them as you progress.

Extras
- [ ] Try teletalk

