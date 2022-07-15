import matplotlib.pyplot as plt
import pandas as pd
import sys

assert len(sys.argv) == 2

fpath = sys.argv[1]
assert fpath[-4:] == ".csv"

df = pd.read_csv(fpath)
df_intervals = df.diff()
df_intervals["tstamp"] = df["time"]
df_intervals["ctime"] = df_intervals["time"].cumsum()
df_intervals = df_intervals.iloc[1:, :]
df_intervals["tx_mpps"] = df_intervals["tx_pkts"] / (df_intervals["time"] * 1e6)
df_intervals["rx_mpps"] = df_intervals["rx_pkts"] / (df_intervals["time"] * 1e6)

fig, ax = plt.subplots()
ax.plot(df_intervals["ctime"], df_intervals["tx_mpps"], label="TX")
ax.plot(df_intervals["ctime"], df_intervals["rx_mpps"], label="RX")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Mpps (Payload = 128B)")
ax.legend()
fig.set_tight_layout(True)

figname = fpath.replace(".csv", ".pdf")
fig.savefig(figname, pad_inches=0.01, bbox_inches="tight")

# import ipdb; ipdb.set_trace()
