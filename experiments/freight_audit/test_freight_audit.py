from datetime import date
from decimal import Decimal
import unittest

from freight_audit import Contract, Shipment, Invoice, audit_batch, audit_invoice


class FreightAuditTests(unittest.TestCase):
    def setUp(self):
        self.contract = Contract(
            contract_id='CTR-1', carrier='Carrier A', origin='VNSGN', destination='USLAX',
            container_type='40HC', base_rate=Decimal('2450.00'), fuel_surcharge_pct=Decimal('0.12'),
            free_demurrage_days=7, demurrage_rate_per_day=Decimal('50.00'),
            allowed_accessorials=frozenset({'DOCUMENTATION'})
        )
        self.shipment = Shipment('BOL-1', 'CTR-1', 5)

    def invoice(self, number='INV-1', **overrides):
        values = dict(invoice_number=number, bol_number='BOL-1', carrier='Carrier A', invoice_date=date(2026, 3, 20),
                      base_rate=Decimal('2450.00'), fuel_surcharge=Decimal('294.00'), demurrage=Decimal('0.00'), accessorials=())
        values.update(overrides)
        return Invoice(**values)

    def test_clean_invoice_has_no_findings(self):
        self.assertEqual(audit_invoice(self.invoice(), self.shipment, self.contract), [])

    def test_rate_fuel_demurrage_and_accessorial_are_explainable(self):
        inv = self.invoice(base_rate=Decimal('2650'), fuel_surcharge=Decimal('320'), demurrage=Decimal('150'), accessorials=(('PORT_CONGESTION', Decimal('75')),))
        findings = audit_invoice(inv, self.shipment, self.contract)
        self.assertEqual({f.code for f in findings}, {'BASE_RATE_OVERCHARGE','FUEL_SURCHARGE_OVERCHARGE','INVALID_DEMURRAGE_CHARGE','UNSUPPORTED_ACCESSORIAL'})
        self.assertEqual(sum((f.difference for f in findings), Decimal('0')), Decimal('451.00'))
        self.assertTrue(all(f.evidence for f in findings))

    def test_duplicate_requires_same_bol_carrier_and_total(self):
        a = self.invoice('INV-A')
        b = self.invoice('INV-B', invoice_date=date(2026,3,21))
        c = self.invoice('INV-C', invoice_date=date(2026,3,22), fuel_surcharge=Decimal('295'))
        findings = audit_batch([a,b,c], {'BOL-1':self.shipment}, {'CTR-1':self.contract})
        dups = [f for f in findings if f.code == 'DUPLICATE_CANDIDATE']
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0].invoice_number, 'INV-B')
        self.assertEqual(dups[0].confidence, 'medium')

    def test_missing_inputs_fail_to_review_not_fake_expected_amount(self):
        inv = self.invoice()
        findings = audit_batch([inv], {}, {})
        self.assertEqual([f.code for f in findings], ['MISSING_SHIPMENT_RECORD'])
        self.assertEqual(findings[0].confidence, 'low')


if __name__ == '__main__':
    unittest.main()
