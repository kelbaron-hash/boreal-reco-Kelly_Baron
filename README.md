# Boréal Marché: recommendation engine with association rules
A system that answers "given what this customer already has in their basket, what should we
suggest next, and why?". Rules are mined offline with Apriori (`mlxtend`) from 1,000,000 baskets
(8,379,837 rows, 98 products) and served online by a Streamlit app that only loads the saved rules.

## Setup

**Tested on:** Python 3.12.10, Windows.

### 1. Get the project

```
git clone <your-repository-url>
cd boreal-reco-<yourname>
```

### 2. Create and activate a virtual environment

```
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

On Mac or Linux:

```
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install the dependencies

```
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Add the data

The raw transaction file is too large for Git (about 318 MB), so it is not
included in full. Place the following files in the `data/` folder:

- `transactionsdata.csv` (or `transactions.zip`): <where to download it / how it was provided>
- `products.csv`

### 5. (Optional) Re-run the mining

Open `notebooks/01_mining.ipynb`, select the `.venv` kernel, and run all
cells. This regenerates `models/rules.json` and `models/metadata.json`.
The notebook is already submitted with all outputs visible, and the
generated models are included, so this step is only needed to reproduce
the results. Mining at the lowest thresholds is memory-intensive: see
`reports/benchmark.md`.

### 6. Run the application

```
streamlit run app/streamlit_app.py
```

The app only loads `models/rules.json` and `models/metadata.json`.
It never runs Apriori.