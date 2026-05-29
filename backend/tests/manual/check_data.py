import pandas as pd
import qlib
from qlib.data import D

qlib.init(provider_uri="db/qlib_data")
pred = pd.read_pickle("research/data_adapter/qlib_data/predictions/pred.pkl")
pred_instruments = pred.index.get_level_values("instrument").unique().tolist()

print(f"Total instruments in pred.pkl: {len(pred_instruments)}")
print(f"Sample instruments from pred.pkl: {pred_instruments[:10]}")

# Check if these instruments have data in qlib
available_instruments = D.list_instruments(D.instruments("all"), as_list=True)
print(f"Total instruments in Qlib provider: {len(available_instruments)}")

missing = [ins for sym in pred_instruments if (ins := sym) not in available_instruments]
print(f"Missing instruments: {len(missing)}")

if len(available_instruments) > 0:
    print(f"Sample available instruments: {available_instruments[:10]}")

# Check data for one instrument from pred.pkl
if pred_instruments:
    test_ins = pred_instruments[0]
    df = D.features([test_ins], ["$close"], start_time="2025-01-01", end_time="2025-01-10")
    print(f"Data for {test_ins} in 2025: \n{df}")
