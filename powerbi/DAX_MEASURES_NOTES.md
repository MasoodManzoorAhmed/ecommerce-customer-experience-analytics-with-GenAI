# DAX Measures: Notes

All measures in the `_Measures` table of `olist_cx_dashboard.pbix`, with the exact formula, what it means in plain English, its format, where it's used, and the value it was **checked against SQL** (`powerbi/expected_values.csv`). The copy-paste source file is `powerbi/measures.dax`.

**Total: 24 measures.** (The leftover `Column1` in `_Measures` is a placeholder from "Enter data" and can be deleted.)

## Key ideas used throughout

| Idea | Plain English |
|---|---|
| **Measure** | A formula calculated at the moment you look at it, for whatever is filtered (year, state, row of a table). |
| `CALCULATE ( X, filter )` | "Calculate X, but with this filter added or changed." |
| `fact_orders[is_delivered] = TRUE ()` | Keep delivered orders only (the project's definition for delivery and revenue metrics). |
| `DIVIDE ( a, b )` | a ÷ b, but returns blank instead of an error when b is 0. |
| `VAR … RETURN` | Store an intermediate result in a named variable, then use it. Makes long formulas readable. |
| BLANK = FALSE | In DAX a blank value counts as FALSE. Undelivered orders have a blank `is_late`, so measures always add the delivered filter. |
| Order header → lines | Dates and customers filter `fact_orders`; products and sellers filter `fact_order_items` only. That's why category/seller measures count orders through the items table. |

---

## 1. Core KPIs

### Delivered Orders
```
Delivered Orders =
CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[is_delivered] = TRUE () )
```
- **Meaning:** number of delivered orders.
- **Format:** Whole number, thousands separator.
- **Used on:** Overview KPI row.
- **Checked:** 96,470 ✅

### Revenue
```
Revenue =
CALCULATE ( SUM ( fact_order_items[price] ), fact_orders[is_delivered] = TRUE () )
```
- **Meaning:** total item price (without freight) of delivered orders. The filter on orders flows to order lines through `order_id`.
- **Format:** Currency R$ (Portuguese, Brazil).
- **Used on:** KPI row, monthly chart, both tables.
- **Checked:** R$ 13,220,248.93 ✅

### AOV (average order value)
```
AOV =
DIVIDE (
    [Revenue],
    CALCULATE ( DISTINCTCOUNT ( fact_order_items[order_id] ), fact_orders[is_delivered] = TRUE () )
)
```
- **Meaning:** revenue ÷ number of orders. Orders are counted through the items table so it stays correct when a product or seller filter is applied.
- **Format:** Currency, 2 decimals.
- **Checked:** R$ 137.04 ✅

### Late Orders
```
Late Orders =
CALCULATE ( [Delivered Orders], fact_orders[is_late] = TRUE () )
```
- **Meaning:** delivered orders that arrived after the estimated date.
- **Format:** Whole number, thousands separator.
- **Checked:** 6,534 ✅

### On-time %
```
On-time % =
DIVIDE ( [Delivered Orders] - [Late Orders], [Delivered Orders] )
```
- **Meaning:** share of delivered orders that arrived on or before the promised date.
- **Format:** Percentage, 2 decimals.
- **Checked:** 93.23% overall ✅ · MA customers 82.64% ✅

### Avg Review
```
Avg Review =
CALCULATE ( AVERAGE ( fact_orders[review_score] ), fact_orders[is_delivered] = TRUE () )
```
- **Meaning:** average star rating (1–5) of delivered orders.
- **Format:** Decimal, 2 decimals.
- **Checked:** 4.16 ✅

### Avg Delivery Days
```
Avg Delivery Days =
CALCULATE ( AVERAGE ( fact_orders[delivery_days] ), fact_orders[is_delivered] = TRUE () )
```
- **Meaning:** average days from purchase to delivery.
- **Format:** Decimal, 2 decimals.
- **Checked:** 12.56 ✅

### Review Gap
```
Review Gap =
CALCULATE ( [Avg Review], fact_orders[is_late] = FALSE () )
    - CALCULATE ( [Avg Review], fact_orders[is_late] = TRUE () )
```
- **Meaning:** how many stars higher on-time orders are rated than late orders. `[Avg Review]` already keeps delivered orders only, which protects against the BLANK = FALSE trap.
- **Format:** Decimal, 2 decimals.
- **Checked:** 2.02 ✅

---

## 2. Time intelligence (needs `dim_date` marked as the date table)

### Revenue MoM %
```
Revenue MoM % =
VAR CurrentRev = [Revenue]
VAR PrevRev = CALCULATE ( [Revenue], DATEADD ( dim_date[date], -1, MONTH ) )
RETURN DIVIDE ( CurrentRev - PrevRev, PrevRev )
```
- **Meaning:** change in revenue versus the previous month. Only meaningful when each row is a month.
- **Format:** Percentage, 2 decimals.
- **Used on:** chart tooltip, Monthly detail table (coral when negative).
- **Checked:** Aug 2018 −3.33% ✅

### Revenue YoY %
```
Revenue YoY % =
VAR CurrentRev = [Revenue]
VAR PrevYearRev = CALCULATE ( [Revenue], SAMEPERIODLASTYEAR ( dim_date[date] ) )
RETURN DIVIDE ( CurrentRev - PrevYearRev, PrevYearRev )
```
- **Meaning:** change versus the same month one year earlier.
- **Format:** Percentage, 2 decimals.
- **Checked:** Aug 2018 +51.18% ✅

---

## 3. Share, rank and Pareto

### Revenue % of Total
```
Revenue % of Total =
DIVIDE ( [Revenue], CALCULATE ( [Revenue], ALLSELECTED () ) )
```
- **Meaning:** share of whatever is currently **visible** in the visual (respects slicers **and** visual filters).
- **Format:** Percentage, 2 decimals.
- **Checked:** SP 38.34% in a full state table ✅
- **Caution:** inside a Top-N table it divides by the top N only (it showed SP 51.86%). Use **State Share of Total** there.

### State Share of Total
```
State Share of Total =
DIVIDE ( [Revenue], CALCULATE ( [Revenue], REMOVEFILTERS ( dim_customer[state] ) ) )
```
- **Meaning:** a state's share of revenue across **all** states, even when the table shows only the top 5. The year slicer still applies.
- **Format:** Percentage, 2 decimals.
- **Used on:** "Top 5 states by revenue" table (as "Share of revenue", with data bars from 0).
- **Checked:** SP 38.34% ✅ · RJ 13.31% ✅

### Seller Revenue Rank
```
Seller Revenue Rank =
IF (
    HASONEVALUE ( dim_seller[seller_id] ),
    RANKX ( ALLSELECTED ( dim_seller[seller_id] ), [Revenue], , DESC, DENSE )
)
```
- **Meaning:** a seller's position by revenue (1 = highest) among the sellers currently selected. Blank on total rows.
- **Format:** Whole number.
- **Checked:** rank 1 seller R$ 226,987.93 ✅

### Category Cumulative %
```
Category Cumulative % =
VAR CurrentRev = [Revenue]
VAR Cats =
    ADDCOLUMNS ( ALLSELECTED ( dim_product[category_en] ), "@rev", [Revenue] )
RETURN
    DIVIDE ( SUMX ( FILTER ( Cats, [@rev] >= CurrentRev ), [@rev] ), SUMX ( Cats, [@rev] ) )
```
- **Meaning:** running share of revenue from the biggest category down to this one (the Pareto line).
- **Format:** Percentage, 2 decimals.
- **Checked:** 7th category (housewares) 49.87% ✅

---

## 4. Item-level measures (for product and seller visuals)

### Item-level Orders
```
Item-level Orders =
CALCULATE ( DISTINCTCOUNT ( fact_order_items[order_id] ), fact_orders[is_delivered] = TRUE () )
```
- **Meaning:** delivered orders containing the selected category or seller (an order with two categories counts for both).
- **Format:** Whole number, thousands separator.

### Item-level On-time %
```
Item-level On-time % =
VAR LateOrders =
    CALCULATE ( DISTINCTCOUNT ( fact_order_items[order_id] ), fact_orders[is_late] = TRUE () )
RETURN 1 - DIVIDE ( LateOrders, [Item-level Orders] )
```
- **Meaning:** on-time rate for a category or seller (same rule as SQL q05/q06).
- **Format:** Percentage, 2 decimals.
- **Checked:** office_furniture 91.95% ✅

### Avg Review (via items)
```
Avg Review (via items) =
CALCULATE (
    [Avg Review],
    CROSSFILTER ( fact_order_items[order_id], fact_orders[order_id], BOTH )
)
```
- **Meaning:** average review for a category or seller. `CROSSFILTER … BOTH` lets the product/seller filter flow back to orders **for this measure only**, instead of making the whole relationship two-way.
- **Format:** Decimal, 2 decimals.
- **Checked:** health_beauty 4.23 ✅

---

## 5. Late-delivery model

### Avg Late Risk (test)
```
Avg Late Risk (test) =
CALCULATE ( AVERAGE ( fact_orders[late_probability] ), fact_orders[model_split] = "test" )
```
- **Meaning:** average predicted late probability for test-period orders (Apr–Aug 2018). Training-period scores are excluded because they're in-sample.
- **Format:** Percentage, 2 decimals.
- **Checked:** 3.78% ✅

### Late Rate (test)
```
Late Rate (test) =
DIVIDE (
    CALCULATE ( [Late Orders], fact_orders[model_split] = "test" ),
    CALCULATE ( [Delivered Orders], fact_orders[model_split] = "test" )
)
```
- **Meaning:** actual late rate in the same test period, to compare with the prediction.
- **Format:** Percentage, 2 decimals.
- **Checked:** 4.42% ✅ · by risk band (test): high 90.64% on time, low 99.06% on time ✅

---

## 6. Dynamic storytelling (Overview page)

### Top State
```
Top State =
CONCATENATEX ( TOPN ( 1, VALUES ( dim_customer[state] ), [Revenue] ), dim_customer[state], ", " )
```
- **Meaning:** the customer state with the most revenue in the current selection.
- **Checked:** SP ✅

### Top State Share
```
Top State Share =
VAR TopState = TOPN ( 1, VALUES ( dim_customer[state] ), [Revenue] )
RETURN DIVIDE ( CALCULATE ( [Revenue], TopState ), [Revenue] )
```
- **Meaning:** that state's share of revenue.
- **Format:** Percentage, 1 decimal.
- **Used on:** "Key insight" card (big number).
- **Checked:** 38.3% ✅ (2017: 35.9% · 2018: 40.4%)

### Top State Insight
```
Top State Insight =
FORMAT ( [Top State Share], "0.0%" ) & " of revenue comes from customers in " & [Top State]
```
- **Meaning:** the sentence under the big number; rewrites itself when the slicers change.
- **Used on:** "Key insight" card (reference label).

### Bar Color
```
Bar Color =
VAR ThisRev = [Revenue]
VAR MaxRev = MAXX ( ALLSELECTED ( dim_date[year_month] ), [Revenue] )
RETURN IF ( ThisRev = MaxRev, "#E4572E", "#0B6E7A" )
```
- **Meaning:** coral for the highest month currently shown, teal for the rest.
- **Used on:** Monthly revenue chart → Columns → Color → **fx** → Field value.
- **Checked:** all years → 2017-11 ✅ · 2018 → 2018-05 ✅

### Peak Month Text
```
Peak Month Text =
VAR PeakMonth = TOPN ( 1, VALUES ( dim_date[year_month] ), [Revenue] )
RETURN
    "Peak month: " & CONCATENATEX ( PeakMonth, dim_date[year_month] )
        & " (R$ " & FORMAT ( MAXX ( PeakMonth, [Revenue] ), "#,0" ) & ")"
```
- **Meaning:** chart subtitle naming the peak month and its revenue; always agrees with the coral bar.
- **Used on:** Monthly revenue chart → Title → Subtitle → **fx** → Field value.
- **Checked:** "Peak month: 2017-11 (R$ 987,648)" ✅ · 2018: 2018-05 (R$ 977,545) ✅

---

## Lessons worth telling in an interview

1. **Reconciliation first:** every measure was checked against SQL-computed values before any report page was built.
2. **Top-N pitfall:** a "% of total" inside a Top-5 table showed SP at 51.86% instead of 38.34%, because `ALLSELECTED` divided by the visible five. Fixed with `REMOVEFILTERS(dim_customer[state])`.
3. **BLANK = FALSE:** filters on `is_late` are always combined with the delivered filter.
4. **Single-direction model:** `CROSSFILTER` is used inside one measure rather than a two-way relationship.
5. **Data-driven design:** bar colours, the subtitle and the insight sentence are measures, so they stay correct for any slicer selection.
