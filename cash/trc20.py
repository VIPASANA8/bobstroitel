from dataclasses import dataclass
from datetime import datetime

from cash.amounts import MAX_MICROS


MOCK_NETWORK = "TRC20"
MOCK_ADDRESS = "TMockPoker8C2C111111111111111111111"
MOCK_USDT_CONTRACT = "TMockUSDT1111111111111111111111111"


@dataclass(frozen=True)
class TransferEvent:
    provider: str
    external_event_id: str
    tx_hash: str
    event_index: int
    network: str
    token_contract: str
    destination_address: str
    amount_micros: int
    occurred_at: datetime

    def validate(self) -> None:
        values = (
            (self.provider, 32), (self.external_event_id, 200),
            (self.tx_hash, 128), (self.network, 16),
            (self.token_contract, 128), (self.destination_address, 128),
        )
        if any(not isinstance(value, str) or not value or len(value) > limit for value, limit in values):
            raise ValueError("invalid transfer event identifier")
        if type(self.event_index) is not int or not 0 <= self.event_index <= 2**31 - 1:
            raise ValueError("invalid transfer event index")
        if type(self.amount_micros) is not int or not 0 < self.amount_micros <= MAX_MICROS:
            raise ValueError("invalid transfer amount")
        if self.occurred_at.tzinfo is None:
            raise ValueError("transfer time must include a timezone")
