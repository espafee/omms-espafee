class DuplicateProofOfExecutionError(Exception):
    status_code = 409

    def __init__(self, poe_record):
        self.data = {
            "detail": "POE already submitted for this booking.",
            "poe_id": poe_record.id,
            "status": poe_record.verification_status,
        }
        super().__init__(self.data["detail"])
