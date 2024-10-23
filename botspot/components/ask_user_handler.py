# import asyncio
#
# from aiogram import types
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import StatesGroup, State
# from aiogram.types import Message
#
# # from bot_lib import Handler, HandlerDisplayMode
#
#
# class CustomState(StatesGroup):
#     Waiting = State("waiting_for_user_input")
#
#
#
#
# user_inputs = {}
#
# async def get_info_from_user(message: Message, question: str, state: FSMContext):
#     chat_id = message.chat.id
#     await state.set_state(CustomState.Waiting)
#     # Create an Event for this specific chat
#     if chat_id not in user_inputs:
#         user_inputs[chat_id] = {"event": asyncio.Event(), "input": None}
#
#     # Send the question
#     await reply_safe(message, question)
#
#     # Wait for the input
#     await user_inputs[chat_id]["event"].wait()
#
#     # Get and clear the input
#     user_input = user_inputs[chat_id]["input"]
#     user_inputs[chat_id]["input"] = None
#     user_inputs[chat_id]["event"].clear()
#
#     return user_input
#
# async def handle_user_input(message: Message, state: FSMContext):
#     chat_id = message.chat.id
#
#     if chat_id in user_inputs:
#         # Store the user's input
#         user_inputs[chat_id]["input"] = await get_message_text(message)
#         # Set the event to unblock the waiting task
#         user_inputs[chat_id]["event"].set()
#
#     # Clear the state
#     await state.clear()
#
# async def sample_request_data_command(message: types.Message, state: FSMContext):
#     message_from_user = await get_message_text(message)
#     message_from_user = strip_command(message_from_user)
#     if not message_from_user:
#         message_from_user = await get_info_from_user(
#             message, "Please provide some data for the request", state
#         )
#     await reply_safe(message, "You provided: " + message_from_user)
#
# def register_extra_handlers(router):
#     super().register_extra_handlers(router)
#     router.message.register(handle_user_input, CustomState.Waiting)
#     return router
#
# name = "main"
# display_mode = HandlerDisplayMode.FULL
# commands = {
#     "sample_request_data_command": ["sample_request_data_command"],
# }
#
# def setup_dispatcher
