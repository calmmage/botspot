"""
# Queue Operations with MongoDB and MongoEngine

This project demonstrates basic CRUD operations with MongoDB and MongoEngine.

## Use Cases

### Abstract Add
The `add_item` function allows for abstract addition of any class that inherits from MongoEngine's `Document`.

add_item(SQDQueueItem, name='item1', url='url1')

# Find an Item
Items can be fetched by either their _id or a name field.

get_item(SQDQueueItem, 'item1')  # By name
get_item(SQDQueueItem, '5ff751482749093351c3e90f')  # By _id

# Update an Item
Items can be updated by providing their _id or name and the fields to update.

update_item(SQDQueueItem, 'item1', url='new_url1')
update_item(SQDQueueItem, '5ff751482749093351c3e90f', url='new_url1')

# Delete an Item
Items can be deleted by providing their _id or name.
delete_item(SQDQueueItem, '5ff751482749093351c3e90f')
delete_item(SQDQueueItem, 'item1')

"""

import os
from pathlib import Path

import mongoengine
from bson import ObjectId
from dotenv import load_dotenv

default_database_connected = False


def connect_to_db(conn_str=None, db_name=None, alias=None, **kwargs):
    global default_database_connected
    if alias is None or alias == "default":
        if default_database_connected:
            return mongoengine.get_connection(alias=alias)
    dotenv_path = Path(os.curdir) / ".env"
    load_dotenv(dotenv_path)

    if conn_str is None:
        conn_str = os.getenv("DATABASE_CONN_STR")
        if conn_str is None:
            raise ValueError("Connection string not provided")

    if db_name is None:
        db_name = os.getenv("DATABASE_NAME")
        if db_name is None:
            raise ValueError("Database name not provided")

    if alias is None or alias == "default":
        default_database_connected = True
    return mongoengine.connect(db=db_name, host=conn_str, alias=alias, **kwargs)


def add_item(cls, **kwargs):
    item = cls(**kwargs)
    item.save()
    return item


def get_item(cls, key):
    try:
        # Try finding by ObjectId first
        return cls.objects(id=ObjectId(key)).first()
    except:
        # Fallback to find by name
        return cls.objects(name=key).first()


def update_item(cls, key, **kwargs):
    item = get_item(cls, key)
    if item:
        item.update(**kwargs)


def delete_item(cls, key):
    item = get_item(cls, key)
    if item:
        item.delete()


def list_items(cls, **filters):
    return cls.objects(**filters).all()


if __name__ == "__main__":
    connect_to_db()

    class SampleItem(mongoengine.Document):
        name = mongoengine.StringField(required=True)
        url = mongoengine.StringField(required=True)
        _meta = {"collection": "sample_items"}

    add_item(SampleItem, name="item1", url="url1")
    test_item = get_item(SampleItem, "item1")
    print(test_item.to_json())  # Should print the item

    # Assuming you know the '_id' of the item you just inserted
    known_id = str(test_item.id)
    update_item(SampleItem, known_id, url="new_url1")
    print(get_item(SampleItem, known_id).to_json())  # Should print the updated item

    delete_item(SampleItem, known_id)
    print(get_item(SampleItem, known_id))  # Should print None
