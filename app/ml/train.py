import argparse
import asyncio
import os

from prophet import Prophet
from app.ml.data_access import fetch_consumption_timeseries
from app.ml.model_store import save_model


async def train_for_product(product_id: str, model_path: str, freq: str = "D"):
    df = await fetch_consumption_timeseries(product_id, freq=freq)
    if df.empty or len(df) < 10:
        raise RuntimeError("Not enough data to train model. Need at least 10 dates")

    m = Prophet()
    m.fit(df)
    save_model(m, model_path)
    return model_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--model-path", required=True,)
    parser.add_argument("--freq", default="D", help="freqency")
    args = parser.parse_args()

    asyncio.run(train_for_product(args.product_id, args.model_path, args.freq))


if __name__ == "__main__":
    main()
