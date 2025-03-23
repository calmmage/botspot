# Auto Archive

- **Main Feature**: Forwards messages to a bound archive chat and deletes them from the original conversation to keep it clean.
- **Demo Bot**: Bind it with `/bind_archive [archive_chat_id]`; send any message—it auto-forwards to the archive chat and deletes from the original chat.
- **Useful Bot**: **Clean Inbox Bot** - Bind it to an archive chat; it forwards all messages (or specific ones) there, deletes them from your input chat, and maintains a clutter-free space.

**Notes**: The flow is exactly as described—message in, forward to archive, delete from convo. Binding sets up the archive chat once, then it's fully automatic.

## Developer Notes

1) main feature - bot forwards and deletes all messages from chat. by default - from the chat with itself. so this is a bot for writing down information. Optionally - invite a bot to a chat and config to do that there instead of in pm.

2) there should be a configurable timeout (i guess per user) - do we need a simple UserConfig component for that - i think we should already have something like that in UserManager. Maybe rework the user manager to make it simpler? Right now we need to modify User class for that which is not exacly nice - but might be ok. Alternative - have a separate colleciton for thet?

3) there should be a way to set up to which chat are we archiving. I guess that's the /bind command

4) safety - never delete messages unless we're sure they were forwarded successfully. Or even better - simply save all messages to db also before deleting them (i guess this is based on queue also)
