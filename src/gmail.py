# ref: https://github.com/googleworkspace/python-samples/blob/main/gmail/snippet/send%20mail/send_message.py
# ref: https://qiita.com/orikei/items/73dc1ccc95d1872ab1cf
# ref: メッセージを検索する | https://developers.google.com/gmail/api/guides/filtering?hl=ja
# ref: Gmail で使用できる検索演算子 | https://support.google.com/mail/answer/7190?hl=ja
import os.path
from dotenv import dotenv_values
import re
import base64
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
import pandas as pd

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

config = dotenv_values()


class MailAddress(Enum):
    # ref: https://qiita.com/azumagoro/items/bafed453e12b7a5d4b2f
    JCB = (1, config["JCB_MAIL_ADDRESS"])
    VPASS = (2, config["VPASS_MAIL_ADDRESS"])

    def __init__(self, id, mail_address):
        self.id = id
        self.mail_address = mail_address


class EmailParser(BaseModel):
    mail_from: str = Field(..., title="送信元")

    @staticmethod
    def get_email(mail_from):
        regex = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
        match = regex.search(mail_from)
        return match.group() if match else None

    def update_mail_from(self):
        self.mail_from = self.get_email(self.mail_from)


class CashMailParser(EmailParser):
    mail_text: str = Field(..., title="メールテキスト")

    def parse_mail(self):
        # 送信元を更新
        self.update_mail_from()
        # 送信者によってクレジットと正規表現を変更
        (
            credit_name,
            date_time_pattern,
            amount_pattern,
            location_pattern,
        ) = self.get_patterns(self.mail_from)
        # メールテキストから各詳細を検索
        date_time_match = (
            re.search(date_time_pattern, self.mail_text) if date_time_pattern else None
        )
        amount_match = (
            re.search(amount_pattern, self.mail_text) if amount_pattern else None
        )
        location_match = (
            re.search(location_pattern, self.mail_text) if location_pattern else None
        )
        # 詳細を抽出して返す
        dt = (
            datetime.strptime(
                date_time_match.group(1), "%Y/%m/%d %H:%M"
            )  # .strftime("%Y%m%d%H")
            if date_time_match and date_time_match.group(1)
            else None
        )
        price = float(amount_match.group(1).replace(",", "")) if amount_match else None
        usage_location = (
            location_match.group(1).rstrip("\r\n") if location_match else None
        )
        return {
            "credit_name": credit_name,
            "from": self.mail_from,
            "dt": dt,
            "price": price,
            "usage_location": usage_location,
        }

    @staticmethod
    def get_patterns(mail_from):
        credit_name, date_time_pattern, amount_pattern, location_pattern = (
            None,
            None,
            None,
            None,
        )
        if mail_from == MailAddress.JCB.mail_address:
            credit_name = MailAddress.JCB.name
            date_time_pattern = r"{}".format(config["JCB_MAIL_DATE_TIME_PATTERN"])
            amount_pattern = r"{}".format(config["JCB_MAIL_AMOUNT_PATTERN"])
            location_pattern = r"{}".format(config["JCB_MAIL_LOCATION_PATTERN"])
        elif mail_from == MailAddress.VPASS.mail_address:
            credit_name = MailAddress.VPASS.name
            date_time_pattern = r"{}".format(config["VPASS_MAIL_DATE_TIME_PATTERN"])
            amount_pattern = r"{}".format(config["VPASS_MAIL_AMOUNT_PATTERN"])
            location_pattern = r"{}".format(config["VPASS_MAIL_LOCATION_PATTERN"])
        return credit_name, date_time_pattern, amount_pattern, location_pattern


class Gmail:
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def connect_gmail(self):
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", self.SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", self.SCOPES
                )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        # Call the Gmail API
        service = build("gmail", "v1", credentials=creds)
        return service

    def get_message_list(self, date_from, date_to, message_from, subject):
        # 結果を格納するリスト
        MessageList = []
        # 検索用クエリを指定する
        query = self.build_query(date_from, date_to, message_from, subject)

        try:
            # APIに接続
            service = self.connect_gmail()
            # メールIDの一覧を取得する(最大100件)
            messageIDlist = (
                service.users()
                .messages()
                .list(userId="me", maxResults=100, q=query)
                .execute()
            )
            # 該当するメールが存在しない場合は、処理中断
            if messageIDlist["resultSizeEstimate"] == 0:
                print("Message is not found")
                return MessageList
            # メッセージIDを元に、メールの詳細情報を取得
            for message in messageIDlist["messages"]:
                row = self.get_message_detail(service, message)
                MessageList.append(row)
        except HttpError as error:
            print(f"An error occurred: {error}")
        return MessageList

    def build_query(self, date_from, date_to, message_from, subject):
        query = ""
        if date_from != None and date_from != "":
            query += "after:" + date_from + " "
        if date_to != None and date_to != "":
            query += "before:" + date_to + " "
        if message_from != None and message_from != "":
            query += "from:" + message_from + " "
        if subject != None and subject != "":
            query += "subject:" + subject + " "
        return query

    def get_message_detail(self, service, message):
        row = {}
        row["ID"] = message["id"]
        MessageDetail = (
            service.users().messages().get(userId="me", id=message["id"]).execute()
        )
        # 日付、送信元、件名を取得する
        for header in MessageDetail["payload"]["headers"]:
            if header["name"] == "Date":
                row["date"] = header["value"]
            elif header["name"] == "From":
                row["from"] = header["value"]
            elif header["name"] == "Subject":
                row["subject"] = header["value"]

        # ヘッダ情報の取得 ...
        row["body"] = self.get_message_body(MessageDetail)
        # CashMailParserのインスタンスを作成して使用
        parser = CashMailParser(mail_from=row["from"], mail_text=row["body"])
        parsed_details = parser.parse_mail()  # 解析メソッドを呼び出し
        row.update(parsed_details)

        return row

    def get_message_body(self, MessageDetail):
        if MessageDetail["payload"]["body"]["size"] != 0:
            decoded_bytes = base64.urlsafe_b64decode(
                MessageDetail["payload"]["body"]["data"]
            )
            decoded_message = decoded_bytes.decode("UTF-8")
            return decoded_message
        else:
            decoded_bytes = base64.urlsafe_b64decode(
                MessageDetail["payload"]["parts"][0]["body"]["data"]
            )
            decoded_message = decoded_bytes.decode("UTF-8")
            return decoded_message


if __name__ == "__main__":
    credit_history = []

    gmail_conn = Gmail()

    credit_history.extend(
        gmail_conn.get_message_list(
            date_from="2023-10-31",
            date_to="2023-12-03",
            message_from=MailAddress.JCB.mail_address,
            subject=config["SUBJECT"],
            # 複数のキーワードをグループ化します: subject:(夕食 映画)
        )
    )
    credit_history.extend(
        gmail_conn.get_message_list(
            date_from="2023-10-31",
            date_to="2023-12-03",
            message_from=MailAddress.VPASS.mail_address,
            subject=config["SUBJECT"],
            # 複数のキーワードをグループ化します: subject:(夕食 映画)
        )
    )
    df = pd.DataFrame(credit_history)[["usage_location", "price", "credit_name", "dt"]]
    df["dt"] = pd.to_datetime(df["dt"])
    df.to_csv("../credit_history.csv", index=False)
    for _, row in df.iterrows():
        print("--------------------------------------------------")
        print(row["usage_location"])
        print(row["price"])
        print(row["credit_name"])
        print(row["dt"])
