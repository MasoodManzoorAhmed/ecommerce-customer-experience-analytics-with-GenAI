# Power BI Dashboard: Step-by-Step Guide (Day 4)

You build the report in **Power BI Desktop**; this guide gives every click, relationship and DAX measure. At the end, every number is checked against `powerbi/expected_values.csv`, which was computed with SQL from the same data (reconciliation).

**Files used**

| File | What it is |
|---|---|
| `data/powerbi/*.parquet` | The 6 tables to load (made by `scripts/export_powerbi.py`) |
| `powerbi/measures.dax` | All 18 DAX measures, ready to paste |
| `powerbi/theme.json` | Colour theme (same palette as the notebooks) |
| `powerbi/expected_values.csv` | The numbers your visuals must show |

**You will produce:** `powerbi/olist_cx_dashboard.pbix` and PNG screenshots in `powerbi/screenshots/`.

---

## Step 0: Refresh the data files

In a terminal at the project folder:

```bash
.venv\Scripts\python.exe scripts\export_powerbi.py
```

```bash
.venv\Scripts\python.exe scripts\powerbi_expected_values.py
```

You should see 6 files listed (dim_date 852 rows ... fact_order_items 112,650 rows).

---

## Step 1: Load the 6 tables

1. Open Power BI Desktop → **Blank report**.
2. **Home → Get data → More…** → search **Parquet** → **Connect**.
3. In the path box paste the full file path, e.g.
   `D:\ecommerce-customer-experience-analytics\data\powerbi\fact_orders.parquet` → **OK** → **Load**.
4. Repeat for the other 5 files: `dim_date`, `dim_customer`, `dim_seller`, `dim_product`, `fact_order_items`.
5. In the **Data** pane (right), check the table names are exactly:
   `dim_date`, `dim_customer`, `dim_seller`, `dim_product`, `fact_orders`, `fact_order_items`.
   Rename any that differ (right-click → **Rename**). The DAX measures use these names.

**If the Parquet connector only accepts web URLs** (it varies by version), use a blank query instead: **Home → Get data → Blank query**, then **Advanced Editor**, paste and adjust the file name:

```text
let
    Source = Parquet.Document(File.Contents("D:\ecommerce-customer-experience-analytics\data\powerbi\fact_orders.parquet"))
in
    Source
```

Rename the query to the table name and **Close & Apply**. Repeat per file.

**Why Parquet, not CSV?** Parquet stores column types, so dates arrive as dates, money as decimals and true/false as booleans. With CSV, Power BI would have to guess.

---

## Step 2: Build the data model (relationships)

Open **Model view** (left sidebar, third icon). Delete any relationships Power BI auto-detected that aren't in this list, then create these by dragging the first column onto the second:

| From (many side) | To (one side) | Cardinality | Cross-filter |
|---|---|---|---|
| `fact_orders[purchase_date_key]` | `dim_date[date_key]` | Many-to-one | Single |
| `fact_orders[customer_key]` | `dim_customer[customer_key]` | Many-to-one | Single |
| `fact_order_items[order_id]` | `fact_orders[order_id]` | Many-to-one | Single |
| `fact_order_items[product_key]` | `dim_product[product_key]` | Many-to-one | Single |
| `fact_order_items[seller_key]` | `dim_seller[seller_key]` | Many-to-one | Single |

The result is a star with an **order header → order lines** link: dates and customers filter orders; orders, products and sellers filter order lines. Keeping every relationship **single-direction** avoids ambiguous filter paths. The one place we need the reverse direction (average review by category) is handled inside a single measure with `CROSSFILTER`.

**Then:**

1. **Mark the date table:** select `dim_date` → **Table tools → Mark as date table** → date column `date` → **OK**. Time-intelligence functions (MoM, YoY) need this.
2. **Sort month names:** select `dim_date[month_name]` → **Column tools → Sort by column → month**.
3. **Hide key columns** in Report view (right-click → **Hide in report view**): all `*_key` columns, `order_id` in `fact_order_items`, `customer_unique_id`. Users should slice by names, not IDs.
4. **Data types and formats** (Column tools): `price`, `order_value`, `freight_value` → Fixed decimal, Currency **R$ Portuguese (Brazil)**. `late_probability` → Percentage.

---

## Step 3: Add the measures

1. **Home → Enter data** → name the table `_Measures` → **Load**. (A dedicated table keeps measures in one place; the underscore puts it at the top.)
2. Select `_Measures` → **Home → New measure** → paste one measure from `powerbi/measures.dax` → Enter. Repeat for all 18.
3. Set each measure's format in **Measure tools** (the format is noted under each measure in the file).
4. Delete the placeholder column `Column1` in `_Measures`.

**Quick check:** put `[Delivered Orders]` and `[Revenue]` on two cards. They must show **96,470** and **R$ 13,220,249** (`expected_values.csv` rows 1-2). If not, stop and recheck Steps 1-2.

---

## Step 4: Apply the theme

**View → Themes → Browse for themes** → select `powerbi/theme.json`. Blue = main series; orange = late/negative.

---

## Step 5: Page 1, "Executive overview"

Rename the page (double-click the tab). Build:

| Visual | Fields | Notes |
|---|---|---|
| **Slicer** | `dim_date[year]` | Style: Tile |
| **Slicer** | `dim_customer[state]` | Style: Dropdown |
| **5 Cards** | `[Revenue]`, `[Delivered Orders]`, `[AOV]`, `[On-time %]`, `[Avg Review]` | One row across the top |
| **Line chart** | X: `dim_date[year_month]` · Y: `[Revenue]` · Tooltips: `[Revenue MoM %]`, `[Revenue YoY %]` | **Filter on this visual:** `year_month` from 2017-01 to 2018-08 (2016 and Sep-Oct 2018 are too thin; see the data-quality report) |
| **Table** | `dim_date[year_month]`, `[Revenue]`, `[Revenue MoM %]`, `[Revenue YoY %]` | Same visual filter as the line chart |
| **Bar chart** | Y: `dim_customer[state]` · X: `[Revenue]` · Tooltip: `[Revenue % of Total]` | Filter: **Top N = 10 by Revenue** |

**Title:** "How are sales developing?"

---

## Step 6: Page 2, "Delivery & satisfaction"

| Visual | Fields | Notes |
|---|---|---|
| **4 Cards** | `[On-time %]`, `[Late Orders]`, `[Avg Delivery Days]`, `[Review Gap]` | |
| **Column chart** | X: `fact_orders[delay_bucket]` · Y: `[Avg Review]` | Sort by `delay_bucket` ascending. **The headline chart:** reviews collapse once an order is late |
| **Bar chart** | Y: `dim_customer[state]` · X: `[On-time %]` | Sort ascending (worst first). Visual filter: `[Delivered Orders]` ≥ 500 (same rule as SQL q04) |
| **Line chart** | X: `dim_date[year_month]` · Y: `[On-time %]` | Visual filter 2017-01..2018-08: shows the Nov 2017 and Feb-Mar 2018 drops |
| **2 Cards** | `[Avg Late Risk (test)]`, `[Late Rate (test)]` | Titles: "Predicted vs actual late rate (test period)" |
| **Column chart** | X: `fact_orders[risk_band]` · Y: `[On-time %]` and `[Delivered Orders]` (tooltip) | **Visual filter:** `model_split` = test. Shows the model's risk bands separate late from on-time orders |

**Title:** "Do late deliveries hurt reviews, and where?"

---

## Step 7: Page 3, "Sellers & categories"

| Visual | Fields | Notes |
|---|---|---|
| **Line and clustered column chart** (Pareto) | X: `dim_product[category_en]` · Columns: `[Revenue]` · Line: `[Category Cumulative %]` | Sort by Revenue descending. Filter Top N = 20 by Revenue |
| **Table** (categories) | `dim_product[category_en]`, `[Revenue]`, `[Revenue % of Total]`, `[Item-level Orders]`, `[Item-level On-time %]`, `[Avg Review (via items)]` | Conditional formatting (background) on `Item-level On-time %` |
| **Table** (sellers) | `dim_seller[seller_id]`, `dim_seller[state]`, `[Seller Revenue Rank]`, `[Revenue]`, `[Item-level Orders]`, `[Item-level On-time %]` | Sort by rank. Visual filter: `[Item-level Orders]` ≥ 100 |

**Title:** "Who drives revenue, and who delivers late?"

---

## Step 8: Drill-through page, "Seller detail"

Drill-through lets a manager right-click a seller anywhere and jump to that seller's own page.

1. Add a new page, name it **Seller detail**.
2. In the **Visualizations** pane → **Drill through** section, drag `dim_seller[seller_id]` into **Add drill-through fields here**. Power BI adds a Back button automatically.
3. Add: Cards `[Revenue]`, `[Item-level Orders]`, `[Item-level On-time %]`, `[Seller Revenue Rank]` · Line chart X `dim_date[year_month]`, Y `[Revenue]` · Table `dim_product[category_en]`, `[Revenue]`, `[Item-level On-time %]`.
4. **Test it:** on page 3, right-click a seller row → **Drill through → Seller detail**. The page should show only that seller.

---

## Step 9: Check your numbers (reconciliation)

Open `powerbi/expected_values.csv` and compare each row with the visual named in `where_to_look`. Every `display` value must match (small rounding differences in the last decimal are fine).

| If this doesn't match… | Check |
|---|---|
| Delivered Orders / Revenue | Table names, the `fact_order_items → fact_orders` relationship |
| MoM % / YoY % | Date table marked? Visual uses `dim_date` fields? |
| State numbers | `fact_orders → dim_customer` relationship |
| Category or seller numbers | You used the **Item-level** measures, not `[Delivered Orders]` |
| Review Gap | You pasted the measure exactly (the BLANK-vs-FALSE detail) |

When all rows match, write "reconciled" next to Day 4 in `docs/PROGRESS.md`, or tell Claude and it'll log it.

---

## Step 10: Save and screenshot

1. **File → Save as** → `powerbi/olist_cx_dashboard.pbix`.
2. For each page, take a screenshot (Windows: **Win + Shift + S**) and save as
   `powerbi/screenshots/01_executive_overview.png`, `02_delivery_satisfaction.png`, `03_sellers_categories.png`, `04_seller_detail.png`.
3. Note: publishing to Power BI Service needs a work or school account; the `.pbix` + screenshots are enough for the portfolio.

---

## Likely interview questions (also in `docs/INTERVIEW_PREP.md`)

- *Why a star schema in Power BI?* Simple, fast filter paths; one place per definition.
- *Calculated column vs measure?* A column is computed per row at refresh and stored; a measure is computed at query time for the current filter context. KPIs like on-time % must be measures so they react to slicers.
- *Why mark a date table?* Time-intelligence functions (DATEADD, SAMEPERIODLASTYEAR) need a complete, continuous date column.
- *Why single-direction relationships?* Bi-directional filters can create ambiguous paths and slow, surprising results; `CROSSFILTER` inside one measure gives the reverse direction only where needed.
- *How do you know your dashboard is right?* Every visual was reconciled against SQL-computed expected values.
