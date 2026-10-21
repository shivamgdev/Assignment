from sqlalchemy import inspect, text

from app.database import engine


def migrate():
    inspector = inspect(engine)

    if "orders" not in inspector.get_table_names():
        raise RuntimeError("Orders table does not exist")

    columns = {
        column["name"]
        for column in inspector.get_columns("orders")
    }

    if "status" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE orders "
                    "ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'PLACED'"
                )
            )


if __name__ == "__main__":
    migrate()