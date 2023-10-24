#!/usr/bin/python3

from json import load, dumps

###############################################################################
# GitRepoStatsDB class
###############################################################################


class GitRepoStatsDB:
    def __init__(self):
        self.__db = None

        self.views = None
        self.views_start = None
        self.views_end = None

        try:
            with open("src/db/db.json", "r") as db:
                self.__db = load(db)
        except FileNotFoundError:
            with open("../src/db/db.json", "r") as db:
                self.__db = load(db)

        self.views = int(self.__db["views"]["count"])
        self.views_from_date = self.__db["views"]["from"]
        self.views_to_date = self.__db["views"]["to"]
        self.pull_requests = int(self.__db["pull_requests"])
        self.issues = int(self.__db["issues"])

    def __update_db(self) -> None:
        try:
            with open("src/db/db.json", "w") as db:
                db.write(dumps(self.__db, indent=2))
        except FileNotFoundError:
            with open("../src/db/db.json", "w") as db:
                db.write(dumps(self.__db, indent=2))

    def set_views_count(self, views_count: any) -> None:
        self.views = int(views_count)
        self.__db["views"]["count"] = str(self.views)
        self.__update_db()

    def set_views_from_date(self, date: str) -> None:
        self.views_from_date = date
        self.__db["views"]["from"] = self.views_from_date
        self.__update_db()

    def set_views_to_date(self, date: str) -> None:
        self.views_to_date = date
        self.__db["views"]["to"] = self.views_to_date
        self.__update_db()

    def set_pull_requests(self, pull_requests_count: int) -> None:
        self.__db["pull_requests"] = str(pull_requests_count)
        self.__update_db()

    def set_issues(self, issues_count: int) -> None:
        self.__db["issues"] = str(issues_count)
        self.__update_db()
