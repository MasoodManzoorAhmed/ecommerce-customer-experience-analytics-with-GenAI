# DAX Measures: Notes

All measures in the `_Measures` table of `olist_cx_dashboard.pbix`, with the exact formula, what it means in plain English, its format, where it's used, and the value it was **checked against SQL** (`powerbi/expected_values.csv`). The copy-paste source file is `powerbi/measures.dax`.

**Total: 51 measures** (plus the calculated column `dim_seller[Seller] = LEFT ( dim_seller[seller_id], 8 )`, a short ID that is unique for all 3,095 sellers). (The leftover `Column1` in `_Measures` is a placeholder from "Enter data" and can be deleted.)

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

## 7. Delivery & satisfaction page

### Late Rate %
```
Late Rate % =
DIVIDE ( [Late Orders], [Delivered Orders] )
```
- **Meaning:** share of delivered orders that arrived late (the opposite of On-time %).
- **Format:** Percentage, 2 decimals.
- **Used on:** late-rate-by-month line, model risk panel.
- **Checked:** 6.77% overall ✅ · Nov 2017 12.40% ✅ · Mar 2018 18.96% ✅ · test high-risk band 9.36% ✅ · low-risk band 0.94% ✅

### Avg Review On Time / Avg Review Late
```
Avg Review On Time =
CALCULATE ( [Avg Review], fact_orders[is_late] = FALSE () )

Avg Review Late =
CALCULATE ( [Avg Review], fact_orders[is_late] = TRUE () )
```
- **Meaning:** average stars for on-time vs late orders (the two comparison cards).
- **Format:** Decimal, 2 decimals.
- **Checked:** 4.29 ✅ · 2.27 ✅

### Low Rating Share
```
Low Rating Share =
VAR Reviewed =
    CALCULATE (
        COUNTROWS ( fact_orders ),
        fact_orders[is_delivered] = TRUE (),
        NOT ISBLANK ( fact_orders[review_score] )
    )
VAR LowRated =
    CALCULATE (
        COUNTROWS ( fact_orders ),
        fact_orders[is_delivered] = TRUE (),
        NOT ISBLANK ( fact_orders[review_score] ),
        fact_orders[review_score] <= 2
    )
RETURN DIVIDE ( LowRated, Reviewed )
```
- **Meaning:** share of reviewed delivered orders rated 1 or 2 stars.
- **Why `NOT ISBLANK`:** in DAX a blank counts as 0, so `review_score <= 2` would also count orders with **no review**. The extra condition keeps only real ratings.
- **Format:** Percentage, 1 decimal.

### Five Star Share
```
Five Star Share =
VAR Reviewed =
    CALCULATE (
        COUNTROWS ( fact_orders ),
        fact_orders[is_delivered] = TRUE (),
        NOT ISBLANK ( fact_orders[review_score] )
    )
VAR FiveStar =
    CALCULATE (
        COUNTROWS ( fact_orders ),
        fact_orders[is_delivered] = TRUE (),
        fact_orders[review_score] = 5
    )
RETURN DIVIDE ( FiveStar, Reviewed )
```
- **Meaning:** share of reviewed delivered orders rated 5 stars.
- **Format:** Percentage, 1 decimal.

### On-time and late versions (for the comparison cards)
```
Low Rating Share On Time = CALCULATE ( [Low Rating Share], fact_orders[is_late] = FALSE () )
Low Rating Share Late    = CALCULATE ( [Low Rating Share], fact_orders[is_late] = TRUE () )
Five Star Share On Time  = CALCULATE ( [Five Star Share], fact_orders[is_late] = FALSE () )
Five Star Share Late     = CALCULATE ( [Five Star Share], fact_orders[is_late] = TRUE () )
```
- **Checked:** 1-2★ on time 9.27% ✅ · late 62.42% ✅ · 5★ on time 62.27% ✅ · late 16.53% ✅

### Bucket Color
```
Bucket Color =
IF (
    LEFT ( SELECTEDVALUE ( fact_orders[delay_bucket] ), 1 ) IN { "3", "4", "5", "6" },
    "#E4572E",
    "#0B6E7A"
)
```
- **Meaning:** coral for the late delay buckets (3 = 1-3 days late … 6 = 15+ days late), teal for early / on the day.
- **Used on:** "Average review by delivery delay" chart → Columns → Color → **fx** → Field value.
- **Checked (chart values):** bucket 3: 1-3 days late 3.29 ✅ · bucket 6: 15+ days late 1.72 ✅

### Worst Late Month Text
```
Worst Late Month Text =
VAR WorstMonth = TOPN ( 1, VALUES ( dim_date[year_month] ), [Late Rate %] )
RETURN
    "Worst month: " & CONCATENATEX ( WorstMonth, dim_date[year_month] )
        & " (" & FORMAT ( MAXX ( WorstMonth, [Late Rate %] ), "0.0%" ) & " late)"
```
- **Meaning:** subtitle naming the month with the highest late rate in the current selection.
- **Used on:** "Late rate by month" chart → Title → Subtitle → **fx** → Field value.
- **Checked:** "Worst month: 2018-03 (19.0% late)" ✅

---

## 8. Sellers & categories page

### Sellers With Sales
```
Sellers With Sales =
CALCULATE ( DISTINCTCOUNT ( fact_order_items[seller_key] ), fact_orders[is_delivered] = TRUE () )
```
- **Meaning:** sellers with at least one delivered sale in the current selection.
- **Format:** Whole number. **Checked:** 2,970 ✅

### Sellers For 80% Revenue
```
Sellers For 80% Revenue =
VAR SellerRev =
    FILTER ( ADDCOLUMNS ( VALUES ( dim_seller[seller_key] ), "@rev", [Revenue] ), [@rev] > 0 )
VAR Total = SUMX ( SellerRev, [@rev] )
VAR WithCum =
    ADDCOLUMNS (
        SellerRev,
        "@cumBefore", SUMX ( FILTER ( SellerRev, [@rev] > EARLIER ( [@rev] ) ), [@rev] )
    )
RETURN COUNTROWS ( FILTER ( WithCum, [@cumBefore] < 0.8 * Total ) )
```
- **Meaning:** the fewest sellers, biggest first, needed to reach 80% of revenue. For each seller it adds up the revenue of all bigger sellers (`@cumBefore`); a seller is needed if the total *before* them is still under 80%.
- **Format:** Whole number. **Checked:** 533 ✅ (same as SQL q09)

### Sellers For 80% Share
```
Sellers For 80% Share =
DIVIDE ( [Sellers For 80% Revenue], [Sellers With Sales] )
```
- **Meaning:** those sellers as a share of all sellers: the "18%" in "18% of sellers generate 80% of revenue".
- **Format:** Percentage, 1 decimal. **Checked:** 533 / 2,970 = 17.9% ✅

### Top 20% Sellers Share
```
Top 20% Sellers Share =
VAR SellerRev =
    FILTER ( ADDCOLUMNS ( VALUES ( dim_seller[seller_key] ), "@rev", [Revenue] ), [@rev] > 0 )
VAR N = MAX ( 1, ROUND ( 0.2 * COUNTROWS ( SellerRev ), 0 ) )
VAR TopSellers = TOPN ( N, SellerRev, [@rev], DESC, dim_seller[seller_key], ASC )
RETURN DIVIDE ( SUMX ( TopSellers, [@rev] ), SUMX ( SellerRev, [@rev] ) )
```
- **Meaning:** revenue share of the biggest 20% of sellers (594 of 2,970). `seller_key` is a tie-breaker so exactly N sellers are taken.
- **Format:** Percentage, 1 decimal. **Checked:** 82.29% ✅

### Top 7 Categories Share
```
Top 7 Categories Share =
VAR Cats = ADDCOLUMNS ( VALUES ( dim_product[category_en] ), "@rev", [Revenue] )
RETURN DIVIDE ( SUMX ( TOPN ( 7, Cats, [@rev], DESC ), [@rev] ), SUMX ( Cats, [@rev] ) )
```
- **Meaning:** revenue share of the 7 biggest categories (of 74).
- **Format:** Percentage, 1 decimal. **Checked:** 49.87% ✅

### Worst Sellers Headline
```
Worst Sellers Headline =
VAR Eligible =
    FILTER (
        ADDCOLUMNS (
            VALUES ( dim_seller[seller_key] ),
            "@orders", [Item-level Orders],
            "@ontime", [Item-level On-time %],
            "@state", CALCULATE ( SELECTEDVALUE ( dim_seller[state] ) )
        ),
        [@orders] >= 100
    )
VAR Worst = TOPN ( 10, Eligible, [@ontime], ASC, dim_seller[seller_key], ASC )
VAR InSP = COUNTROWS ( FILTER ( Worst, [@state] = "SP" ) ) + 0
RETURN
    IF ( COUNTROWS ( Eligible ) = 0, "n/a", InSP & " of " & COUNTROWS ( Worst ) )
```
- **Meaning:** how many of the 10 worst on-time sellers (100+ delivered orders) are based in São Paulo, e.g. "8 of 10". Updates with the year slicer.
- **Why the tie-breaker:** two sellers tie at #10 (87.07%, 147 orders each). Without `dim_seller[seller_key]` as a second sort key, `TOPN` returns both (11 rows) and the card would read "9 of 11".
- **Empty case:** in 2016 no seller has 100+ orders, so the first version showed a broken "0 of". It now returns "n/a".
- **Used on:** Key insight card (Sellers page). **Checked:** 8 of 10 (all years), 9 of 10 (2017), 8 of 10 (2018) ✅

### SP Share Of Large Sellers
```
SP Share Of Large Sellers =
VAR Eligible =
    FILTER (
        ADDCOLUMNS (
            VALUES ( dim_seller[seller_key] ),
            "@orders", [Item-level Orders],
            "@state", CALCULATE ( SELECTEDVALUE ( dim_seller[state] ) )
        ),
        [@orders] >= 100
    )
RETURN DIVIDE ( COUNTROWS ( FILTER ( Eligible, [@state] = "SP" ) ), COUNTROWS ( Eligible ) )
```
- **Meaning:** the **base rate**: what share of all sellers with 100+ orders are in SP. "8 of 10 worst are in SP" only means something next to this number.
- **Format:** Percentage, 0 decimals. **Used on:** Key insight card → reference label.
- **Checked:** 69.05% all years (145 of 210); 70.97% in 2017 and 2018 (66 of 93) ✅

### Category Cumulative Share
```
Category Cumulative Share =
VAR CurrentRev = [Revenue]
VAR AllCats =
    ADDCOLUMNS (
        CALCULATETABLE ( VALUES ( dim_product[category_en] ), REMOVEFILTERS ( dim_product[category_en] ) ),
        "@rev", [Revenue]
    )
RETURN
    DIVIDE ( SUMX ( FILTER ( AllCats, [@rev] >= CurrentRev ), [@rev] ), SUMX ( AllCats, [@rev] ) )
```
- **Meaning:** the Pareto line, measured against **all 74 categories** even when the chart shows only the top 15.
- **Why not Category Cumulative %:** that one uses `ALLSELECTED`, which inside a Top-15 chart sees only 15 categories, so its line would wrongly reach 100% at the 15th.
- **Format:** Percentage, 1 decimal. **Checked:** 7th 49.87% ✅ · 15th 76.3% ✅ (SQL q03)

### Pareto Color
```
Pareto Color =
IF ( [Category Cumulative Share] <= 0.5, "#0B6E7A", "#7FB7BE" )
```
- **Meaning:** dark teal for the categories that make up the first half of revenue (the top 7), light teal for the rest.
- **Used on:** Pareto chart → Columns → Color → **fx** → Field value.

---

### Concentration Headline
```
Concentration Headline =
FORMAT ( [Sellers For 80% Share], "0%" ) & " of sellers generate 80% of revenue"
```
- **Meaning:** the page title as a measure, so it stays true when a year is selected. The typed title said "18%" in every year.
- **Used on:** page title (Card (new) callout, or a button/shape text with fx). **Checked:** 18% all · 32% 2016 · 20% 2017 · 21% 2018 ✅

### Pareto Subtitle
```
Pareto Subtitle =
CALCULATE (
    VAR Cats = COUNTROWS ( FILTER ( VALUES ( dim_product[category_en] ), [Revenue] > 0 ) )
    RETURN "Top 7 of " & Cats & " categories make " & FORMAT ( [Top 7 Categories Share], "0.0%" ) & " of revenue",
    REMOVEFILTERS ( dim_product[category_en] )
)
```
- **Why `REMOVEFILTERS`:** the chart has a Top-15 visual filter on category; removing category filters makes sure the count and share are over all categories.
- **Why "0.0%":** 49.87% would round to "50%" and overstate "half".
- **Used on:** Pareto chart → Subtitle → fx. **Checked:** 74 / 49.9% all · 30 / 65.6% 2016 · 73 / 49.9% 2017 · 73 / 52.1% 2018 ✅

### Scatter Subtitle
```
Scatter Subtitle =
CALCULATE (
    VAR Cats =
        ADDCOLUMNS ( VALUES ( dim_product[category_en] ), "@rev", [Revenue], "@rv", [Avg Review (via items)] )
    VAR Top20 = TOPN ( 20, Cats, [@rev], DESC, dim_product[category_en], ASC )
    VAR Lowest = TOPN ( 1, Top20, [@rv], ASC, dim_product[category_en], ASC )
    RETURN
        "Lowest-rated of the top 20: " & MAXX ( Lowest, dim_product[category_en] ) & " ("
            & FORMAT ( MAXX ( Lowest, [@rv] ), "0.00" ) & "★) vs " & FORMAT ( [Avg Review], "0.00" )
            & "★ overall. Hover a bubble for details.",
    REMOVEFILTERS ( dim_product[category_en] )
)
```
- **Meaning:** names the weakest of the 20 biggest categories for whatever is selected.
- **Pattern:** build a small table in memory (`ADDCOLUMNS`), take the top 20 by revenue (`TOPN`), then the 1 lowest review from those, and read its name and value with `MAXX`.
- **Used on:** scatter → Subtitle → fx. **Checked:** office_furniture in every view: 3.64 vs 4.16 (all) · 1.60 vs 4.00 (2016) · 3.66 vs 4.17 (2017) · 3.64 vs 4.14 (2018) ✅

## 9. Seller detail (drill-through page)

### Seller Detail Title
```
Seller Detail Title =
IF (
    HASONEVALUE ( dim_seller[Seller] ),
    "Seller " & SELECTEDVALUE ( dim_seller[Seller] ) & " · "
        & SELECTEDVALUE ( dim_seller[city] ) & ", " & SELECTEDVALUE ( dim_seller[state] ),
    "Right-click a seller on the Sellers page → Drill through → Seller detail"
)
```
- **Meaning:** page title naming the seller you drilled into. `SELECTEDVALUE` returns the value only when exactly one seller is in the filter, and `HASONEVALUE` swaps the broken "Seller · ," for an instruction when the page is opened without drilling.
- **Checked:** 1ca7077d → "Seller 1ca7077d · santana de parnaiba, SP" ✅

### Platform On-time % / Platform Avg Review
```
Platform On-time % = CALCULATE ( [Item-level On-time %], REMOVEFILTERS ( dim_seller ) )
Platform Avg Review = CALCULATE ( [Avg Review (via items)], REMOVEFILTERS ( dim_seller ) )
```
- **Meaning:** the same measures for **all** sellers, as a benchmark on the seller's cards. `REMOVEFILTERS ( dim_seller )` drops the drill-through seller filter but keeps the year slicer.
- **Used on:** reference labels on the drill-through cards. **Checked:** Platform On-time % 93.23% (all years) ✅

### Seller Verdict
```
Seller Verdict =
VAR OT = [Item-level On-time %]
VAR POT = [Platform On-time %]
VAR R = [Avg Review (via items)]
VAR PR = [Platform Avg Review]
RETURN
    "On-time " & FORMAT ( OT, "0.0%" ) & " vs " & FORMAT ( POT, "0.0%" ) & " for all sellers ("
        & FORMAT ( ( OT - POT ) * 100, "+0.0;-0.0" ) & " pts) · Review " & FORMAT ( R, "0.00" )
        & "★ vs " & FORMAT ( PR, "0.00" ) & "★ (" & FORMAT ( R - PR, "+0.00;-0.00" ) & ")"
```
- **Meaning:** one sentence comparing the drilled seller with all sellers. The format `"+0.0;-0.0"` always shows the sign, so "−9.9 pts" reads instantly as worse.
- **"pts" = percentage points:** 83.3% − 93.2% is 9.9 *points*, not 9.9 *percent*.
- **Used on:** insight strip on Seller detail. **Checked:** 1ca7077d → On-time 83.3% vs 93.2% (−9.9 pts) · Review 2.39★ vs 4.16★ ✅

## Lessons worth telling in an interview

1. **Reconciliation first:** every measure was checked against SQL-computed values before any report page was built.
2. **Top-N pitfall:** a "% of total" inside a Top-5 table showed SP at 51.86% instead of 38.34%, because `ALLSELECTED` divided by the visible five. Fixed with `REMOVEFILTERS(dim_customer[state])`.
3. **BLANK = FALSE (and BLANK = 0):** filters on `is_late` are always combined with the delivered filter, and rating shares add `NOT ISBLANK` so orders without a review aren't counted as 1-star.
4. **Single-direction model:** `CROSSFILTER` is used inside one measure rather than a two-way relationship.
5. **TOPN ties:** `TOPN` returns every row tied at the cut-off, so a "top 10" can be 11 rows; a unique second sort key (`seller_key`) makes it exact.
6. **Data-driven design:** bar colours, the subtitle and the insight sentence are measures, so they stay correct for any slicer selection.
