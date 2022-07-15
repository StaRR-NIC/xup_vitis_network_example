# %%
import json
import os
import platform
import subprocess
import time

import pandas as pd
import pynq
from distributed.client import Client
from distributed.deploy.ssh import SSHCluster
from distributed.variable import Variable

from vnx_utils import *

# %%

# REMOTE
REMOTE_NAME = "neptune3"
BITSTREAM_1 = (
    "/home/ubuntu/Projects/StaRR-NIC/anup-starrnic-shell/"
    "build/au280_shorted-p4-bypass-ila/open_nic_shell/"
    "open_nic_shell.runs/impl_1/"
    "box_250mhz_inst_stream_switch_dfx_inst_partition1_"
    "rm_intf_inst_pkt_size_counter_partial.bit")
BITSTREAM_2 = (
    "/home/ubuntu/Projects/StaRR-NIC/anup-starrnic-shell/"
    "build/au280_shorted-p4-bypass-ila/open_nic_shell/"
    "open_nic_shell.runs/child_0_impl_1/"
    "box_250mhz_inst_stream_switch_dfx_inst_partition1_"
    "rm_intf_inst_pkt_size_counter5_partial.bit")
PR_SCRIPT_PATH = ("/home/ubuntu/Projects/StaRR-NIC/"
                  "anup-starrnic-shell/script/replace_pr_util.sh")
PROBES_PATH = (
    "/home/ubuntu/Projects/StaRR-NIC/anup-starrnic-shell/"
    "build/au280_shorted-p4-bypass-ila/open_nic_shell/"
    "open_nic_shell.runs/impl_1/open_nic_shell.ltx")
BOARD_NAME = "au280"


# LOCAL
XCLBIN = xclbin = (
    "/home/ubuntu/Projects/StaRR-NIC/"
    "xup_vitis_network_example/"
    "benchmark.intf3.xilinx_u280_xdma_201920_3/"
    "vnx_benchmark_if3.xclbin")

# PACKET HEADERS
ip_w0_0, ip_w0_1 = '10.0.0.47', '10.0.0.45'
# # Change mac address here after recompiling Open NIC
# # TODO: Make open nic use static mac address
n3_data = {
    'ip_tx_0': '10.0.0.55',
    'ip_rx_1': '10.0.0.57',
    'mac_rx_1': "00:0a:35:ec:b9:9e",  # "00:0a:35:6e:dc:b4",
    'mac_tx_0': "00:0a:35:23:1d:87",  # "00:0a:35:72:7b:90",
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

# CLUSTER
cluster = SSHCluster(["localhost", REMOTE_NAME],
                     connect_options={"known_hosts": None})
client = Client(cluster)

# https://stackoverflow.com/questions/49203128/how-do-i-stop-a-running-task-in-dask
STOP = Variable(name="stop", client=client)

# %%
# Remote --------------------------------


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

    return ol_w0


def setup_local_machine_throughput_experiment(ol_w0):

    # Setup TX (Port 0)
    ol_w0.networklayer_0.resetDebugProbes()
    ol_w0.networklayer_0.sockets[12] = (tx_dst_ip, tx_dst_port,
                                        tx_src_port, True)
    ol_w0.networklayer_0.sockets[1] = (rx_src_ip, rx_dst_port,
                                       rx_src_port, True)
    ol_w0.networklayer_0.populateSocketTable()

    ol_w0.networklayer_0.invalidateARPTable()
    ol_w0.networklayer_0.arpDiscovery()
    ol_w0.networklayer_0.write_arp_entry(tx_dst_mac, tx_dst_ip)
    ol_w0.networklayer_0.write_arp_entry(rx_src_mac, rx_src_ip)
    ol_w0.networklayer_0.readARPTable()
    print(ol_w0.networklayer_0.getDebugProbes)

    # Setup RX (Port 1)
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

    # Setup CONSUMER
    ol_w0_1_tg = ol_w0.traffic_generator_1_1
    ol_w0_1_tg.register_map.debug_reset = 1
    ol_w0_1_tg.register_map.mode = benchmark_mode.index('CONSUMER')
    ol_w0_1_tg.register_map.CTRL.AP_START = 1

    # Setup PRODUCER
    ol_w0_0_tg = ol_w0.traffic_generator_0_3
    ol_w0_0_tg.register_map.debug_reset = 1
    ol_w0_0_tg.register_map.mode = benchmark_mode.index('PRODUCER')
    ol_w0_0_tg.register_map.dest_id = 12

    freq = int(ol_w0.clock_dict['clock0']['frequency'])
    print("Frequency: {}".format(freq))
    ol_w0_1_tg.freq = freq
    ol_w0_0_tg.freq = freq


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

# # %%
# wf = client.submit(perform_pr_once, workers=dut, pure=False)
# start = time.time()
# stdout, stderr = wf.result()
# print(stdout)
# end = time.time()
# print("PR operation took {} seconds.".format(end - start))

# %%
ol_w0 = setup_local_machine()
setup_local_machine_throughput_experiment(ol_w0)

# Sent  6,960,000,000 size:  128-Byte done!       Got  6,960,000,000 took 118.3673 sec, thr: 60.211 Gbps, theoretical: 65.979 Gbps, difference:  5.768 Gbps
start = time.time()
summary, entries = measure_throughput(ol_w0, 128, int(30 * 58 * 1e6))
end = time.time()
print("No PR: {}".format(summary))
print("Thr measurement took {} seconds.".format(end - start))

df = pd.DataFrame(entries)
df.to_csv("./data/no-pr-ts.csv", index=False)
with open("./data/no-pr-summary.json", "w") as f:
    json.dump(summary, f)

print("Sleeping for 10 seconds")
time.sleep(10)

delay = 30
start = time.time()
(summary, entries), pr_future = measure_throughput_under_pr(
    client, dut, delay, ol_w0, 128, int(2 * 60 * 58 * 1e6))
end = time.time()
print("With full PR blast: {}".format(summary))
print("Thr measurement took {} seconds.".format(end - start))

df = pd.DataFrame(entries)
df.to_csv(f"./data/switch-only-pr-{delay}delay-ts.csv", index=False)
with open(f"./data/switch-only-pr-{delay}delay-summary.json", "w") as f:
    json.dump(summary, f)

import ipdb; ipdb.set_trace()

# %%
client.close()
cluster.close()
pynq.Overlay.free(ol_w0)
