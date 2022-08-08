# %%
import pickle
import json
import os
import platform
import subprocess
import time
from turtle import position

import matplotlib.cbook as cbook
import matplotlib.pyplot as plt
import pandas as pd
import pynq
from distributed.client import Client
from distributed.deploy.ssh import SSHCluster
from distributed.variable import Variable
from scipy import stats

from vnx_utils import *

# %%

# REMOTE
REMOTE_NAME = "neptune3"
PR_SCRIPT_PATH = ("/home/ubuntu/Projects/StaRR-NIC/"
                  "anup-starrnic-shell/script/replace_pr_util.sh")
SETUP_REGISTER_SCRIPT_PATH = ("/home/ubuntu/Projects/StaRR-NIC/"
                              "anup-starrnic-shell/script/setup_p4_reg_util.sh")

# # AXIS SWITCH
# BITSTREAM_1 = (
#     "/datadrive/StaRR-NIC/starrnic-data/bitfiles/dfx-shorted-p4-reg/"
#     "box_250mhz_inst_stream_switch_dfx_inst_partition1_rm_intf_inst"
#     "_pkt_size_counter_partial.bit"
# )
# BITSTREAM_2 = (
#     "/datadrive/StaRR-NIC/starrnic-data/bitfiles/dfx-shorted-p4-reg/"
#     "box_250mhz_inst_stream_switch_dfx_inst_partition1_rm_intf_inst"
#     "_pkt_size_counter5_partial.bit"
# )
# PROBES_PATH = (
#     "/datadrive/StaRR-NIC/starrnic-data/bitfiles/dfx-shorted-p4-reg"
#     "open_nic_shell_counter.ltx"
# )

# # AXIS ARB MUX
# BITSTREAM_1 = (
#     "/home/ubuntu/Projects/StaRR-NIC/anup-starrnic-shell/"
#     "build/au280_shorted-p4-bypass-ila/open_nic_shell/"
#     "open_nic_shell.runs/impl_1/"
#     "box_250mhz_inst_stream_switch_dfx_inst_partition1_"
#     "rm_intf_inst_pkt_size_counter_partial.bit")
# BITSTREAM_2 = (
#     "/home/ubuntu/Projects/StaRR-NIC/anup-starrnic-shell/"
#     "build/au280_shorted-p4-bypass-ila/open_nic_shell/"
#     "open_nic_shell.runs/child_0_impl_1/"
#     "box_250mhz_inst_stream_switch_dfx_inst_partition1_"
#     "rm_intf_inst_pkt_size_counter5_partial.bit")
# PROBES_PATH = (
#     "/home/ubuntu/Projects/StaRR-NIC/anup-starrnic-shell/"
#     "build/au280_shorted-p4-bypass-ila/open_nic_shell/"
#     "open_nic_shell.runs/impl_1/open_nic_shell.ltx")

# # AXIS DEMUX
# BITSTREAM_1 = (
#     "/home/ubuntu/Projects/StaRR-NIC/anup-starrnic-shell/"
#     "build/au280_shorted-p4-bypass-demux/open_nic_shell/"
#     "open_nic_shell.runs/child_0_impl_1/"
#     "box_250mhz_inst_stream_switch_dfx_inst_partition1"
#     "_rm_intf_inst_pkt_size_counter5_partial.bit")
# BITSTREAM_2 = (
#     "/home/ubuntu/Projects/StaRR-NIC/anup-starrnic-shell/"
#     "build/au280_shorted-p4-bypass-demux/open_nic_shell/"
#     "open_nic_shell.runs/impl_1/"
#     "box_250mhz_inst_stream_switch_dfx_inst_partition1"
#     "_rm_intf_inst_pkt_size_counter_partial.bit")
# PROBES_PATH = ""

# DISABLE_RM
BITSTREAM_1 = (
    "/home/ubuntu/Projects/StaRR-NIC/anup-starrnic-shell/"
    "build/au280_shorted-p4-bypass-disable_rm/open_nic_shell/"
    "open_nic_shell.runs/child_0_impl_1/"
    "box_250mhz_inst_stream_switch_dfx_inst_partition1"
    "_rm_intf_inst_pkt_size_counter5_partial.bit")
BITSTREAM_2 = (
    "/home/ubuntu/Projects/StaRR-NIC/anup-starrnic-shell/"
    "build/au280_shorted-p4-bypass-disable_rm/open_nic_shell/"
    "open_nic_shell.runs/impl_1/"
    "box_250mhz_inst_stream_switch_dfx_inst_partition1"
    "_rm_intf_inst_pkt_size_counter_partial.bit")
PROBES_PATH = ""

BOARD_NAME = "au280"


# LOCAL
XCLBIN = xclbin = (
    "/home/ubuntu/Projects/StaRR-NIC/"
    "xup_vitis_network_example/"
    "benchmark.intf3.xilinx_u280_xdma_201920_3/"
    "vnx_benchmark_if3.xclbin")

# PACKET HEADERS
ip_w0_0, ip_w0_1 = '10.0.0.47', '10.0.0.45'
n3_data = {
    'ip_tx_0': '10.0.0.55',
    'ip_rx_1': '10.0.0.57',
    'mac_rx_1': '00:0a:35:86:00:01',
    'mac_tx_0': '00:0a:35:86:00:00',
    'sport': 64000,
    'dport': 64001,
}

tx_src_port, tx_dst_port = 60512, 62177
tx_dst_ip = n3_data['ip_rx_1']
tx_dst_mac = n3_data['mac_rx_1']

# The ports are from the reference of n5 (not in the packet)
rx_src_port, rx_dst_port = n3_data['dport'], n3_data['sport']
rx_src_ip = n3_data['ip_tx_0']
rx_src_mac = n3_data['mac_tx_0']

# overhead is UDP (8), IP (20), Ethernet(14) and FCS (4), IFG (12), preamble (7), start frame delimiter (1)
OVERHEAD_APP = 8 + 20 + 14 + 4 + 12 + 7 + 1
OVERHEAD_FRAME = 12 + 7 + 1

# Latency consts
# HBM0 is 256 MB total.
# Default design only connects HBM0 to collector kernel.
# TODO: Recompile to be able to connect other HBM pseudo channels.
LATENCY_PROBE_PKTS = 2 ** 25  # equal to 128MB (2^25 4 byte words), as some space is also used for summary buffer.
LATENCY_PROBE_PKTS = 2 ** 22  # Takes less than a second
SHAPE_RTT_CYCLES = (LATENCY_PROBE_PKTS, 1)
LATENCY_PROBE_GAP = 50

# CLUSTER
cluster = SSHCluster(["localhost", REMOTE_NAME],
                     connect_options={"known_hosts": None})
client = Client(cluster)

# https://stackoverflow.com/questions/49203128/how-do-i-stop-a-running-task-in-dask
STOP = Variable(name="stop", client=client)

# %%
# Remote --------------------------------


def setup_remote_machine_experiment(experiment):
    cmd = " ".join([SETUP_REGISTER_SCRIPT_PATH, experiment])
    print("Executing on remote machine: ", cmd)
    process = subprocess.run(
        " ".join([SETUP_REGISTER_SCRIPT_PATH, experiment]),
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return process.stdout, process.stderr


def setup_remote_machine_throughput_experiment(client, dut):
    return client.submit(setup_remote_machine_experiment, "throughput",
                         workers=dut, pure=False)


def setup_remote_machine_latency_experiment(client, dut):
    return client.submit(setup_remote_machine_experiment, "latency",
                         workers=dut, pure=False)


def get_ltx_path(bistream_path):
    return bistream_path.replace('.bit', '.ltx')


def get_workers(client):
    client_info = client.scheduler_info()['workers']
    workers = []
    for cli in client_info:
        workers.append(client_info[cli]['name'])
    return workers


def verify_workers():
    node_name = platform.node()
    shell_version = os.popen(
        "/opt/xilinx/xrt/bin/xbutil dump | grep dsa_name").read()
    return node_name, shell_version[24:-2]


def check_workers(client, workers):
    worker_check = []
    for w in workers:
        wf = client.submit(verify_workers, workers=w, pure=False)
        worker_check.append(wf.result())

    for w in worker_check:
        print('Worker name: {} | shell version: {}'.format(w[0], w[1]))
    return worker_check


def perform_pr_once(bitstream=BITSTREAM_1):
    process = subprocess.run(
        " ".join([PR_SCRIPT_PATH, bitstream,
                  BOARD_NAME, PROBES_PATH]),
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return process.stdout, process.stderr


def perform_pr_continuous(inter_pr_time):
    itr = 0
    ret_list = []
    while(not STOP.get()):
        itr += 1
        node_name = platform.node()

        # Do PR
        bitstream = BITSTREAM_1
        if(itr % 2 == 0):
            bitstream = BITSTREAM_2
        ret = perform_pr_once(bitstream)
        ret_list.append(ret)

        with open('/home/ubuntu/test.log', 'a') as f:
            f.write("{}: {}, {}\n".format(itr, node_name, inter_pr_time))
        time.sleep(inter_pr_time)

    return ret_list


def start_pr(client, dut, inter_pr_time):
    STOP.set(False)
    ret = client.submit(perform_pr_continuous, inter_pr_time,
                        workers=dut, pure=False)
    return ret


def stop_pr(inter_pr_time):
    STOP.set(True)
    time.sleep(inter_pr_time)


# Local --------------------------------


def setup_local_machine():
    xup = pynq.Device.devices[0]
    ol_w0 = pynq.Overlay(XCLBIN, device=xup)

    # Check link
    print("Link worker 0_0 {}, worker 0_1 {}".format(
        ol_w0.cmac_0.linkStatus(), ol_w0.cmac_1.linkStatus()))

    if_status_w0_0 = ol_w0.networklayer_0.updateIPAddress(ip_w0_0, debug=True)
    if_status_w0_1 = ol_w0.networklayer_1.updateIPAddress(ip_w0_1, debug=True)
    print("Worker 0_0: {}\nWorker 0_1: {}".format(
        if_status_w0_0, if_status_w0_1))

    # Throughput: Setup TX (Port 0). Latency: Setup port 0 for both TX/RX.
    # Ensure DUT configured to route packets accordingly.
    ol_w0.networklayer_0.resetDebugProbes()
    ol_w0.networklayer_0.sockets[2] = (tx_dst_ip, tx_dst_port,
                                       tx_src_port, True)
    # Used for debugging is port 0 mistakenly recvs packets
    # ol_w0.networklayer_0.sockets[1] = (rx_src_ip, rx_dst_port,
    #                                    rx_src_port, True)
    ol_w0.networklayer_0.populateSocketTable()

    ol_w0.networklayer_0.invalidateARPTable()
    ol_w0.networklayer_0.arpDiscovery()
    ol_w0.networklayer_0.write_arp_entry(tx_dst_mac, tx_dst_ip)
    ol_w0.networklayer_0.write_arp_entry(rx_src_mac, rx_src_ip)
    ol_w0.networklayer_0.readARPTable()
    print(ol_w0.networklayer_0.getDebugProbes)

    # Throughput: Setup RX (Port 1). Latency: Don't care
    ol_w0.networklayer_1.resetDebugProbes()
    ol_w0.networklayer_1.sockets[1] = (rx_src_ip, rx_dst_port,
                                       rx_src_port, True)
    ol_w0.networklayer_1.populateSocketTable()

    ol_w0.networklayer_1.invalidateARPTable()
    ol_w0.networklayer_1.arpDiscovery()
    ol_w0.networklayer_1.write_arp_entry(tx_dst_mac, tx_dst_ip)
    ol_w0.networklayer_1.write_arp_entry(rx_src_mac, rx_src_ip)
    ol_w0.networklayer_1.readARPTable()
    print(ol_w0.networklayer_1.getDebugProbes)

    return ol_w0


def setup_local_machine_throughput_experiment(ol_w0):
    # Setup CONSUMER
    ol_w0_1_tg = ol_w0.traffic_generator_1_1
    ol_w0_1_tg.register_map.debug_reset = 1
    ol_w0_1_tg.register_map.mode = benchmark_mode.index('CONSUMER')
    ol_w0_1_tg.register_map.CTRL.AP_START = 1

    # Setup PRODUCER
    ol_w0_0_tg = ol_w0.traffic_generator_0_3
    ol_w0_0_tg.register_map.debug_reset = 1
    ol_w0_0_tg.register_map.mode = benchmark_mode.index('PRODUCER')
    ol_w0_0_tg.register_map.dest_id = 2

    freq = int(ol_w0.clock_dict['clock0']['frequency'])
    print("Frequency: {}".format(freq))
    ol_w0_1_tg.freq = freq
    ol_w0_0_tg.freq = freq


def setup_local_machine_latency_experiment(ol_w0):
    # Returns the allocated buffers
    # Allocate these buffers only once

    rtt_cycles = pynq.allocate(SHAPE_RTT_CYCLES, dtype=np.uint32, target=ol_w0.HBM0)
    pkt_summary = pynq.allocate(1, dtype=np.uint32, target=ol_w0.HBM0)

    # Setup LATENCY kernel
    ol_w0_tg = ol_w0.traffic_generator_0_2
    ol_w0_tg.register_map.debug_reset = 1
    ol_w0.networklayer_0.register_map.debug_reset_counters = 1
    ol_w0_tg.register_map.mode = benchmark_mode.index('LATENCY')
    ol_w0_tg.register_map.number_packets = LATENCY_PROBE_PKTS
    ol_w0_tg.register_map.time_between_packets = LATENCY_PROBE_GAP  # cyles
    ol_w0_tg.register_map.number_beats = 1  # Unused. 64 byte frame
    ol_w0_tg.register_map.dest_id = 2

    return rtt_cycles, pkt_summary


def latency_probe(ol_w0, rtt_cycles, pkt_summary):
    start = time.time()
    # collector_h =
    ol_w0.collector_0_2.start(rtt_cycles, pkt_summary)

    ol_w0_tg = ol_w0.traffic_generator_0_2
    ol_w0_tg.register_map.CTRL.AP_START = 1

    # last_print = 0
    # start_pkts = int(ol_w0_tg.register_map.out_traffic_packets)
    # start_rx_pkts = int(ol_w0_tg.register_map.in_traffic_packets)
    # window_start_pkts = int(ol_w0_tg.register_map.out_traffic_packets)
    # window_start_rx_pkts = int(ol_w0_tg.register_map.in_traffic_packets)

    while(int(ol_w0_tg.register_map.out_traffic_packets)
          != LATENCY_PROBE_PKTS):
        pass
        # end = time.time()
        # if(end - start > last_print + 1):  # print every second
        #     last_print = end - start

        #     end_pkts = int(ol_w0_tg.register_map.out_traffic_packets)
        #     end_rx_pkts = int(ol_w0_tg.register_map.in_traffic_packets)

        #     print(("{:.6f} secs, Total: TX {} pkts, RX {} pkts."
        #            " Delta: TX {} MPkts, RX: {} Mpkts")
        #           .format(
        #               end - start,
        #               end_pkts - start_pkts, end_rx_pkts - start_rx_pkts,
        #               (end_pkts - window_start_pkts)/1e6,
        #               (end_rx_pkts - window_start_rx_pkts)/1e6
        #     ))

        #     window_start_pkts = end_pkts
        #     window_start_rx_pkts = end_rx_pkts

    end = time.time()
    # print(f"Latency measurement took {end - start} secs.")

    rtt_cycles.sync_from_device()
    pkt_summary.sync_from_device()
    ol_w0_tg.register_map.debug_reset = 1  # for next measurement

    freq = int(ol_w0.clock_dict['clock0']['frequency'])
    rtt_usec = np.array(SHAPE_RTT_CYCLES, dtype=float)
    rtt_usec = rtt_cycles / freq  # convert to microseconds
    return rtt_usec


def latency_probe_summary(rtt_usec, time_since_start):
    mean, std_dev, mode = (np.mean(rtt_usec), np.std(
        rtt_usec), stats.mode(rtt_usec))
    print("{:6f}, mean {:6f} us, std dev {:6f} us, max {:6f} us, min {:6f} us.".format(
        time_since_start, mean, std_dev, np.max(rtt_usec), np.min(rtt_usec)
    ))
    # This summary can be directly used with matplotlib boxplot
    summary = cbook.boxplot_stats(rtt_usec)

    # print("Round trip time at application level using {:,} packets"
    #       .format(len(rtt_usec)))
    # print("\tmean    = {:.3f} us\n\tstd_dev = {:.6f} us".format(mean, std_dev))
    # print("\tmode    = {:.3f} us, which appears {:,} times"
    #       .format(mode[0][0][0], mode[1][0][0]))
    # print("\tmax     = {:.3f} us".format(np.max(rtt_usec)))
    # print("\tmin     = {:.3f} us".format(np.min(rtt_usec)))
    return summary


def measure_latency(ol_w0, rtt_cycles, pkt_summary, measurement_time):
    start = time.time()
    end = time.time()
    summary_list = []
    times = []
    print("Time, mean latency, std dev, max latency, min latency")
    while(end - start <= measurement_time):
        rtt_usec = latency_probe(ol_w0, rtt_cycles, pkt_summary)
        end = time.time()
        summary = latency_probe_summary(rtt_usec, end - start)
        summary_list.extend(summary)
        times.append(end - start)
    return summary_list, times


def measure_latency_under_pr(client, dut, inter_pr_time,
                             ol_w0, rtt_cycles, pkt_summary, measurement_time):
    pr_future = start_pr(client, dut, inter_pr_time)
    ret = measure_latency(ol_w0, rtt_cycles, pkt_summary, measurement_time)
    stop_pr(inter_pr_time)
    return ret, pr_future


def _plot_latency_probe(rtt_usec):
    red_square = dict(markerfacecolor='r', marker='s')
    fig, ax = plt.subplots()
    ax.set_title('RTT Box and whisker plot')
    ax.set_xlabel('Round Trip Time (microsecond)')
    ax.set_yticklabels([''])
    fig.set_size_inches(18, 2)
    ax.boxplot(rtt_usec, vert=False, flierprops=red_square)
    fig.savefig('latency.pdf')


def measure_throughput_under_pr(client, dut, inter_pr_time,
                                ol_w0, payload_size, num_pkts):
    pr_future = start_pr(client, dut, inter_pr_time)
    ret = measure_throughput(ol_w0, payload_size, num_pkts)
    stop_pr(inter_pr_time)
    return ret, pr_future


def measure_throughput(ol_w0, payload_size, num_pkts=int(1e6)):
    # Setup local device and throughput experiment before calling this function
    ol_w0_1_tg = ol_w0.traffic_generator_1_1
    ol_w0_0_tg = ol_w0.traffic_generator_0_3
    ol_w0_0_tg.register_map.debug_reset = 1
    ol_w0_1_tg.register_map.debug_reset = 1
    ol_w0_0_tg.register_map.time_between_packets = 0
    ol_w0_0_tg.register_map.number_packets = num_pkts

    beats = int(payload_size / 64)
    ol_w0_0_tg.register_map.number_beats = beats
    ol_w0_0_tg.register_map.CTRL.AP_START = 1
    start_time = time.time()
    entries = []
    print("Time, sent pkts, recd pkts, mpps sent, mpps recd")
    while(int(ol_w0_0_tg.register_map.out_traffic_packets) != num_pkts):
        start_pkts = int(ol_w0_0_tg.register_map.out_traffic_packets)
        start_rx_pkts = int(ol_w0_1_tg.register_map.in_traffic_packets)
        time.sleep(1)
        end_pkts = int(ol_w0_0_tg.register_map.out_traffic_packets)
        end_rx_pkts = int(ol_w0_1_tg.register_map.in_traffic_packets)
        end_time = time.time()

        entry = {
            'time': end_time,
            'tx_pkts': end_pkts,
            'rx_pkts': end_rx_pkts,
        }
        entries.append(entry)

        print("{:.6f} secs, TX {} pkts, RX {} pkts, TX {} Mpps, RX {} Mpps".format(
            end_time - start_time,
            end_pkts - start_pkts, end_rx_pkts - start_rx_pkts,
            (end_pkts - start_pkts)/1e6, (end_rx_pkts - start_rx_pkts)/1e6
        ))

        # print(("Sent {} pkts in 1 sec ({} Mpps)."
        #        " Total elapsed {} secs. Total sent {} pkts.")
        #       .format(end_pkts - start_pkts, (end_pkts - start_pkts)/1e6,
        #               end_time - start_time, end_pkts))
        # print(("Recd {} pkts in 1 sec ({} Mpps)."
        #        " Total elapsed {} secs. Total sent {} pkts.")
        #       .format(end_rx_pkts - start_rx_pkts,
        #               (end_rx_pkts - start_rx_pkts)/1e6,
        #               end_time - start_time, end_pkts))

    # Get results from local and remote worker
    rx_tot_pkt, rx_thr, rx_time = ol_w0_1_tg.computeThroughputApp('rx')
    tx_tot_pkt, tx_thr, tx_time = ol_w0_0_tg.computeThroughputApp('tx')

    # Reset probes to prepare for next computation
    ol_w0_0_tg.resetProbes()
    ol_w0_1_tg.resetProbes()

    # Compute theoretical maximum at application level
    app_payload_size = beats * 64
    frame_size = payload_size + (OVERHEAD_APP - OVERHEAD_FRAME)
    theoretical_app = 100 * (app_payload_size /
                             (app_payload_size + OVERHEAD_APP))
    theoretical_frame = 100 * (frame_size /
                               (frame_size + OVERHEAD_FRAME))

    # Create dict entry for this particular experiment
    entry_dict = {
        'size': app_payload_size,
        'rx_pkts': rx_tot_pkt,
        'tx_thr': tx_thr,
        'rx_thr': rx_thr,
        'theoretical_app': theoretical_app,

        'frame_size': frame_size,
        'theoretical_frame': theoretical_frame,
        'frame_rx_thr': rx_thr * (frame_size / app_payload_size)
    }

    print("Sent {:14,} size: {:4}-Byte done!	Got {:14,} took {:8.4f} sec, thr: {:.3f} Gbps, theoretical: {:.3f} Gbps, difference: {:6.3f} Gbps"
          .format(num_pkts, app_payload_size, rx_tot_pkt, rx_time, rx_thr, theoretical_app, theoretical_app-rx_thr))
    time.sleep(0.5)
    return entry_dict, entries


# %%
# if(__name__ == "__main__"):
workers = get_workers(client)
worker_check = check_workers(client, workers)
assert len(worker_check) == 1 and worker_check[0][0] == REMOTE_NAME
dut = workers[0]

# # Test PR operation
# wf = client.submit(perform_pr_once, workers=dut, pure=False)
# start = time.time()
# stdout, stderr = wf.result()
# print(stdout)
# end = time.time()
# print("PR operation took {} seconds.".format(end - start))


# # Test register setup
# setup_future = setup_remote_machine_throughput_experiment(client, dut)
# out, err = setup_future.result()
# print(out)
# print(err)

# %%
EXP_TAG = "disable_rm"
EXP_DIR = f"./data/{EXP_TAG}"
os.makedirs(EXP_DIR, exist_ok=True)

# Exp config
INTER_PR_TIME = 10  # secs

LATENCY_MEASUREMENT_TIME = 15  # secs
LATENCY_MEASUREMENT_TIME_UNDER_PR = 120  # secs

THROUGHPUT_PAYLOAD_SIZE = 64  # bytes
THROUGHPUT_PROBE_PKTS = int(30 * 58 * 1e6)
THROUGHPUT_PROBE_PKTS_UNDER_PR = int(2 * 60 * 58 * 1e6)

exp_config = {
    "INTER_PR_TIME": INTER_PR_TIME,
    "LATENCY_PROBE_PKTS": LATENCY_PROBE_PKTS,
    "LATENCY_PROBE_GAP": LATENCY_PROBE_GAP,
    "THROUGHPUT_PAYLOAD_SIZE": THROUGHPUT_PAYLOAD_SIZE,
    "THROUGHPUT_PROBE_PKTS": THROUGHPUT_PROBE_PKTS,
    "THROUGHPUT_PROBE_PKTS_UNDER_PR": THROUGHPUT_PROBE_PKTS_UNDER_PR
}
with open(os.path.join(EXP_DIR, "config.json"), 'w') as f:
    json.dump(exp_config, f)

ol_w0 = setup_local_machine()

# %%
# Latency measurement
print("Latency measurement started")

rtt_cycles, pkt_summary = setup_local_machine_latency_experiment(ol_w0)
setup_remote_machine_latency_experiment(client, dut)

summary_list, times = measure_latency(ol_w0, rtt_cycles, pkt_summary,
                                      LATENCY_MEASUREMENT_TIME)
fname = "without_pr-latency.pickle"
with open(os.path.join(EXP_DIR, fname), 'wb') as f:
    pickle.dump((summary_list, times), f)

(summary_list_pr, times_pr), pr_future = measure_latency_under_pr(
    client, dut, INTER_PR_TIME, ol_w0, rtt_cycles, pkt_summary,
    LATENCY_MEASUREMENT_TIME_UNDER_PR)

fname = "with_pr-latency.pickle"
with open(os.path.join(EXP_DIR, fname), 'wb') as f:
    pickle.dump((summary_list_pr, times_pr), f)

print("Latency measurement complete")

# %%
# Throughput measurement
print("Throughput measurement started")

setup_local_machine_throughput_experiment(ol_w0)
setup_remote_machine_throughput_experiment(client, dut)

start = time.time()
summary, entries = measure_throughput(
    ol_w0, THROUGHPUT_PAYLOAD_SIZE, THROUGHPUT_PROBE_PKTS)
end = time.time()
print("No PR: {}".format(summary))
print("Thr measurement took {} seconds.".format(end - start))

df = pd.DataFrame(entries)
df.to_csv(os.path.join(EXP_DIR, f"without_pr-ts.csv"), index=False)
with open(os.path.join(EXP_DIR, f"without_pr-summary.json"), "w") as f:
    json.dump(summary, f)

start = time.time()
(summary, entries), pr_future = measure_throughput_under_pr(
    client, dut, INTER_PR_TIME, ol_w0, THROUGHPUT_PAYLOAD_SIZE,
    THROUGHPUT_PROBE_PKTS_UNDER_PR)
end = time.time()
print("With PR every {} secs: {}".format(INTER_PR_TIME, summary))
print("Thr measurement took {} seconds.".format(end - start))

df = pd.DataFrame(entries)
df.to_csv(os.path.join(EXP_DIR, f"with_pr-ts.csv"), index=False)
with open(os.path.join(EXP_DIR, f"with_pr-summary.json"), "w") as f:
    json.dump(summary, f)

print("Throughput measurement complete")

# %%
client.close()
cluster.close()
pynq.Overlay.free(ol_w0)
