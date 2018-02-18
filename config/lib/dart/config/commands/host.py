from . import BaseCommand
import cassandra.query
import json


class HostsCommand(BaseCommand):
    def run(self, **kwargs):
        hosts = dict()

        # we only care about hosts that we are probing. we don't want to deploy
        # to hosts that aren't maintained with dart. that would be a surprising
        # situation.
        query = cassandra.query.SimpleStatement("""
            SELECT fqdn
            FROM dart.probe
        """)
        rows = self.session.execute(query)
        for row in rows:
            hosts[row["fqdn"]] = dict(tags=[])

        # we can also deploy by tag name instead of fqdn. get all of the
        # hosts for each tag and put them into a list.
        query = cassandra.query.SimpleStatement("""
            SELECT
                fqdn,
                tag
            FROM dart.host_tag
        """)
        rows = self.session.execute(query)
        for row in rows:
            if (row["fqdn"] not in hosts):
                hosts[row["fqdn"]] = dict()
            if ("tags" not in hosts[row["fqdn"]]):
                hosts[row["fqdn"]]["tags"] = []
            hosts[row["fqdn"]]["tags"].append(row["tag"])

        print(json.dumps(hosts, sort_keys=True, indent=4))
