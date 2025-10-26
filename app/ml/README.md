RTK-smart-warehouse — ML helpers
================================

This folder contains helpers to train and run a Prophet model that forecasts daily consumption
for a product.

Files:
- `data_access.py` — fetch inventory history and produce a regular consumption series (columns `ds`,`y`).
- `featurization.py` — small helper (lag features).
- `train.py` — example training script using `prophet`.
- `predictor.py` — simple wrapper to load model and predict horizon days.
- `model_store.py` — save/load models via `joblib`.

Dependencies (install into your environment):

    pip install pandas prophet joblib

Quick train example (powershell):

    python -m app.ml.train --product-id <PRODUCT_ID> --model-path app/ml/models/p_<PRODUCT_ID>.pkl

Quick predict example (python):

    from app.ml.predictor import Predictor
    p = Predictor('app/ml/models/p_<PRODUCT_ID>.pkl')
    # `series` should be a pandas DataFrame with columns ['ds','y'] — historical consumption
    preds = p.predict_from_series(series, horizon_days=30)

Notes:
- The data code expects `inventory_history` to contain `stock` snapshots with `created_at`. We compute
  consumption as positive decreases in stock between consecutive timestamps and resample to daily frequency.
- For production use consider: (1) storing models and metadata in a more robust storage (S3, DB),
  (2) adding feature drift monitoring, (3) using a worker queue for heavy batch inference.
