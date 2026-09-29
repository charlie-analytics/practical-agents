# Payment Reconciler

Match payment exports to invoices without moving money. Useful for research operations, freelance billing and examining machine-payment records after they have been normalized into the input schema.

```bash
python3 -m agentkit payment-reconciler --demo
python3 -m agentkit payment-reconciler --workspace examples --model YOUR_INSTALLED_MODEL \
  --task "Reconcile invoices.csv and payments.csv as of 2026-09-29. Explain overdue balances and every exception. Keep currencies separate."
```

Invoice headers: `invoice_id,currency,amount,due_date`.

Payment headers: `payment_id,invoice_id,currency,amount,status`.

Use non-empty unique invoice IDs, ISO dates, uppercase three-letter currency codes and decimal amounts. A payment counts only if its ID is unique, its invoice exists, currency matches, amount is positive, and status is exactly `settled`. Every occurrence of a duplicated payment ID is excluded pending review; this deliberately avoids choosing an arbitrary winner. Pending payments, unknown invoices and currency mismatches become exceptions.

Partial payments are supported. Overpayments are flagged separately and do not offset another invoice. Balances use Python Decimal; no FX conversion, tolerance, tax inference, fee allocation, refunds or chargebacks are implemented. A supplied `settled` label is accepted as input, not independently verified with a bank or chain. Use only records available by the requested reference date; the schema does not contain settlement timestamps, so this is not a historical reconstruction tool.

Tools: `list_files`, `read_excerpt`, `reconcile_payments`.
