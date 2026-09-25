class FakeDataClient:
    """Scripted stand-in for boto3 redshift-data: each statement walks through `statuses`."""

    def __init__(self, statuses=("STARTED", "FINISHED"), duration_ns=2_000_000_000, error="", pages=None):
        self.statuses = list(statuses)
        self.duration_ns = duration_ns
        self.error = error
        self.pages = pages or []
        self.calls = []
        self._polls = {}

    def batch_execute_statement(self, **kw):
        self.calls.append(("batch", kw))
        return {"Id": f"s{len(self.calls)}"}

    def execute_statement(self, **kw):
        self.calls.append(("exec", kw))
        return {"Id": f"s{len(self.calls)}"}

    def describe_statement(self, Id):
        n = self._polls.get(Id, 0)
        self._polls[Id] = n + 1
        status = self.statuses[min(n, len(self.statuses) - 1)]
        return {"Id": Id, "Status": status, "Duration": self.duration_ns, "Error": self.error}

    def cancel_statement(self, Id):
        self.calls.append(("cancel", {"Id": Id}))
        return {"Status": True}

    def get_statement_result(self, Id, NextToken=None):
        index = int(NextToken or 0)
        page = dict(self.pages[index])
        if index + 1 < len(self.pages):
            page["NextToken"] = str(index + 1)
        return page
