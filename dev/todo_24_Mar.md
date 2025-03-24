
- [ ] Update all examples to a new template (import base bot)
- [ ] update mini-botspot template and botspot template to new format	

Chat binder:
- [x] /bind_status - know if this chat is bound and with which keys 
- [x] /unbind -> check if there are records in the db with this key first. If not - error instead of success
- [x] /unbind -> if default key, check if there are records in db for this chat with any key - and delete that if there's no default
