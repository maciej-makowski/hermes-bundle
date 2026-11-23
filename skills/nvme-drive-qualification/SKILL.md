---
name: nvme-drive-qualification
"description": "Use for NVMe drive burn-in, SMART checks, USB speed triage."
version: 1.0.0
author: Hermes Agent
license: MIT
tags: [storage, nvme, ssd, burn-in, smart, fio]
metadata:
  hermes:
    tags: [storage, nvme, ssd, burn-in, smart, fio]
---

# NVMe drive qualification

## When to Use

Load when brand-new NVMe drives must be proven before mounting into any host (PCIe HAT, laptop slot, USB enclosure): the SMART new-drive battery, the full-surface burn-in, and the transport triage when throughput looks wrong. Also carries the Pi 5 NVMe hardware constraints for storage work.

## Tier 1: SMART battery (minutes, per drive)

Run before anything else; it decides new-vs-used and catches DOA drives.

```bash
sudo apt install -y smartmontools nvme-cli   # Fedora: dnf install smartmontools nvme-cli
sudo smartctl -i /dev/<dev>                  # model, firmware, capacity
sudo smartctl -H /dev/<dev>                  # overall health must print PASSED
sudo smartctl -A /dev/<dev>                  # counters
sudo nvme smart-log /dev/<dev>               # critical_warning must read 0x0
```

A factory-fresh drive shows ALL of:

- Power On Hours 0-2 with 1 power cycle, Data Units Read/Written near zero
- Percentage Used 0%, Available Spare 100%, Media and Data Integrity Errors 0
- Error Information Log Entries 0, Unsafe Shutdowns 1 or fewer, Critical Warning 0x00

High hours or nonzero write units on a drive sold as new means used or refurbished: return it. Compare the pair: same model and same firmware version ideally.

## Tier 2: full-surface burn-in (before building any array)

fio writes the entire surface with per-block checksums, then re-reads and verifies. It destroys all data on the target; safe on fresh drives only, and the target check (`lsblk -d -o NAME,MODEL,SIZE,TRAN`) is repeated after every drive swap because sdX letters shift.

```bash
sudo fio --name=burnin --filename=/dev/<dev> --rw=write --bs=1M \
  --direct=1 --ioengine=libaio --iodepth=16 \
  --verify=crc32c --verify_fatal=1 --size=<in-bounds>G --bandwidth-log
```

- Pass `--ioengine=libaio` or iodepth does nothing: with the default sync engine fio prints "queue depth will be capped at 1" and roughly halves throughput. io_uring is the fallback engine. A distro-packaged fio has engines compiled in; Homebrew's Linux fio often does not (engine "not loadable"), so install the distro fio and run it by absolute path (/usr/bin/fio).
- Size the run INSIDE the device: the label's TB is about 0.91 of the TiB fio counts (a 2.00 TB label is 1.82 TiB). Overshooting aborts mid-run; 1800G is the in-bounds size for a 2 TB drive. State the gate's coverage by its actual range (1800G is 96.6% of a 2 TB label) and point the uncovered tail at the on-target SMART check; never describe a sized run as 'whole drive' or 'every LBA' — the claim is false against the command itself, and a design review flags the mismatch as a finding.
- A clean pass is the verdict that matters: verify_fatal=1 aborts on the first mismatch. After the pass the counters must still show Percentage Used 0% and Media Errors 0; a pass that bumps Percentage Used marks a weak drive for return.
- Burn one drive at a time on any shared transport (USB bridge, switch-based HAT) so bandwidth is full and errors are attributable.
- Wall clock estimate: 2 x capacity / sustained MB/s. About 1-1.5 h per 2 TB drive on a healthy 10 Gbps bridge; about 2.2 h per drive on the Pi 5's shared PCIe Gen 2 lane.

## Transport triage when throughput looks wrong

- Around 30 MB/s is the USB 2.0 signature (a 480 Mbps link), not a drive defect: `lsusb -t` shows 5000M vs 480M per port; try another data port and replug. If EVERY port yields 480M (the device never appears on any 10000M bus), the fault travels with the plug, not the host: read the device's declared generation with `lsusb -v -d <vid:pid> | grep -m1 bcdUSB` (0x03xx declares SuperSpeed, blame the cable; 0x02xx is firmware-locked to 2.0, blame the case) and confirm with `sudo dmesg` during a replug (new SuperSpeed vs new high-speed). A 2.0-only USB-C cable reproduces 480M on every port; charge-first C-to-C cables (laptop charger leads) are commonly 2.0-only while looking identical to data cables.
- `sudo dmesg | grep -iE 'uas|usb-storage'`: the uas driver must bind; usb-storage (single-command BOT) cripples queueing. Replug to re-negotiate; plain dmesg hits Operation not permitted on Fedora (dmesg_restrict), run it with sudo. Direction-check any internet quirk advice before applying it: the widely posted `usb-storage.quirks=0bda:9210:u` FORCES the slow BOT driver (a Pi-class stability workaround) - on a workstation you want the opposite (uas to bind). If uas never binds on any port, burning over BOT on a 10 Gbps link still works at roughly a third of uas speed (about 300-400 MB/s on a 2 TB pass) - a valid, slower burn.
- Healthy link (5000M + uas) but slow under sustained write is bridge thermal throttling (RTL9210-class bridges throttle hard while the drive's SMART temperature stays low). Resting recovers speed.
- smartmontools auto-detects common NVMe USB bridges, so plain smartctl works; only on "Unknown USB bridge" retry with `-d sntrealtek`, `-d sntasmedia`, or `-d sntjmicron` matching the chip from lsusb.
- A dirty burn over a suspect bridge implicates the TRANSPORT first: re-run before condemning the drive. Burning on the deployment target itself (a HAT lane) validates the real path and is the better burn when the bridge misbehaves. The fastest burn transport when one exists is a laptop's FREE M.2 slot (real PCIe, no bridge): seating a drive there costs one bottom-plate removal and runs the burn at native speed with native SMART (no -d snt* workaround); prefer it over a suspect or slow bridge.

## Notes

- SMART counters persist across moves (enclosure to HAT): a laptop-side burn carries over; still re-run Tier 1 on the target after mounting.
- On a switch-based two-slot board behind one PCIe Gen 2 x1 lane, RAID 1 is the only sensible array: writes hit both drives at about half the lane each, while RAID 0 gains nothing (the lane caps combined throughput) and doubles failure risk.
- Pi 5 storage context: the PCIe interface is Gen 2 x1 (~450 MB/s) on an FFC connector; drives must be M-key NVMe, never M.2 SATA; booting from an NVMe board needs bootloader firmware 2024-05-17 or newer (`sudo rpi-eeprom-update` to check); power-hungry drives may need the board's 5V pads and the 27W official PSU.
- Swapping or replacing a boot SD card breaks every PARTUUID-based fstab line that names it (a PARTUUID is the card's MBR disk ID plus the partition number): clone the old card's MBR disk signature onto the replacement (`fdisk` expert mode `i`, or write the four little-endian ID bytes at offset 440) and the fstab needs no edit - cheaper than sed-ing fstab from an emergency shell after a failed boot.
- Never require physical disassembly for drive-to-slot identification: the array self-identifies a pulled member after the fact (the surviving `btrfs filesystem show` names the missing UUID), and a 15-second read-only fio LED test (`fio --rw=read --runtime=15 --time_based` on one nvme device) maps device-to-slot by watching which bay's activity LED flickers - no unscrewing. Record an uncertain physical mapping as provisional and settle it by LED test when a drill actually needs it.
