import matplotlib.pyplot as plt
import pandas as pd
import sys

# TODO: Read from exp dir
#  If files don't exist. Skip plotting them.


def plot_latency_summary_list(summary_list, times, figname):
    fig, ax = plt.subplots()
    round_times = [round(x, 6) for x in times]
    ax.bxp(summary_list, positions=round_times)
    ax.set_ylabel("Latency (us)")
    ax.set_xlabel("Time (s)")
    fig.savefig(figname, pad_inches=0.01, bbox_inches="tight")

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
ax.set_ylim(bottom=0)
ax.legend()
fig.set_tight_layout(True)

figname = fpath.replace(".csv", ".pdf")
fig.savefig(figname, pad_inches=0.01, bbox_inches="tight")

# import ipdb; ipdb.set_trace()
