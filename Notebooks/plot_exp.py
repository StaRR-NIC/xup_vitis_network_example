import os
import pickle
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plot_config.figure_type_creator import FigureTypeCreator
from pubplot.document_classes import acm_sigconf


doc = FigureTypeCreator(document_class=acm_sigconf).get_figure_type(usetex=False, usecache=True)
FIGSIZE = (3.33, 3.33/1.618)


def plot_latency_summary_list(summary_list, times, figname):
    fig, ax = plt.subplots()
    round_times = [round(x, 6) for x in times]
    ax.bxp(summary_list, positions=round_times)
    ax.set_ylabel("Latency (us)")
    ax.set_xlabel("Time (s)")
    fig.savefig(figname, pad_inches=0.01, bbox_inches="tight")


def plot_throughput_ts(inpath, outpath):
    if(not os.path.exists(inpath)):
        return
    df = pd.read_csv(inpath)
    df_intervals = df.diff()
    df_intervals["tstamp"] = df["time"]
    df_intervals["ctime"] = df_intervals["time"].cumsum()
    df_intervals = df_intervals.iloc[1:, :]
    df_intervals["tx_mpps"] = df_intervals["tx_pkts"] / (df_intervals["time"] * 1e6)
    df_intervals["rx_mpps"] = df_intervals["rx_pkts"] / (df_intervals["time"] * 1e6)

    # fig, ax = plt.subplots()
    fig, ax = doc.subfigures()
    ax.plot(df_intervals["ctime"], df_intervals["tx_mpps"], label="TX")
    ax.plot(df_intervals["ctime"], df_intervals["rx_mpps"], label="RX")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Mpps (Payload = 64B)")
    ax.set_ylim(bottom=0)
    legend = ax.legend()
    legend.set_frame_on(False)
    fig.set_tight_layout({'pad': 0.3})

    fig.savefig(outpath)
    # fig.savefig(outpath, pad_inches=0.01, bbox_inches="tight")


def plot_latency_box(inpath, outpath):
    with open(inpath, 'rb') as f:
        summary_list, times = pickle.load(f)
    # import ipdb; ipdb.set_trace()
    fig, ax = plt.subplots()
    round_times = [round(x, 1) for x in times]
    ax.bxp(summary_list, positions=round_times, showmeans=True, showfliers=False)
    round_min = round(min(times), 1)
    round_max = round(max(times), 1)
    steps = (round_max - round_min) / 8
    ax.set_xticks(np.arange(round_min, round_max, steps).round(1), np.arange(round_min, round_max, steps).round(1))
    ax.set_ylabel("Latency (us)")
    ax.set_xlabel("Time (s)")
    fig.savefig(outpath, pad_inches=0.01, bbox_inches="tight")


def plot_latency_line(inpath, outpath):
    with open(inpath, 'rb') as f:
        summary_list, times = pickle.load(f)
    # import ipdb; ipdb.set_trace()
    means = [x['mean'] for x in summary_list]
    hi = [x['whishi'] for x in summary_list]
    # fig, ax = plt.subplots()
    fig, ax = doc.subfigures()
    round_times = [round(x, 1) for x in times]
    # ax.bxp(summary_list, positions=round_times, showmeans=True, showfliers=False)
    ax.plot(round_times, means, label='Mean')
    ax.plot(round_times, hi, label='Max')
    # round_min = round(min(times), 1)
    # round_max = round(max(times), 1)
    # steps = (round_max - round_min) / 8
    # ax.set_xticks(np.arange(round_min, round_max, steps).round(1), np.arange(round_min, round_max, steps).round(1))
    # ax.set_xlim(0, 300)
    legend = ax.legend()
    legend.set_frame_on(False)
    ax.set_ylabel("Latency (us)")
    ax.set_xlabel("Time (s)")
    fig.set_tight_layout({'pad': 0.3})

    fig.savefig(outpath)
    # fig.savefig(outpath, pad_inches=0.01, bbox_inches="tight")


EXP_DIR = sys.argv[1]

throughput_without_pr = os.path.join(EXP_DIR, f"without_pr-ts.csv")
throughput_with_pr = os.path.join(EXP_DIR, f"with_pr-ts.csv")
latency_without_pr = os.path.join(EXP_DIR, 'without_pr-latency.pickle')
latency_with_pr = os.path.join(EXP_DIR, 'with_pr-latency.pickle')

plot_throughput_ts(throughput_without_pr, throughput_without_pr.replace('csv', 'pdf'))
plot_throughput_ts(throughput_with_pr, throughput_with_pr.replace('csv', 'pdf'))
plot_latency_line(latency_without_pr, latency_without_pr.replace('.pickle', '.pdf'))
plot_latency_line(latency_with_pr, latency_with_pr.replace('.pickle', '.pdf'))
