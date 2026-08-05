# Postgres database demo

Async SQLAlchemy 2.x + asyncpg via Botspot. App owns tables and Alembic migrations.

## Setup

```bash
cp example.env .env   # set token + BOTSPOT_POSTGRES_DATABASE_URL
uv run python bot.py
```

## App integration

```python
from botspot.components.data.postgres_database import Base, get_session
from sqlalchemy.orm import Mapped, mapped_column

class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str]

async with get_session() as session:
    session.add(Note(text="hello"))
    await session.commit()
```

## Alembic (in the consuming bot)

```python
# alembic/env.py
from botspot.components.data.postgres_database import Base
import myapp.models  # noqa: F401 — register models on Base.metadata
target_metadata = Base.metadata
```

Use the same `postgresql+asyncpg://...` URL. Botspot does not ship app tables or migration scripts.

When sharing a database with another application, give the bot its own schema and
Alembic version table. Set table schemas on the consuming app's models, enable
`include_schemas`, and configure `version_table_schema` (or a distinct
`version_table`) so the bot never reads or overwrites the host application's
`alembic_version` row.
