# MyFatoorah Test Cards & Test Environment

## Test API Token (Public — safe to share)
```
rLtt6JWvbUHDDhsZnfpAhpYk4dxYDQkbcPTyGaKp2hyMB3Eq1uNQ5GKGB35E4R62Gad5UBtSHQzIUzd7VXMxZ3DkuKr6Lhxl5fqkVyaC9pSXkJITJINdxDVyiRvJtCb1yRlRX2sXMjVjKl
```
Source: https://docs.myfatoorah.com/docs/test-cards  
Routes to: `apitest.myfatoorah.com`

---

## Test Cards

### VISA / Mastercard — SUCCESS
| Field | Value |
|-------|-------|
| Card Number | 4111 1111 1111 1111 |
| Expiry | Any future date (e.g. 12/26) |
| CVV | Any 3 digits (e.g. 123) |
| Name | Any name |
| 3DS Password | 1234 |

### VISA / Mastercard — FAIL (insufficient funds)
| Field | Value |
|-------|-------|
| Card Number | 4000 0000 0000 0002 |
| Expiry | Any future date |
| CVV | Any 3 digits |

### KNET (Kuwait) — TEST
- Use the KNET test portal that appears automatically in test mode
- Payment ID: `0`
- Result: Select "CAPTURED" to simulate success, "NOT CAPTURED" for failure

### Mada (Saudi Arabia)
| Field | Value |
|-------|-------|
| Card Number | 4111 1111 1111 1111 |
| Use SA test token | (different token for SA) |

---

## How to Test in Odoo

1. Install module — test token is pre-loaded automatically
2. Go to **Accounting → Configuration → Payment Providers → MyFatoorah**
3. State should show **Test Mode** ✓
4. Go to your website/eCommerce → add product to cart → checkout
5. Select MyFatoorah → use test card above
6. After payment, verify:
   - Transaction state = **Done** in payment.transaction
   - Invoice status = **Paid**
   - Sales order status = **Confirmed**

## Switching to Live

1. Get your live API token from https://portal.myfatoorah.com → Settings → API
2. In Odoo: Payment Providers → MyFatoorah → Credentials tab
3. Replace token with your live token
4. Set **State** to **Enabled**
5. Check **Published** so customers can see it

⚠️ Never use the test token on a live database.
