# Power BI Dashboard: Build Guide (final "Storyteller" design)

This guide rebuilds `powerbi/olist_cx_dashboard.pbix` from scratch: data, model, measures, design system and every page as built. Every number on the dashboard is checked against `powerbi/expected_values.csv`, computed with SQL from the same data (reconciliation).

**Files used**

| File | What it is |
|---|---|
| `data/powerbi/*.parquet` | The 6 tables to load (made by `scripts/export_powerbi.py`, git-ignored) |
| `powerbi/measures.dax` | All 51 DAX measures, ready to paste |
| `powerbi/DAX_MEASURES_NOTES.md` | What each measure means, its format, where it's used and its checked value |
| `powerbi/theme.json` | The "Storyteller" colour theme |
| `powerbi/expected_values.csv` | 48 numbers the visuals must show |
| `powerbi/screenshots/` | The four finished pages |

**Pages:** 1 Executive overview · 2 Delivery & satisfaction · 3 Sellers & categories · 4 Seller detail (hidden drill-through page).

---

## Step 0: Refresh the data files

```bash
.venv\Scripts\python.exe scripts\export_powerbi.py
```

```bash
.venv\Scripts\python.exe scripts\powerbi_expected_values.py
```

The first lists 6 files (dim_date 852 rows … fact_order_items 112,650 rows); the second ends with "All checks passed!".

---

## Step 1: Load the 6 tables

1. Power BI Desktop → **Blank report** → **Home → Get data → More… → Parquet**.
2. Paste the full path, e.g. `D:\ecommerce-customer-experience-analytics\data\powerbi\fact_orders.parquet` → **OK → Load**. Repeat for `dim_date`, `dim_customer`, `dim_seller`, `dim_product`, `fact_order_items`.
3. Table names must be exactly as above (the measures use them).

If the connector only accepts URLs, use **Get data → Blank query → Advanced Editor**:

```text
let
    Source = Parquet.Document(File.Contents("D:\ecommerce-customer-experience-analytics\data\powerbi\fact_orders.parquet"))
in
    Source
```

**Why Parquet, not CSV?** Parquet keeps column types (dates, decimals, true/false); with CSV Power BI has to guess.

---

## Step 2: Data model

**Model view** → delete auto-detected relationships not in this list, then create:

| From (many side) | To (one side) | Cross-filter |
|---|---|---|
| `fact_orders[purchase_date_key]` | `dim_date[date_key]` | Single |
| `fact_orders[customer_key]` | `dim_customer[customer_key]` | Single |
| `fact_order_items[order_id]` | `fact_orders[order_id]` | Single |
| `fact_order_items[product_key]` | `dim_product[product_key]` | Single |
| `fact_order_items[seller_key]` | `dim_seller[seller_key]` | Single |

Dates and customers filter orders; orders, products and sellers filter order lines. Everything is single-direction; the one place that needs the reverse direction (review by category or seller) uses `CROSSFILTER` inside `[Avg Review (via items)]` only.

Then:
1. **Mark `dim_date` as the date table** (Table tools → Mark as date table → `date`). Needed for MoM / YoY.
2. `dim_date[year]` → **Summarization: Don't summarize** (otherwise visuals show "Sum of year").
3. Sort `dim_date[month_name]` by `month`.
4. Hide `*_key` columns and `customer_unique_id` from report view.
5. Money columns → Currency **R$ Portuguese (Brazil)**; `late_probability` → Percentage.
6. **Calculated column** on `dim_seller` (a short, readable seller ID; unique for all 3,095 sellers):
   ```
   Seller = LEFT ( dim_seller[seller_id], 8 )
   ```

---

## Step 3: Measures

1. **Home → Enter data** → table `_Measures` → **Load**; delete its placeholder `Column1` later.
2. **Modeling → New measure** → paste each measure from `measures.dax` (51 in total) → set the format noted under it in **Measure tools**.
3. **Quick check:** cards with `[Delivered Orders]` and `[Revenue]` must show **96,470** and **R$ 13,220,249**.

---

## Step 4: Design system ("Storyteller")

**Theme:** View → Themes → Browse → `powerbi/theme.json`.

| Element | Rule |
|---|---|
| Canvas | 1920 × 1080; page background `#FAF8F4` |
| Sidebar | Dark rectangle `#0B3C49`, X 0 · W 300 · full height; "Olist CX" title, dataset note "2016–2018 · 96,470 delivered orders", **page navigator**, **Year** button slicer, **State** dropdown slicer |
| Page title | Question or finding as a headline (Segoe UI Semibold 24, `#0B3C49`) + one grey sentence (`#5C6B70`) |
| Cards and visuals | White, border `#E9E2D6`, radius 8 (from the theme) |
| Colour meaning | Teal `#0B6E7A` = normal/good · **Coral `#E4572E` = problem** (late, below threshold, worst) · light teal `#7FB7BE` = secondary |
| Insight + action | Every page ends with a key insight and an **"Action to test"** bar (light `#E9F2F3` or dark `#0B3C49`) |
| Text that contains numbers | Must be a **measure** (dynamic), never typed, so it stays true for every year and state |

**Sidebar build (once, then copy to every page):**
- **Page navigator:** Insert → Buttons → Navigator → Page navigator. Selected state: white fill, teal text; default and hover: transparent fill (the Fill toggle is global, so use transparency per state).
- **Year slicer:** `dim_date[year]`, style **Buttons**, multi-button layout; selected state white, others `#5C6B70`.
- **State slicer:** `dim_customer[state]`, style **Dropdown**.
- Copy the whole sidebar (Ctrl+C / Ctrl+V keeps positions) and **sync the slicers** across the three visible pages.

**Testing rule:** after building a page, click **All, 2016, 2017 and 2018** and check that every title, subtitle and card still tells the truth.

---

## Step 5: Page 1, "Executive overview"

**Title:** "How are sales developing?"

| Visual | Fields / measures | Notes |
|---|---|---|
| 5 KPI cards | `[Revenue]`, `[Delivered Orders]`, `[AOV]`, `[On-time %]`, `[Avg Review]` | One row under the title |
| Monthly revenue (column chart) | X `dim_date[year_month]` · Y `[Revenue]` · tooltips `[Revenue MoM %]`, `[Revenue YoY %]` | **Visual-level** filter 2017-01 … 2018-08 (a page filter would cut 2016 from the KPIs). Sort axis by `year_month` ascending. Column colour **fx → Field value → `[Bar Color]`** (peak month coral). Subtitle **fx → `[Peak Month Text]`** |
| Key insight card (dark) | `[Top State Share]` + text `[Top State Insight]` | "38.3% of revenue comes from customers in SP" |
| Top 5 states by revenue (table) | `dim_customer[state]`, `[Revenue]`, `[State Share of Total]` | Top N 5 by Revenue. Share uses `REMOVEFILTERS` (not `ALLSELECTED`, which would divide by the top 5 only). Data bars with Minimum = Number 0 |
| Monthly detail (table) | `year_month`, `[Revenue]`, `[Revenue MoM %]`, `[Revenue YoY %]` | Same visual filter; latest month first |

---

## Step 6: Page 2, "Delivery & satisfaction"

**Title:** "Late delivery costs about 2 stars per order"

| Visual | Fields / measures | Notes |
|---|---|---|
| On-time vs late comparison cards | `[Avg Review On Time]` (4.29) vs `[Avg Review Late]` (2.27); share of orders `[On-time %]` / `[Late Rate %]`; `[Low Rating Share On Time/Late]` (9.3% / 62.4%); `[Five Star Share On Time/Late]` (62.3% / 16.5%) | Teal card for on time, coral card for late; custom format `0.00" ★"` where a star is shown |
| Avg delivery days, Review gap | `[Avg Delivery Days]` (12.56), `[Review Gap]` (2.02) | |
| Average review by delivery delay (column chart) | X `fact_orders[delay_bucket]` · Y `[Avg Review]` | Colour **fx → `[Bucket Color]`** (late buckets coral). The headline chart: ratings fall from the first day late |
| Late-delivery rate by month (line) | X `year_month` · Y `[Late Rate %]` | Visual filter 2017-01 … 2018-08; linear line; subtitle **fx → `[Worst Late Month Text]`** (2018-03, 19.0%) |
| Late-delivery risk model (bar) | Y `fact_orders[risk_band]` · X `[Late Rate (test)]` | Visual filter `model_split = test` (training scores are in-sample). high 9.4% · medium 3.8% · low 0.9% |
| Predicted vs actual | `[Avg Late Risk (test)]` (3.78%), `[Late Rate (test)]` (4.42%) | Shows the model is roughly calibrated on unseen orders |
| On-time % by state (bar, worst first) | Y `dim_customer[state]` · X `[On-time %]` | Visual filter `[Delivered Orders]` ≥ 500; colour rules with **Number** (not Percent): below 0.90 coral |
| Action bar | "Warn customers early and prioritise high-risk orders, and review carriers on the worst routes first (MA, RJ). Measure the effect on reviews before rolling out." | |

---

## Step 7: Page 3, "Sellers & categories"

**Title:** Card (new) with `[Concentration Headline]` → "18% of sellers generate 80% of revenue" (32% in 2016, 20% in 2017, 21% in 2018).

| Visual | Fields / measures | Notes |
|---|---|---|
| 4 KPI cards | `[Sellers With Sales]`, `[Sellers For 80% Revenue]`, `[Top 20% Sellers Share]`, `[Top 7 Categories Share]` | 2,970 · 533 · 82.3% · 49.9% |
| Category Pareto (line and clustered column) | X `category_en` · columns `[Revenue]` · line `[Category Cumulative Share]` | Top N 15 by Revenue. `Category Cumulative Share` always divides by **all** categories, so the line ends at 76.3%, not a fake 100%. Columns **fx → `[Pareto Color]`**. Subtitle **fx → `[Pareto Subtitle]`**. Revenue data labels off; cumulative labels above, coral, no background |
| Revenue vs average review (scatter) | Values `category_en` · X `[Revenue]` · Y `[Avg Review (via items)]` · Size `[Item-level Orders]` · tooltips `[Item-level On-time %]` | Top N 20 by Revenue. Marker colour rule: review < 3.9 coral. **Format → Reference line** (newer versions; formerly the Analytics pane): constant line at `[Avg Review]`, dashed `#C9B79C`. Subtitle **fx → `[Scatter Subtitle]`**. Small text label "office_furniture" beside the coral dot. Don't put `[Late Rate %]` in the tooltip: it can't see product filters and shows 6.77% for every category |
| Top 5 sellers by revenue (table) | `dim_seller[Seller]`, `state`, `[Revenue]`, `[Item-level On-time %]`, `[Avg Review (via items)]` | Top N 5 by Revenue; totals off; data bars on Revenue; review < 4 coral. `[Seller Revenue Rank]` is left out: it ranks over `seller_id`, so with the short `Seller` column every row would show 1 |
| Worst on-time sellers (table) | `Seller`, `state`, `[Item-level Orders]`, `[Item-level On-time %]`, `[Avg Review (via items)]` | Visual filter `[Item-level Orders]` ≥ 100 (same threshold as SQL q05); sort on-time ascending; on-time < 0.85 coral; subtitle notes "(none in 2016)" |
| Key insight card | `[Worst Sellers Headline]` ("8 of 10"; "n/a" in 2016) + reference label `[SP Share Of Large Sellers]` (69%) | The base rate: 69% of sellers with 100+ orders are in SP, so "8 of 10" means the problem is individual sellers, not the region |
| Action bar | "Action to test: put the worst on-time sellers on a delivery SLA with weekly tracking, and measure whether their reviews improve over the next quarter." | |

---

## Step 8: Page 4, "Seller detail" (drill-through)

1. New page **Seller detail** → right-click the tab → **Hide page**.
2. With nothing selected: **Format → Page information → Page type: Drillthrough**. Drag `dim_seller[Seller]` into the drill-through field box (shown in the Build pane, the Filters pane or under Page information depending on the version). **Keep all filters: On** (carries the year selection).
3. Sidebar: copy the dark rectangle and "Olist CX" texts; add a **Back** button ("← Back to sellers", teal fill, Action = Back) and a "SELLER DETAIL" label. No slicers on this page.

| Visual | Fields / measures | Notes |
|---|---|---|
| Title | `[Seller Detail Title]` | "Seller 4869f7a5 · guariba, SP"; shows instructions when opened without drilling |
| 4 KPI cards | `[Revenue]`, `[Item-level Orders]`, `[Item-level On-time %]` (+ reference label `[Platform On-time %]`), `[Avg Review (via items)]` (+ reference label `[Platform Avg Review]`) | Display units **None** (exact values); on-time < 0.85 and review < 4 coral |
| Verdict strip | `[Seller Verdict]` | "On-time 89.5% vs 93.2% for all sellers (−3.7 pts) · Review 4.15★ vs 4.16★ (−0.01)" |
| Revenue by month (line) | X `year_month` · Y `[Revenue]` | Linear, markers, light gridlines. The text axis shows only months with sales |
| What this seller sells (table) | `category_en`, `[Item-level Orders]`, `[Revenue]`, `[Avg Review (via items)]` | "unknown" = product listed without a category |

**Test:** on page 3 right-click seller **1ca7077d** → Drill through → Seller detail → Revenue R$ 12,475 · 108 orders · on-time 83.33% (vs 93.23%) · review 2.39. **Ctrl+click** the Back button to return.

---

## Step 9: Reconciliation

Compare every row of `expected_values.csv` with the visual named in its `where_to_look` column (rounding in the last decimal is fine).

| If this doesn't match… | Check |
|---|---|
| Delivered Orders / Revenue | Table names; the `fact_order_items → fact_orders` relationship |
| MoM % / YoY % | Date table marked? Visual uses `dim_date` fields? |
| State numbers | `fact_orders → dim_customer` relationship; `REMOVEFILTERS` in share measures |
| Category or seller numbers | Item-level measures used, not `[Delivered Orders]` |
| Review Gap / late measures | BLANK = FALSE in DAX: undelivered orders have blank `is_late` |
| Whole page wrong after a year click | A page-level filter instead of a visual-level one |

---

## Step 10: Save and screenshot

1. **File → Save as** → `powerbi/olist_cx_dashboard.pbix`.
2. Screenshots (Win + Shift + S), All years selected: `powerbi/screenshots/01_overview.png`, `02_delivery_satisfaction.png`, `03_sellers_categories.png`, `04_seller_detail.png` (drilled into seller 4869f7a5).
3. Publishing to Power BI Service needs a work or school account; the `.pbix` + screenshots are enough for the portfolio.

Interview questions on the dashboard are in `docs/INTERVIEW_PREP.md`, section 9e.
