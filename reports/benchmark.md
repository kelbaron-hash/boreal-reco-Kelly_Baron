# Benchmark: Boréal Marché association rules

## 1. Environment
- Python 3.12.10, Windows
- pandas 3.1.0, numpy 2.5.4, scipy 1.18.1, mlxtend 0.25.0
- Machine: AMD Ryzen 7 7730U, 16 GB RAM, Windows
- Peak memory measured with `tracemalloc` (peak of Python and NumPy allocations). It adds some overhead, so times are slightly inflated; the same tool is used for every run.

## 2. Phase 1: loading and long-to-wide conversion

| Step | Time | Memory | Notes |
|---|---|---|---|
| Load transactions (2 columns: `TransactionID` as int32, `Item` as category) | 0.8 s | 40.0 MB | The raw file is about 318 MB on disk. Warm run, so a cold first load may take longer |
| Boolean table, Approach B (integer codes + sparse matrix + dense bool DataFrame) | 0.59 s | 93.5 MB | 1,000,000 × 98, dtype `bool`, 8,379,837 True cells |
| Boolean table, Approach A (basket lists + `TransactionEncoder`) | 3.9 s on 50,000 baskets (about 78 s extrapolated) | not measured | Sample only, then extrapolated linearly. Roughly 130 times slower than Approach B |

**Approach chosen:** Approach B (integer codes and a sparse matrix). It builds the full table in
0.59 s and 93.5 MB, while Approach A would take about 78 s on the full data (extrapolated from a
50,000-basket sample) and builds Python lists of baskets first.

**Verification of the table:** the shape, the grand total (8,379,837), every column sum
against its product's count, and the column names against the catalogue all match.

**Why loading only two columns matters:** Only `TransactionID` and `Item` are loaded, with compact types (int32 and category), giving 40.0 MB for 8,379,837 rows. A four-column load was not measured.

## 3. Phase 2: Apriori runs
| min_support | Itemsets | Rules | Time | Peak memory | Outcome |
|---|---|---|---|---|---|
| 0.05 | 191 | 282 | 2.47 s | 106.5 MB | `low_memory=True`: success. Default: projected about 7.5 GB, not run |
| 0.02 | 658 | 2,707 | 6.01 s | 109.9 MB | `low_memory=True`: success. Default: projected about 12.3 GB, not run |
| 0.01 | 2,267 | 7,817 | 14.30 s | 109.9 MB | `low_memory=True`: success. Default: projected about 23.3 GB, would exceed RAM, not run |
| 0.005 | 7,106 | 23,918 | 31.99 s | 110.0 MB | `low_memory=True`: success. Default: projected about 101.8 GB, would exceed RAM, not run |

Time and peak memory are for the `apriori` call only, measured with `tracemalloc` (which adds some
overhead). The Rules column is the number of rules with confidence of at least 0.3 from
`association_rules`.

### Memory scaling of the default setting (min_support 0.05, random samples)
| Baskets | Peak memory | Time |
|---|---|---|
| 10,000 | 75.3 MB | 0.07 s |
| 50,000 | 366.1 MB | 0.30 s |
| 100,000 | 752.7 MB | 0.55 s |

Memory grows linearly, at about 7.5 MB per 1,000 baskets.

### Projection of the default setting on 1,000,000 baskets (sample of 10,000 × 100)
| min_support | Sample peak | Projected peak | Against 16 GB RAM |
|---|---|---|---|
| 0.05 | 75.3 MB | about 7.5 GB | fits |
| 0.02 | 122.5 MB | about 12.3 GB | borderline |
| 0.01 | 232.8 MB | about 23.3 GB | exceeds RAM |
| 0.005 | 1,018.4 MB | about 101.8 GB | far exceeds RAM |

On the sample, `low_memory=True` used 1.1 MB at 0.05, against 75.3 MB for the default (both found
the same 195 itemsets). These are projections from a sample, not full-table measurements.

**The MemoryError:** with the default `low_memory=False`, Apriori tests all candidate itemsets of one
size against all baskets at once, so the memory it needs is proportional to
(baskets × candidates). My measurements show that growth is linear in the number of baskets
and increases as `min_support` falls, because more candidates survive (659, 2,327 and 7,231
itemsets on the 10,000-basket sample at 0.02, 0.01 and 0.005). Projected to 1,000,000 baskets, the
default needs about 7.5 GB at 0.05 and over 23 GB from 0.01 down, more than my 16 GB of RAM.
Setting `low_memory=True` tests candidates one at a time, which cut the peak from 75.3 MB to 1.1 MB
on the sample. [After the full runs, add what actually happened.]

## 4. Coverage
[how many of the 98 products can ever be recommended, from the final rules]


## 5. Two things this approach cannot do
1. **It cannot personalise or handle new customers and new products.** Rules depend only on
   what is in the current basket, so a new customer with an empty basket gets the popular-products
   fallback, and a product too rare to reach `min_support` (the five rarest, at about 0.08% of
   baskets) can never be recommended. Fix: add a collaborative filtering model on customer history
   and a content-based fallback using product categories.
2. **It is static and ignores context such as season, price and stock.** The rules are mined once, so
   they go stale (Phase 4 shows seasonal rules), and ranking by lift ignores margin and
   availability. Fix: re-mine per season on a schedule, and re-rank the candidate rules with a
   business score that includes margin and stock.