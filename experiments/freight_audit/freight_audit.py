from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

CENT = Decimal('0.01')


def money(value: str | int | float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Contract:
    contract_id: str
    carrier: str
    origin: str
    destination: str
    container_type: str
    base_rate: Decimal
    fuel_surcharge_pct: Decimal
    free_demurrage_days: int
    demurrage_rate_per_day: Decimal
    allowed_accessorials: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Shipment:
    bol_number: str
    contract_id: str
    actual_demurrage_days: int


@dataclass(frozen=True)
class Invoice:
    invoice_number: str
    bol_number: str
    carrier: str
    invoice_date: date
    base_rate: Decimal
    fuel_surcharge: Decimal
    demurrage: Decimal
    accessorials: tuple[tuple[str, Decimal], ...] = ()

    @property
    def total(self) -> Decimal:
        return money(self.base_rate + self.fuel_surcharge + self.demurrage + sum((v for _, v in self.accessorials), Decimal('0')))


@dataclass(frozen=True)
class Finding:
    invoice_number: str
    code: str
    severity: str
    billed: Decimal
    expected: Decimal
    difference: Decimal
    evidence: str
    confidence: str


def _finding(invoice: Invoice, code: str, billed: Decimal, expected: Decimal, evidence: str, *, severity: str = 'review', confidence: str = 'high') -> Finding:
    billed, expected = money(billed), money(expected)
    return Finding(invoice.invoice_number, code, severity, billed, expected, money(max(Decimal('0'), billed - expected)), evidence, confidence)


def audit_invoice(invoice: Invoice, shipment: Shipment, contract: Contract) -> list[Finding]:
    findings: list[Finding] = []
    if shipment.bol_number != invoice.bol_number:
        raise ValueError('invoice/shipment BOL mismatch')
    if shipment.contract_id != contract.contract_id:
        raise ValueError('shipment/contract mismatch')
    if invoice.carrier.casefold() != contract.carrier.casefold():
        findings.append(_finding(invoice, 'CARRIER_MISMATCH', invoice.total, Decimal('0'), f'Invoice carrier {invoice.carrier!r} differs from contract carrier {contract.carrier!r}.', confidence='medium'))

    if invoice.base_rate > contract.base_rate:
        findings.append(_finding(invoice, 'BASE_RATE_OVERCHARGE', invoice.base_rate, contract.base_rate, f'Contract {contract.contract_id} base rate is {money(contract.base_rate)}.'))

    expected_fuel = money(contract.base_rate * contract.fuel_surcharge_pct)
    if invoice.fuel_surcharge > expected_fuel:
        findings.append(_finding(invoice, 'FUEL_SURCHARGE_OVERCHARGE', invoice.fuel_surcharge, expected_fuel, f'Fuel = contract base {money(contract.base_rate)} × {contract.fuel_surcharge_pct}.'))

    excess_days = max(0, shipment.actual_demurrage_days - contract.free_demurrage_days)
    expected_demurrage = money(Decimal(excess_days) * contract.demurrage_rate_per_day)
    if invoice.demurrage > expected_demurrage:
        code = 'INVALID_DEMURRAGE_CHARGE' if excess_days == 0 else 'DEMURRAGE_OVERCHARGE'
        findings.append(_finding(invoice, code, invoice.demurrage, expected_demurrage, f'Shipment recorded {shipment.actual_demurrage_days} demurrage days; contract allows {contract.free_demurrage_days} free days at {money(contract.demurrage_rate_per_day)}/excess day.'))

    for name, amount in invoice.accessorials:
        if name not in contract.allowed_accessorials and amount > 0:
            findings.append(_finding(invoice, 'UNSUPPORTED_ACCESSORIAL', amount, Decimal('0'), f'Accessorial {name!r} is not present in the supplied contract allow-list.', confidence='medium'))
    return findings


def duplicate_candidates(invoices: Iterable[Invoice]) -> list[Finding]:
    """Flag only strong duplicate candidates, not every multi-invoice BOL.

    Same BOL alone is insufficient because legitimate split/supplemental invoices exist.
    This prototype requires same carrier and same component total; findings remain REVIEW,
    never an automatic recovery claim.
    """
    seen: dict[tuple[str, str, Decimal], Invoice] = {}
    findings: list[Finding] = []
    for invoice in sorted(invoices, key=lambda x: (x.invoice_date, x.invoice_number)):
        key = (invoice.bol_number, invoice.carrier.casefold(), invoice.total)
        prior = seen.get(key)
        if prior and prior.invoice_number != invoice.invoice_number:
            findings.append(_finding(invoice, 'DUPLICATE_CANDIDATE', invoice.total, Decimal('0'), f'Same BOL, carrier, and total as earlier invoice {prior.invoice_number}; human review required.', confidence='medium'))
        else:
            seen[key] = invoice
    return findings


def audit_batch(invoices: Iterable[Invoice], shipments: dict[str, Shipment], contracts: dict[str, Contract]) -> list[Finding]:
    invoices = list(invoices)
    findings = duplicate_candidates(invoices)
    for invoice in invoices:
        shipment = shipments.get(invoice.bol_number)
        if shipment is None:
            findings.append(_finding(invoice, 'MISSING_SHIPMENT_RECORD', invoice.total, Decimal('0'), f'No shipment/BOL record supplied for {invoice.bol_number}.', confidence='low'))
            continue
        contract = contracts.get(shipment.contract_id)
        if contract is None:
            findings.append(_finding(invoice, 'MISSING_CONTRACT', invoice.total, Decimal('0'), f'No contract supplied for {shipment.contract_id}.', confidence='low'))
            continue
        findings.extend(audit_invoice(invoice, shipment, contract))
    return findings
