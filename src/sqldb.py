# ref: https://note.com/astropomeai/n/nb42830d2db8c
from dotenv import dotenv_values
import sqlite3
from sqlite3 import Error
from gmail import MailAddress, Gmail

config = dotenv_values()


def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(e)

    if conn:
        return conn


def create_table(conn):
    # テーブル作成
    try:
        query = f"""
        CREATE TABLE IF NOT EXISTS "{config['TABLE_NAME']}" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usage_location TEXT,
            price INTEGER,
            credit_name TEXT,
            dt TEXT
        );
        """
        conn.execute(query)
    except Error as e:
        print(e)


def drop_table_if_exists(conn):
    try:
        query = f"""DROP TABLE IF EXISTS "{config['TABLE_NAME']}";"""
        conn.execute(query)
    except Error as e:
        print(e)


def insert_values(conn, rows):
    try:
        cursor = conn.cursor()
        for row in rows:
            query = f"""
            INSERT INTO "{config['TABLE_NAME']}" (usage_location, price, credit_name, dt)
            VALUES ('{row["usage_location"]}', '{row["price"]}', '{row["credit_name"]}', '{row["dt"]}');
            """
            cursor.execute(query)
        conn.commit()
    except Error as e:
        print(e)


def get_credit_history():
    credit_history = []

    gmail_conn = Gmail()

    credit_history.extend(
        gmail_conn.get_message_list(
            date_from="2023-11-01",
            date_to="2023-12-03",
            message_from=MailAddress.JCB.mail_address,
            subject=config["SUBJECT"],
            # 複数のキーワードをグループ化します: subject:(夕食 映画)
        )
    )
    credit_history.extend(
        gmail_conn.get_message_list(
            date_from="2023-11-01",
            date_to="2023-12-03",
            message_from=MailAddress.VPASS.mail_address,
            subject=config["SUBJECT"],
            # 複数のキーワードをグループ化します: subject:(夕食 映画)
        )
    )
    return credit_history


def main():
    # Create a database connection
    conn = create_connection(config["DB_PATH"])
    if conn is not None:
        # Drop table if exists
        drop_table_if_exists(conn)
        # Create table
        create_table(conn)
        # Insert sample data
        rows = get_credit_history()
        insert_values(conn, rows)
        # Execute sql query
        res = conn.execute(f"""SELECT COUNT(1) FROM "{config['TABLE_NAME']}";""")
        print(res.fetchone())
    else:
        print("Error! Cannot create the database connection.")


if __name__ == "__main__":
    main()
