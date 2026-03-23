"""Policy domain errors."""


class PolicyError(Exception):
    pass


class PolicyNotFound(PolicyError):
    def __init__(self, policy_id: str):
        super().__init__(f"Policy not found: {policy_id}")
        self.policy_id = policy_id
