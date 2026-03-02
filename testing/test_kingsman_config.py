import configparser
import unittest

from app.__init__ import _build_mysql_uri, _build_mysql_uri_with_database


class KingsmanConfigTests(unittest.TestCase):
    def setUp(self):
        self.cfg = configparser.ConfigParser()
        self.cfg.read_dict(
            {
                "mysql": {
                    "host": "127.0.0.1",
                    "port": "3306",
                    "user": "deep3576",
                    "password": "Gmsshn!43",
                    "database": "deep3576$TheSpiritSchool_ProdDB",
                    "charset": "utf8mb4",
                },
                "mysql_kingsman": {
                    "host": "127.0.0.1",
                    "port": "3306",
                    "user": "deep3576",
                    "password": "Gmsshn!43",
                    "database": "deep3576$TheSpiritSchool_ProdDB",
                    "kingsman_database": "deep3576$ProductionDB",
                    "charset": "utf8mb4",
                },
            }
        )

    def test_builds_music_school_uri_from_primary_database(self):
        uri = _build_mysql_uri(self.cfg, "mysql")
        self.assertIn("/deep3576$TheSpiritSchool_ProdDB?", uri)

    def test_builds_kingsman_uri_with_same_server_and_overridden_database(self):
        uri = _build_mysql_uri_with_database(
            self.cfg,
            "mysql_kingsman",
            self.cfg.get("mysql_kingsman", "kingsman_database"),
        )
        self.assertIn("@127.0.0.1:3306/", uri)
        self.assertIn("/deep3576$ProductionDB?", uri)


if __name__ == "__main__":
    unittest.main()
