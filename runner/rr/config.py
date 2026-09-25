import os
from dataclasses import dataclass

REGION = "us-east-1"


def require_sandbox() -> None:
    """Refuse to touch AWS unless the personal sandbox profile or CI OIDC is in use."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return
    profile = os.environ.get("AWS_PROFILE", "")
    if "sandbox" not in profile:
        raise RuntimeError(
            "AWS_PROFILE must be the personal sandbox profile (name contains 'sandbox'); "
            "refusing to use default credentials"
        )


@dataclass(frozen=True)
class Target:
    kind: str  # "cluster" | "workgroup"
    name: str
    database: str = "tpcds"
    db_user: str = "awsuser"

    @classmethod
    def parse(cls, spec: str) -> "Target":
        kind, _, name = spec.partition(":")
        if kind not in ("cluster", "workgroup") or not name:
            raise ValueError(f"target must be cluster:<id> or workgroup:<name>, got {spec!r}")
        return cls(kind, name)

    def api_kwargs(self) -> dict:
        if self.kind == "cluster":
            return {"ClusterIdentifier": self.name, "Database": self.database, "DbUser": self.db_user}
        return {"WorkgroupName": self.name, "Database": self.database}


def data_client():
    import boto3
    from botocore.config import Config

    require_sandbox()
    return boto3.client(
        "redshift-data", region_name=REGION, config=Config(retries={"mode": "standard", "max_attempts": 10})
    )
