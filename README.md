# cash-llm-sample

## Getting Started

Sync the contents of pyproject.toml to the Python environment managed by rye.

```
rye sync
```

Create a SQLite database.

```sh
$ sqlite3 cash.db
```

Save credit card usage history to SQLite by hitting the Gmail API.

```sh
$ python sqldb.py
```

Get the total expenditure and the top 3 usage locations in the past month.

```sh
$ python cash_llm.py

The total expenditure in November is 128455. 
The top 10 usage locations and their proportions in the total expenditure are as follows:
1. SEVEN-ELEVEN: 23471 (18.27%)
2. JR EAST MOBILE SUICA: 19432 (15.13%)
3. AMAZON CO JP: 13400 (10.43%)
...
```

