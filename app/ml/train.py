import argparse
import asyncio
import os
from typing import Optional


from prophet import Prophet
from app.ml.data_access import fetch_movement_timeseries
from app.ml.model_store import save_model


async def train_for_product(product_id: str, model_path: str, freq: str = "D", warehouse_id: Optional[str] = None):
    df = await fetch_movement_timeseries(product_id, warehouse_id, None, None, freq=freq)
    if df.empty or len(df) < 10:
        raise RuntimeError("Not enough data to train model. Need at least 10 dates")

    if "net_outgoing" not in df.columns:
        raise RuntimeError("Movement timeseries does not contain 'net_outgoing' column")

    train_df = df[["ds", "net_outgoing"]].rename(columns={"net_outgoing": "y"}).copy()
    train_df["y"] = train_df["y"].astype(float)

    m = Prophet()
    m.fit(train_df)
    save_model(m, model_path)
    return model_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--model-path", required=True,)
    parser.add_argument("--freq", default="D", help="freqency")
    parser.add_argument("--warehouse-id", default=None, help="optional warehouse id to filter events")
    args = parser.parse_args()

    asyncio.run(train_for_product(args.product_id, args.model_path, args.freq, args.warehouse_id))


if __name__ == "__main__":
    main()
