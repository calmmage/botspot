# Features

## Command request parameters

A simple feature: I want to be able to have commands ask me for parameters, if I forgot to provide one

How to implement:
- a general decorator that accepts a list of parameters that should be in the message
- simplest case: just one parameter (all text -> that parameter)

- if multiple parameters - ... should we ask llm? 
- if enums -> make selection? 

- Utilize pydantic somehow? 
  - Parse with llm should be the best option..

## Botspot errors types

- make integrate with error handler

idea 1: User-facing error type. Inherit from it -> the user will get the error message
idea 2: error formatter. If present -> the formatted error message will be sent to the user
idea 3: llm? 