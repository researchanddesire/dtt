#!/usr/bin/env python3
"""Build the DTT v2 (rev5) KiCad project: symbols, schematic, footprints, board.

Run with KiCad 7+ Python (needs `pcbnew`):  python3 build_dtt_v2.py
The netlist below is the single source; schematic and board are regenerated
from it, then route_dtt_v2.py routes the board.
"""
import json
import shutil
import uuid
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
STEM = 'dtt_v2'
LIB = 'dtt_v2'
REV4 = HERE.parents[1] / 'kicad-rev4' / '217A_dttrainer_rev4'
KICAD_FP = Path('/usr/share/kicad/footprints')

# Board and mechanical parameters (mm). Screen size is provisional until the
# panel is chosen; the board follows it.
PARAMS = {
    'board_w': 38.0,
    'board_h': 64.0,
    'corner_r': 3.0,
    'antenna_strip': 7.0,      # top strip kept free of copper for the S3 antenna
    'screen_w': 36.0,          # 2.0 in 240x320 module outline, assumed
    'screen_h': 52.0,
    'origin': (100.0, 100.0),  # board top-left in KiCad coordinates
    # Case screws: M2 self-tapping through the board into the front shell, at
    # the corners outside the screen glass and the S3 module.
    'holes': [(3.0, 2.5), (35.0, 2.5), (3.0, 61.5), (35.0, 61.5)],
}

# Nets routed 0.4 mm wide.
POWER_NETS = ('VBUS', 'VBAT', 'VBAT_SW', 'VSYS', 'VSYS_PORT', '+3V3', 'OUT1', 'OUT2')

NS = uuid.UUID('6b1f8a2e-6f0e-4f4e-9a52-0d7d2c1e5a10')


def uid(*parts):
    return str(uuid.uuid5(NS, '/'.join(str(p) for p in parts)))


# ---------------------------------------------------------------- footprints
# (library, name) of KiCad standard footprints copied into the project library.
STD = {
    'R0402': ('Resistor_SMD', 'R_0402_1005Metric'),
    'C0402': ('Capacitor_SMD', 'C_0402_1005Metric'),
    'C0805': ('Capacitor_SMD', 'C_0805_2012Metric'),
    'C1206': ('Capacitor_SMD', 'C_1206_3216Metric'),
    'F0805': ('Fuse', 'Fuse_0805_2012Metric'),
    'SOT23': ('Package_TO_SOT_SMD', 'SOT-23'),
    'SOT23-5': ('Package_TO_SOT_SMD', 'SOT-23-5'),
    'SOT23-6': ('Package_TO_SOT_SMD', 'SOT-23-6'),
    'SOD123': ('Diode_SMD', 'D_SOD-123'),
    'S3': ('RF_Module', 'ESP32-S3-WROOM-1'),
    'USBC': ('Connector_USB', 'USB_C_Receptacle_HRO_TYPE-C-31-M-12'),
    'PH2': ('Connector_JST', 'JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal'),
    'PH6': ('Connector_JST', 'JST_PH_S6B-PH-SM4-TB_1x06-1MP_P2.00mm_Horizontal'),  # SMD: no pins through the front, under the glass
    'FPC21': ('Connector_FFC-FPC', 'TE_2-1734839-1_1x21-1MP_P0.5mm_Horizontal'),
    'TACT': ('Button_Switch_SMD', 'SW_Push_1P1T_XKB_TS-1187A'),
}


def lga_footprint(name, descr, pads, body, courtyard):
    """Write an LGA footprint from (number, x, y, w, h) pad tuples, y down."""
    bw, bh = body
    cw, ch = courtyard
    out = [f'(footprint "{name}" (version 20221018) (generator build_dtt_v2)',
           '  (layer "F.Cu")', f'  (descr "{descr}")', '  (attr smd)',
           f'  (fp_text reference "REF**" (at 0 {-ch / 2 - 0.8:.3f}) (layer "F.SilkS")'
           ' (effects (font (size 0.8 0.8) (thickness 0.12))))',
           f'  (fp_text value "{name}" (at 0 {ch / 2 + 0.8:.3f}) (layer "F.Fab")'
           ' (effects (font (size 0.8 0.8) (thickness 0.12))))',
           f'  (fp_rect (start {-bw / 2} {-bh / 2}) (end {bw / 2} {bh / 2})'
           ' (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))',
           f'  (fp_rect (start {-cw / 2} {-ch / 2}) (end {cw / 2} {ch / 2})'
           ' (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))']
    # pin-1 dot on silk, outside the body
    x1, y1 = pads[0][1], pads[0][2]
    sx = (bw / 2 + 0.35) * (1 if x1 > 0 else -1)
    sy = (bh / 2 + 0.35) * (1 if y1 > 0 else -1)
    out.append(f'  (fp_circle (center {sx:.3f} {sy:.3f}) (end {sx + 0.1:.3f} {sy:.3f})'
               ' (stroke (width 0.2) (type default)) (fill solid) (layer "F.SilkS"))')
    for num, x, y, w, h in pads:
        out.append(f'  (pad "{num}" smd rect (at {x:.4f} {y:.4f}) (size {w:.4f} {h:.4f})'
                   ' (layers "F.Cu" "F.Paste" "F.Mask"))')
    out.append(')')
    return '\n'.join(out) + '\n'


def custom_footprints():
    fps = {}
    # VL53L4CD optical LGA-12, 4.4 x 2.4 mm. Pad pattern from the Adafruit
    # VL53L4CD breakout (CC BY-SA); pads 0.5 mm square on a 0.8 mm grid.
    p = []
    for i, x in enumerate([1.6, 0.8, 0.0, -0.8, -1.6]):
        p.append((str(i + 1), x, 0.8, 0.5, 0.5))
    p += [('6', -1.6, 0.0, 0.5, 0.5)]
    for i, x in enumerate([-1.6, -0.8, 0.0, 0.8, 1.6]):
        p.append((str(i + 7), x, -0.8, 0.5, 0.5))
    p += [('12', 1.6, 0.0, 0.5, 0.5)]
    fps['ST_VL53L4CD_LGA-12_4.4x2.4mm'] = lga_footprint(
        'ST_VL53L4CD_LGA-12_4.4x2.4mm', 'ST VL53L4CD ToF sensor, optical LGA-12',
        p, (4.4, 2.4), (5.0, 3.0))
    # LSM6DSO LGA-14 2.5 x 3 mm (pattern as Adafruit LSM6DSOX breakout).
    p = []
    for i, y in enumerate([-0.75, -0.25, 0.25, 0.75]):
        p.append((str(i + 1), -1.1625, y, 0.475, 0.25))
    for i, x in enumerate([-0.5, 0.0, 0.5]):
        p.append((str(i + 5), x, 0.9125, 0.25, 0.475))
    for i, y in enumerate([0.75, 0.25, -0.25, -0.75]):
        p.append((str(i + 8), 1.1625, y, 0.475, 0.25))
    for i, x in enumerate([0.5, 0.0, -0.5]):
        p.append((str(i + 12), x, -0.9125, 0.25, 0.475))
    fps['ST_LGA-14_2.5x3mm_P0.5mm'] = lga_footprint(
        'ST_LGA-14_2.5x3mm_P0.5mm', 'ST LGA-14L 2.5x3x0.83 mm (LSM6DSO)',
        p, (3.0, 2.5), (3.6, 3.1))
    # LIS3MDL LGA-12 2 x 2 mm (pattern as Adafruit LIS3MDL breakout).
    p = []
    for i, y in enumerate([-0.75, -0.25, 0.25, 0.75]):
        p.append((str(i + 1), -0.75, y, 0.275, 0.25))
    for i, x in enumerate([-0.25, 0.25]):
        p.append((str(i + 5), x, 0.75, 0.25, 0.275))
    for i, y in enumerate([0.75, 0.25, -0.25, -0.75]):
        p.append((str(i + 7), 0.75, y, 0.275, 0.25))
    for i, x in enumerate([0.25, -0.25]):
        p.append((str(i + 11), x, -0.75, 0.25, 0.275))
    fps['ST_LGA-12_2x2mm_P0.5mm'] = lga_footprint(
        'ST_LGA-12_2x2mm_P0.5mm', 'ST LGA-12 2x2x1 mm (LIS3MDL)',
        p, (2.0, 2.0), (2.6, 2.6))
    return fps


# ------------------------------------------------------------------- netlist
# Each part: ref, value, footprint key (STD key or custom name or 'rev4:<name>'),
# LCSC part ('' = to be sourced), sheet, pins [(number, name, net)].
PARTS = []

# Placement (x, y, rotation before flip, side) in board mm from the top-left
# corner, front view. Back-side parts are flipped left-right.
PLACE = {'J1': (34.0, 36.0, 270, 'B'),
    'R1': (35.5, 29.0, 0, 'B'),
    'R2': (35.5, 27.5, 0, 'B'),
    'U1': (31.5, 22.5, 0, 'B'),
    'C1': (30.5, 44.0, 90, 'B'),
    'U2': (25.5, 37.5, 90, 'B'),
    'R3': (25.5, 41.0, 0, 'B'),
    'R4': (25.5, 42.3, 0, 'B'),
    'C2': (22.5, 41.0, 0, 'B'),
    'J2': (5.2, 53.5, 0, 'B'),
    'SW1': (35.7, 50.0, 270, 'B'),
    'Q1': (18.5, 43.0, 0, 'B'),
    'R5': (18.5, 45.5, 0, 'B'),
    'D1': (23.5, 44.5, 0, 'B'),
    'U3': (14.3, 37.0, 0, 'B'),
    'C3': (14.5, 40.2, 0, 'B'),
    'C4': (19.0, 37.0, 90, 'B'),
    'C5': (22.0, 37.0, 90, 'B'),
    'R6': (27.0, 44.0, 0, 'B'),
    'R7': (27.0, 45.3, 0, 'B'),
    'C6': (27.0, 46.6, 0, 'B'),
    'R8': (30.5, 47.0, 0, 'B'),
    'R9': (30.5, 48.3, 0, 'B'),
    'U4': (19.0, 13.0, 0, 'B'),
    'C7': (33.0, 9.0, 0, 'B'),
    'C8': (30.0, 9.0, 0, 'B'),
    'R10': (30.0, 11.5, 0, 'B'),
    'C9': (30.0, 13.0, 0, 'B'),
    'R11': (6.5, 13.0, 90, 'B'),
    'SW2': (5.0, 21.5, 90, 'B'),
    'TP1': (2.5, 9.5, 0, 'B'),
    'TP2': (5.0, 9.5, 0, 'B'),
    'TP3': (7.5, 9.5, 0, 'B'),
    'J3': (19.0, 58.8, 0, 'B'),
    'R12': (20.5, 52.5, 0, 'B'),
    'Q2': (17.0, 53.0, 0, 'B'),
    'R13': (20.5, 54.0, 0, 'B'),
    'R14': (3.5, 13.0, 90, 'B'),
    'R15': (5.0, 13.0, 90, 'B'),
    # ToF in the bottom right corner of the front, beside the screen FPC (which
    # wraps round the bottom edge at x 13 to 25) and clear of the H2 screw boss.
    'U5': (29.0, 61.7, 0, 'F'),
    'C10': (28.3, 62.0, 90, 'B'),
    'C11': (29.8, 62.0, 90, 'B'),
    'R16': (31.3, 62.0, 90, 'B'),
    'R17': (28.3, 60.0, 90, 'B'),
    'U6': (15.3, 49.0, 0, 'B'),
    'C12': (15.3, 46.5, 0, 'B'),
    'C13': (14.0, 52.2, 90, 'B'),
    'U7': (20.0, 49.0, 0, 'B'),
    'C14': (20.0, 46.8, 0, 'B'),
    'C15': (22.5, 49.0, 90, 'B'),
    'J4': (7.0, 35.5, 90, 'B'),   # SMD PH6 is 17 mm long: above J2, left of the output drivers
    'F1': (11.8, 54.2, 0, 'B'),
    'U8': (11.5, 46.5, 90, 'B'),
    'U9': (11.5, 50.7, 90, 'B'),
    'R18': (14.0, 28.0, 0, 'B'),
    'Q3': (14.5, 31.0, 0, 'B'),
    'R19': (17.5, 28.0, 0, 'B'),
    'R20': (17.5, 29.5, 0, 'B'),
    'Q4': (18.5, 32.5, 0, 'B'),
    'R21': (22.0, 28.0, 0, 'B'),
    'Q5': (22.5, 31.0, 0, 'B'),
    'R22': (25.5, 28.0, 0, 'B'),
    'R23': (25.5, 29.5, 0, 'B'),
    'Q6': (26.5, 32.5, 0, 'B')}


def part(ref, value, fp, lcsc, sheet, pins, dnp=False):
    PARTS.append(dict(ref=ref, value=value, fp=fp, lcsc=lcsc, sheet=sheet,
                      pins=pins, place=PLACE[ref], dnp=dnp))


def two(ref, value, fp, lcsc, sheet, n1, n2):
    part(ref, value, fp, lcsc, sheet, [('1', '1', n1), ('2', '2', n2)])


# Power: USB-C, charger, battery, switch, power path, 3.3 V LDO --------------
P = 'power'
part('J1', 'USB-C', 'USBC', 'C165948', P, [
    ('A4', 'VBUS', 'VBUS'), ('A9', 'VBUS', 'VBUS'), ('B4', 'VBUS', 'VBUS'), ('B9', 'VBUS', 'VBUS'),
    ('A1', 'GND', 'GND'), ('A12', 'GND', 'GND'), ('B1', 'GND', 'GND'), ('B12', 'GND', 'GND'),
    ('S1', 'SHIELD', 'GND'),
    ('A5', 'CC1', 'USB_CC1'), ('B5', 'CC2', 'USB_CC2'),
    ('A6', 'D+', 'USB_DP'), ('B6', 'D+', 'USB_DP'),
    ('A7', 'D-', 'USB_DN'), ('B7', 'D-', 'USB_DN'),
    ('A8', 'SBU1', None), ('B8', 'SBU2', None)])
two('R1', '5.1k', 'R0402', 'C25905', P, 'USB_CC1', 'GND')
two('R2', '5.1k', 'R0402', 'C25905', P, 'USB_CC2', 'GND')
part('U1', 'USBLC6-2SC6', 'SOT23-6', 'C7519', P, [
    ('1', 'IO1', 'USB_DN'), ('2', 'GND', 'GND'), ('3', 'IO2', 'USB_DP'),
    ('4', 'IO2', 'USB_DP'), ('5', 'VBUS', 'VBUS'), ('6', 'IO1', 'USB_DN')])
two('C1', '10uF', 'C0805', 'C89827', P, 'VBUS', 'GND')
part('U2', 'TP4054', 'SOT23-5', 'C32574', P, [
    ('1', 'CHRG', 'CHG_N'), ('2', 'GND', 'GND'), ('3', 'BAT', 'VBAT'),
    ('4', 'VCC', 'VBUS'), ('5', 'PROG', 'CHG_PROG')])
two('R3', '2k', 'R0402', 'C5126028', P, 'CHG_PROG', 'GND')
two('R4', '10k', 'R0402', 'C25744', P, 'CHG_N', '+3V3')
two('C2', '10uF', 'C0805', 'C89827', P, 'VBAT', 'GND')
part('J2', 'Battery', 'PH2', 'C295747', P, [
    ('1', '+', 'VBAT'), ('2', '-', 'GND'), ('MP', 'MP', 'GND')])
part('SW1', 'JS102011JAQN', 'rev4:S1', 'C221658', P, [
    ('1', 'OFF', None), ('2', 'COM', 'VBAT'), ('3', 'ON', 'VBAT_SW')])
part('Q1', 'Si2301', 'SOT23', 'C727151', P, [
    ('1', 'G', 'VBUS'), ('2', 'S', 'VSYS'), ('3', 'D', 'VBAT_SW')])
two('R5', '10k', 'R0402', 'C25744', P, 'VBUS', 'GND')
part('D1', 'B5819W', 'SOD123', 'C22463588', P, [
    ('1', 'K', 'VSYS'), ('2', 'A', 'VBUS')])
part('U3', 'ME6211C33M5', 'SOT23-5', 'C82942', P, [
    ('1', 'VIN', 'VSYS'), ('2', 'GND', 'GND'), ('3', 'EN', 'VSYS'), ('4', 'NC', None),
    ('5', 'VOUT', '+3V3')])
two('C3', '10uF', 'C0805', 'C89827', P, 'VSYS', 'GND')
two('C4', '100uF', 'C1206', 'C7432784', P, '+3V3', 'GND')
two('C5', '10uF', 'C0805', 'C89827', P, '+3V3', 'GND')
# battery and USB sense dividers into ADC1
two('R6', '100k', 'R0402', 'C25741', P, 'VBAT', 'VBAT_SENSE')
two('R7', '100k', 'R0402', 'C25741', P, 'VBAT_SENSE', 'GND')
two('C6', '100nF', 'C0402', 'C56392', P, 'VBAT_SENSE', 'GND')
two('R8', '100k', 'R0402', 'C25741', P, 'VBUS', 'VBUS_SENSE')
two('R9', '100k', 'R0402', 'C25741', P, 'VBUS_SENSE', 'GND')

# MCU ------------------------------------------------------------------------
M = 'mcu'
S3_NETS = {
    1: 'GND', 2: '+3V3', 3: 'EN', 4: 'VBAT_SENSE', 5: 'VBUS_SENSE', 6: 'CHG_N',
    7: 'TP_INT', 8: 'I2C_SDA', 9: 'I2C_SCL', 10: 'LCD_CS', 11: 'LCD_MOSI', 12: 'LCD_SCK',
    13: 'LCD_DC', 14: 'LCD_RST', 15: 'TP_RST', 16: 'TOF_XSHUT', 17: 'TOF_INT',
    18: None, 19: 'USB_DN', 20: 'USB_DP', 21: 'LCD_BL', 47: 'IMU_INT1', 48: 'MAG_DRDY',
    38: 'OUT1_EN', 39: 'OUT2_EN', 40: 'LCD_TE', 0: 'BOOT', 43: 'UART_TX', 44: 'UART_RX',
}
S3_PINS = [(1, 'GND'), (2, '3V3'), (3, 'EN'), (4, 'IO4'), (5, 'IO5'), (6, 'IO6'), (7, 'IO7'),
           (8, 'IO15'), (9, 'IO16'), (10, 'IO17'), (11, 'IO18'), (12, 'IO8'), (13, 'IO19'),
           (14, 'IO20'), (15, 'IO3'), (16, 'IO46'), (17, 'IO9'), (18, 'IO10'), (19, 'IO11'),
           (20, 'IO12'), (21, 'IO13'), (22, 'IO14'), (23, 'IO21'), (24, 'IO47'), (25, 'IO48'),
           (26, 'IO45'), (27, 'IO0'), (28, 'IO35'), (29, 'IO36'), (30, 'IO37'), (31, 'IO38'),
           (32, 'IO39'), (33, 'IO40'), (34, 'IO41'), (35, 'IO42'), (36, 'RXD0'), (37, 'TXD0'),
           (38, 'IO2'), (39, 'IO1'), (40, 'GND'), (41, 'GND')]


def s3_net(name):
    if name in ('GND', '3V3', 'EN'):
        return {'GND': 'GND', '3V3': '+3V3', 'EN': 'EN'}[name]
    if name == 'RXD0':
        return S3_NETS.get(44)
    if name == 'TXD0':
        return S3_NETS.get(43)
    return S3_NETS.get(int(name[2:]))


part('U4', 'ESP32-S3-WROOM-1-N16R8', 'S3', 'C2913202', M,
     [(str(n), nm, s3_net(nm)) for n, nm in S3_PINS])
two('C7', '22uF', 'C0805', 'C45783', M, '+3V3', 'GND')
two('C8', '100nF', 'C0402', 'C56392', M, '+3V3', 'GND')
two('R10', '10k', 'R0402', 'C25744', M, '+3V3', 'EN')
two('C9', '1uF', 'C0402', 'C52923', M, 'EN', 'GND')
two('R11', '10k', 'R0402', 'C25744', M, '+3V3', 'BOOT')
part('SW2', 'BOOT', 'TACT', 'C318884', M, [('1', '1', 'BOOT'), ('2', '2', 'GND')])
for i, net in enumerate(['UART_TX', 'UART_RX', 'EN']):
    part(f'TP{i + 1}', net, 'rev4:TP', '', M, [('1', '1', net)])

# Screen, touch and sensors --------------------------------------------------
U = 'ui'
# 2.0 in 240x320 IPS panel with CST816D touch, 21-pin 0.5 mm FPC (the bare
# panel inside Waveshare's "2inch Capacitive Touch LCD"; pin order from that
# module's schematic, connector L2). Confirm LEDA/LEDK on the sample.
LCD = [('1', 'GND', 'GND'), ('2', 'LEDK', 'LCD_LEDK'), ('3', 'LEDA', 'LCD_LEDA'),
       ('4', 'GND', 'GND'), ('5', 'VCC', '+3V3'), ('6', 'VCC', '+3V3'),
       ('7', 'GND', 'GND'), ('8', 'RESET', 'LCD_RST'), ('9', 'SCL', 'LCD_SCK'),
       ('10', 'TE', 'LCD_TE'), ('11', 'SDA', 'LCD_MOSI'), ('12', 'RS', 'LCD_DC'),
       ('13', 'CS', 'LCD_CS'), ('14', 'GND', 'GND'), ('15', 'TP_VDD', '+3V3'),
       ('16', 'TP_RESET', 'TP_RST'), ('17', 'TP_INT', 'TP_INT'), ('18', 'TP_SDA', 'I2C_SDA'),
       ('19', 'TP_SCL', 'I2C_SCL'), ('20', 'GND', 'GND'), ('21', 'GND', 'GND'),
       ('MP', 'MP', 'GND')]
part('J3', 'LCD+CTP FPC 21P', 'FPC21', '', U, LCD)
two('R12', '10R', 'R0402', 'C25077', U, '+3V3', 'LCD_LEDA')
part('Q2', 'AO3400', 'SOT23', 'C2938367', U, [
    ('1', 'G', 'LCD_BL'), ('2', 'S', 'GND'), ('3', 'D', 'LCD_LEDK')])
two('R13', '100k', 'R0402', 'C25741', U, 'LCD_BL', 'GND')
two('R14', '4.7k', 'R0402', 'C25900', U, '+3V3', 'I2C_SDA')
two('R15', '4.7k', 'R0402', 'C25900', U, '+3V3', 'I2C_SCL')
# VL53L4CD, front face, below the screen
part('U5', 'VL53L4CD', 'ST_VL53L4CD_LGA-12_4.4x2.4mm', 'C3178291', U, [
    ('1', 'AVDDVCSEL', '+3V3'), ('2', 'AVSSVCSEL', 'GND'), ('3', 'GND', 'GND'),
    ('4', 'GND2', 'GND'), ('5', 'XSHUT', 'TOF_XSHUT'), ('6', 'GND3', 'GND'),
    ('7', 'GPIO1', 'TOF_INT'), ('8', 'DNC', None), ('9', 'SDA', 'I2C_SDA'),
    ('10', 'SCL', 'I2C_SCL'), ('11', 'AVDD', '+3V3'), ('12', 'GND4', 'GND')])
two('C10', '100nF', 'C0402', 'C56392', U, '+3V3', 'GND')
two('C11', '4.7uF', 'C0402', 'C23733', U, '+3V3', 'GND')
two('R16', '10k', 'R0402', 'C25744', U, '+3V3', 'TOF_INT')
two('R17', '10k', 'R0402', 'C25744', U, '+3V3', 'TOF_XSHUT')
# LSM6DSO accel + gyro, I2C address 0x6A
part('U6', 'LSM6DSO', 'ST_LGA-14_2.5x3mm_P0.5mm', 'C2655100', U, [
    ('1', 'SDO/SA0', 'GND'), ('2', 'SDX', 'GND'), ('3', 'SCX', 'GND'),
    ('4', 'INT1', 'IMU_INT1'), ('5', 'VDDIO', '+3V3'), ('6', 'GND', 'GND'), ('7', 'GND', 'GND'),
    ('8', 'VDD', '+3V3'), ('9', 'INT2', None), ('10', 'OCS_AUX', None),
    ('11', 'SDO_AUX', None), ('12', 'CS', '+3V3'), ('13', 'SCL', 'I2C_SCL'),
    ('14', 'SDA', 'I2C_SDA')])
two('C12', '100nF', 'C0402', 'C56392', U, '+3V3', 'GND')
two('C13', '100nF', 'C0402', 'C56392', U, '+3V3', 'GND')
# LIS3MDL magnetometer, I2C address 0x1C
part('U7', 'LIS3MDL', 'ST_LGA-12_2x2mm_P0.5mm', 'C478483', U, [
    ('1', 'SCL', 'I2C_SCL'), ('2', 'GND', 'GND'), ('3', 'GND', 'GND'), ('4', 'C1', 'MAG_C1'),
    ('5', 'VDD', '+3V3'), ('6', 'VDDIO', '+3V3'), ('7', 'INT', None), ('8', 'DRDY', 'MAG_DRDY'),
    ('9', 'SDO/SA1', 'GND'), ('10', 'CS', '+3V3'), ('11', 'SDA', 'I2C_SDA'), ('12', 'GND', 'GND')])
two('C14', '100nF', 'C0402', 'C56392', U, 'MAG_C1', 'GND')
two('C15', '100nF', 'C0402', 'C56392', U, '+3V3', 'GND')

# Accessory port -------------------------------------------------------------
A = 'port'
part('J4', 'PH6 accessory', 'PH6', 'TBD', A, [
    ('1', 'GND', 'GND'), ('2', 'VSYS', 'VSYS_PORT'), ('3', 'OUT1', 'OUT1'),
    ('4', 'OUT2', 'OUT2'), ('5', 'SDA', 'I2C_SDA'), ('6', 'SCL', 'I2C_SCL')])
part('F1', '0.5A PTC', 'F0805', 'C269104', A, [('1', '1', 'VSYS'), ('2', '2', 'VSYS_PORT')])
part('U8', 'USBLC6-2SC6', 'SOT23-6', 'C7519', A, [
    ('1', 'IO1', 'OUT1'), ('2', 'GND', 'GND'), ('3', 'IO2', 'OUT2'),
    ('4', 'IO2', 'OUT2'), ('5', 'VBUS', 'VSYS_PORT'), ('6', 'IO1', 'OUT1')])
part('U9', 'USBLC6-2SC6', 'SOT23-6', 'C7519', A, [
    ('1', 'IO1', 'I2C_SDA'), ('2', 'GND', 'GND'), ('3', 'IO2', 'I2C_SCL'),
    ('4', 'IO2', 'I2C_SCL'), ('5', 'VBUS', 'VSYS_PORT'), ('6', 'IO1', 'I2C_SDA')])
# Two high-side 3.3 V outputs, same stage as rev4 (BC817 + MMBT4403).
for n, (q_lo, q_hi, rb, rpu, rlink) in enumerate(
        [('Q3', 'Q4', 'R18', 'R19', 'R20'), ('Q5', 'Q6', 'R21', 'R22', 'R23')], 1):
    en, mid, base = f'OUT{n}_EN', f'OUT{n}_N', f'OUT{n}_B'
    two(rb, '1k', 'R0402', 'C11702', A, en, f'OUT{n}_LB')
    part(q_lo, 'BC817', 'SOT23', 'C8658', A, [
        ('1', 'B', f'OUT{n}_LB'), ('2', 'E', 'GND'), ('3', 'C', mid)])
    two(rpu, '10k', 'R0402', 'C25744', A, mid, '+3V3')
    two(rlink, '1k', 'R0402', 'C11702', A, mid, base)
    part(q_hi, 'MMBT4403', 'SOT23', 'C78864', A, [
        ('1', 'B', base), ('2', 'E', '+3V3'), ('3', 'C', f'OUT{n}')])

SHEETS = [
    ('power', 'power.kicad_sch', 'USB-C, charging and power'),
    ('mcu', 'mcu.kicad_sch', 'ESP32-S3'),
    ('ui', 'ui.kicad_sch', 'Screen, touch and sensors'),
    ('port', 'port.kicad_sch', 'Accessory port'),
]


# ------------------------------------------------------------------ helpers
def nets():
    out = {}
    for p in PARTS:
        for num, name, net in p['pins']:
            if net:
                out.setdefault(net, []).append((p['ref'], num))
    return out


def check_netlist():
    problems = []
    for net, conns in sorted(nets().items()):
        if len({r for r, _ in conns}) < 2:
            problems.append(f'net {net} has one part: {conns}')
    refs = [p['ref'] for p in PARTS]
    dup = {r for r in refs if refs.count(r) > 1}
    if dup:
        problems.append(f'duplicate refs {dup}')
    return problems


def fp_id(p):
    fp = p['fp']
    if fp.startswith('rev4:'):
        return f"{LIB}:{ {'S1': 'SW_SPDT_JS102011JAQN', 'TP': 'TestPoint_Pad_1.0mm'}[fp[5:]] }"
    if fp in STD:
        return f'{LIB}:{STD[fp][1]}'
    return f'{LIB}:{fp}'


# ------------------------------------------------------------- footprint lib
def build_footprints():
    pretty = HERE / f'{LIB}.pretty'
    if pretty.exists():
        shutil.rmtree(pretty)
    pretty.mkdir()
    for lib, name in STD.values():
        shutil.copy(KICAD_FP / f'{lib}.pretty' / f'{name}.kicad_mod', pretty)
    for name, text in custom_footprints().items():
        (pretty / f'{name}.kicad_mod').write_text(text)
    # Slide switch footprint proven on rev4 (with its locating holes).
    s1 = (REV4 / '217A_dttrainer_rev4.pretty' / 'S1.kicad_mod').read_text()
    s1 = s1.replace('(footprint "S1"', '(footprint "SW_SPDT_JS102011JAQN"', 1)
    (pretty / 'SW_SPDT_JS102011JAQN.kicad_mod').write_text(s1)
    shutil.copy(KICAD_FP / 'MountingHole.pretty' / 'MountingHole_2.2mm_M2.kicad_mod', pretty)
    shutil.copy(KICAD_FP / 'TestPoint.pretty' / 'TestPoint_Pad_D1.0mm.kicad_mod',
                pretty / 'TestPoint_Pad_1.0mm.kicad_mod')
    t = (pretty / 'TestPoint_Pad_1.0mm.kicad_mod').read_text()
    (pretty / 'TestPoint_Pad_1.0mm.kicad_mod').write_text(
        t.replace('(footprint "TestPoint_Pad_D1.0mm"', '(footprint "TestPoint_Pad_1.0mm"', 1))
    (HERE / 'fp-lib-table').write_text(
        '(fp_lib_table\n  (version 7)\n'
        f'  (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/{LIB}.pretty")(options "")(descr ""))\n)\n')


# ---------------------------------------------------------------- schematic
G = 2.54


def fmt(v):
    return f'{round(v, 4):g}'


def sym_geometry(p):
    pins = p['pins']
    half = (len(pins) + 1) // 2
    left, right = pins[:half], pins[half:]
    rows = max(len(left), 1)
    longest = max(len(n) for _, n, _ in pins)
    w = max(10.16, round((longest * 1.27 * 2 + 5.08) / G) * G)
    h = rows * G
    return left, right, w, h


def in_bom(p):
    return 'no' if p['ref'].startswith('TP') else 'yes'


def lib_symbol(p, prefix=True):
    left, right, w, h = sym_geometry(p)
    name = f'{LIB}:{p["ref"]}' if prefix else p['ref']
    top = (len(left) - 1) * G / 2
    s = [f'(symbol "{name}" (pin_names (offset 0.508)) (in_bom {in_bom(p)}) (on_board yes)',
         f'(property "Reference" "{p["ref"].rstrip("0123456789")}" (at 0 {fmt(top + 3.81)} 0)'
         ' (effects (font (size 1.27 1.27))))',
         f'(property "Value" "{p["value"]}" (at 0 {fmt(-top - 3.81)} 0) (effects (font (size 1.27 1.27))))',
         f'(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
         f'(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
         f'(symbol "{p["ref"]}_0_1" (rectangle (start {fmt(-w / 2)} {fmt(top + G / 2)})'
         f' (end {fmt(w / 2)} {fmt(-top - G / 2)}) (stroke (width 0.254) (type default))'
         ' (fill (type background))))',
         f'(symbol "{p["ref"]}_1_1"']
    for side, lst in ((-1, left), (1, right)):
        for i, (num, nm, net) in enumerate(lst):
            x = side * (w / 2 + 5.08)
            y = top - i * G
            kind = 'no_connect' if net is None else 'passive'
            s.append(f'(pin {kind} line (at {fmt(x)} {fmt(y)} {0 if side < 0 else 180})'
                     f' (length 5.08) (name "{nm}" (effects (font (size 1.016 1.016))))'
                     f' (number "{num}" (effects (font (size 1.016 1.016)))))')
    s.append('))')
    return ' '.join(s)


def pin_points(p, at):
    """Pin end points on the sheet (sheet Y runs down, symbol Y up)."""
    left, right, w, h = sym_geometry(p)
    top = (len(left) - 1) * G / 2
    out = []
    for side, lst in ((-1, left), (1, right)):
        for i, (num, nm, net) in enumerate(lst):
            out.append((num, net, side, at[0] + side * (w / 2 + 5.08), at[1] - (top - i * G)))
    return out


def build_schematic(root_uuid):
    sheet_uuid = {key: uid('sheet', key) for key, _, _ in SHEETS}
    for key, fname, title in SHEETS:
        parts = [p for p in PARTS if p['sheet'] == key]
        body = []
        x, y = 50.8, 38.1
        col_w = 0
        for p in parts:
            left, right, w, h = sym_geometry(p)
            if y + h > 190:
                x += col_w + 60.96
                y = 38.1
                col_w = 0
            at = (round(x / G) * G, round((y + h / 2) / G) * G)
            col_w = max(col_w, w + 20)
            y += h + 15.24
            su = uid('sym', p['ref'])
            props = [('Reference', p['ref'], -h / 2 - 2.54, False),
                     ('Value', p['value'], h / 2 + 2.54, False),
                     ('Footprint', fp_id(p), 0, True), ('Datasheet', '', 0, True),
                     ('LCSC', p['lcsc'] or 'TBD', 0, True)]
            ptxt = ''.join(
                f'(property "{k}" "{v}" (at {fmt(at[0])} {fmt(at[1] + dy)} 0)'
                f' (effects (font (size 1.27 1.27)){" hide" if hid else ""}))'
                for k, v, dy, hid in props)
            pins = ''.join(f'(pin "{num}" (uuid {uid("pin", p["ref"], num, i)}))'
                           for i, (num, _, _) in enumerate(p['pins']))
            body.append(
                f'(symbol (lib_id "{LIB}:{p["ref"]}") (at {fmt(at[0])} {fmt(at[1])} 0) (unit 1)'
                f' (in_bom {in_bom(p)}) (on_board yes) (dnp {"yes" if p["dnp"] else "no"}) (uuid {su}) {ptxt}'
                f' {pins} (instances (project "{STEM}" (path "/{root_uuid}/{sheet_uuid[key]}"'
                f' (reference "{p["ref"]}") (unit 1)))))')
            for num, net, side, px, py in pin_points(p, at):
                if net is None:
                    body.append(f'(no_connect (at {fmt(px)} {fmt(py)}) (uuid {uid("nc", p["ref"], num, px, py)}))')
                    continue
                lx = px + side * 5.08
                body.append(f'(wire (pts (xy {fmt(px)} {fmt(py)}) (xy {fmt(lx)} {fmt(py)}))'
                            f' (stroke (width 0) (type default)) (uuid {uid("w", p["ref"], num, px, py)}))')
                ang = 180 if side < 0 else 0
                just = 'right' if side < 0 else 'left'
                body.append(f'(global_label "{net}" (shape bidirectional) (at {fmt(lx)} {fmt(py)} {ang})'
                            f' (effects (font (size 1.016 1.016)) (justify {just}))'
                            f' (uuid {uid("gl", p["ref"], num, px, py)})'
                            f' (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {fmt(lx)} {fmt(py)} 0)'
                            ' (effects (font (size 1.27 1.27)) hide)))')
        libs = ' '.join(lib_symbol(p) for p in parts)
        notes = ''
        if key == 'ui':
            notes = (f'(text "J3: 2.0 in 240x320 IPS + CST816D panel, 21-pin 0.5 mm FPC, pin order from the Waveshare 2inch Capacitive Touch LCD schematic (L2). Verify LEDA/LEDK and FPC contact side on the sample."'
                     f' (at 50.8 25.4 0) (effects (font (size 2 2)) (justify left)) (uuid {uid("note", key)}))')
        if key == 'port':
            notes = (f'(text "PH6: 1 GND, 2 VSYS (PTC), 3 OUT1, 4 OUT2, 5 SDA, 6 SCL. TRRS adapter: tip GND, ring 1 OUT1, ring 2 OUT2."'
                     f' (at 50.8 25.4 0) (effects (font (size 2 2)) (justify left)) (uuid {uid("note", key)}))')
        text = (f'(kicad_sch (version 20230121) (generator eeschema) (uuid {sheet_uuid[key]}) (paper "A3")'
                f' (title_block (title "{title}") (rev "5.0") (company "DTT v2")'
                f' (comment 1 "CERN-OHL-S v2; generated by build_dtt_v2.py"))'
                f' (lib_symbols {libs}) {notes} {"".join(body)})\n')
        (HERE / fname).write_text(text)
    # root
    sheets = []
    for i, (key, fname, title) in enumerate(SHEETS):
        sx, sy = 35 + (i % 2) * 130, 65 + (i // 2) * 60
        sheets.append(
            f'(sheet (at {sx} {sy}) (size 105 35) (stroke (width 0.254) (type default))'
            f' (fill (color 0 0 0 0)) (uuid {sheet_uuid[key]})'
            f' (property "Sheetname" "{title}" (at {sx} {sy - 2} 0) (effects (font (size 1.27 1.27))))'
            f' (property "Sheetfile" "{fname}" (at {sx} {sy + 38} 0) (effects (font (size 1.27 1.27))))'
            f' (instances (project "{STEM}" (path "/{root_uuid}" (page "{i + 2}")))))')
    root = (f'(kicad_sch (version 20230121) (generator eeschema) (uuid {root_uuid}) (paper "A4")'
            f' (title_block (title "DTT v2") (rev "5.0") (comment 1 "CERN-OHL-S v2"))'
            f' (lib_symbols)'
            f' (text "DTT v2 (rev5): ESP32-S3, 2.0 in touch screen, ToF, 9DOF IMU, PH6 accessory port."'
            f' (at 25 25 0) (effects (font (size 2 2)) (justify left)) (uuid {uid("roottext")}))'
            f' {"".join(sheets)} (sheet_instances (path "/" (page "1"))))\n')
    (HERE / f'{STEM}.kicad_sch').write_text(root)


# -------------------------------------------------------------------- board
def mm(v):
    return pcbnew.FromMM(v)


def set_field(fp, name, value):
    if hasattr(fp, 'SetField'):      # KiCad 8+
        fp.SetField(name, value)
    else:                            # KiCad 7
        fp.SetProperty(name, value)


def build_board():
    ox, oy = PARAMS['origin']
    W, H, R = PARAMS['board_w'], PARAMS['board_h'], PARAMS['corner_r']
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.SetAuxOrigin(pcbnew.VECTOR2I(mm(ox), mm(oy + H)))
    ds.SetGridOrigin(pcbnew.VECTOR2I(mm(ox), mm(oy)))
    ds.m_MinThroughDrill = mm(0.2)       # S3 module thermal vias
    ds.m_CopperEdgeClearance = mm(0.3)

    def seg(x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(mm(ox + x1), mm(oy + y1)))
        s.SetEnd(pcbnew.VECTOR2I(mm(ox + x2), mm(oy + y2)))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)

    def arc(cx, cy, sx, sy, ang):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetCenter(pcbnew.VECTOR2I(mm(ox + cx), mm(oy + cy)))
        s.SetStart(pcbnew.VECTOR2I(mm(ox + sx), mm(oy + sy)))
        s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T), True)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)

    seg(R, 0, W - R, 0); seg(W, R, W, H - R); seg(W - R, H, R, H); seg(0, H - R, 0, R)
    arc(W - R, R, W - R, 0, 90); arc(W - R, H - R, W, H - R, 90)
    arc(R, H - R, R, H, 90); arc(R, R, 0, R, 90)

    netinfo = {}
    nc = {(p['ref'], num): f'unconnected-({p["ref"]}-{nm}-Pad{num})'
          for p in PARTS for num, nm, net in p['pins'] if net is None}
    for name in sorted(nets()) + sorted(set(nc.values())):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni

    pretty = str(HERE / f'{LIB}.pretty')
    for i, (x, y) in enumerate(PARAMS['holes'], 1):   # board-only: no symbol, not in the BOM
        fp = pcbnew.FootprintLoad(pretty, 'MountingHole_2.2mm_M2')
        fp.SetFPID(pcbnew.LIB_ID(LIB, 'MountingHole_2.2mm_M2'))
        fp.SetReference(f'H{i}')
        fp.SetValue('M2 case screw')
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM
                         | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        board.Add(fp)
        fp.SetPosition(pcbnew.VECTOR2I(mm(ox + x), mm(oy + y)))
        fp.Reference().SetLayer(pcbnew.F_Fab)
    for p in PARTS:
        fpname = fp_id(p).split(':', 1)[1]
        fp = pcbnew.FootprintLoad(pretty, fpname)
        fp.SetFPID(pcbnew.LIB_ID(LIB, fpname))
        fp.SetReference(p['ref'])
        fp.SetValue(p['value'])
        set_field(fp, 'LCSC', p['lcsc'] or 'TBD')
        board.Add(fp)
        x, y, rot, side = p['place']
        fp.SetPosition(pcbnew.VECTOR2I(mm(ox + x), mm(oy + y)))
        fp.SetOrientationDegrees(rot)
        if side == 'B':
            fp.Flip(fp.GetPosition(), True)
        # Dense board: reference designators live on the fab layer, not silk.
        fp.Reference().SetLayer(pcbnew.B_Fab if side == 'B' else pcbnew.F_Fab)
        pinnet = {}
        for num, _, net in p['pins']:
            if net:
                pinnet.setdefault(num, net)
        for pad in fp.Pads():
            n = pad.GetNumber()
            if n in pinnet:
                pad.SetNet(netinfo[pinnet[n]])
            elif (p['ref'], n) in nc:
                pad.SetNet(netinfo[nc[(p['ref'], n)]])
            elif n and n not in pinnet and p['ref'] == 'U4' and n == '41':
                pad.SetNet(netinfo['GND'])
        fp.SetPath(pcbnew.KIID_PATH(f'/{uid("sheet", p["sheet"])}/{uid("sym", p["ref"])}'))
        for z in fp.Zones():   # the S3 module's own antenna keepout: copper only, so the
            z.SetDoNotAllowFootprints(False)   # case-screw holes may sit beside it
            z.SetDoNotAllowPads(False)

    # Antenna keepout across the top strip, both layers.
    ka = pcbnew.ZONE(board)
    ka.SetIsRuleArea(True)
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.F_Cu)
    ls.AddLayer(pcbnew.B_Cu)
    ka.SetLayerSet(ls)
    ka.SetDoNotAllowCopperPour(True)
    ka.SetDoNotAllowTracks(True)
    ka.SetDoNotAllowVias(True)
    ka.SetDoNotAllowPads(False)
    ka.SetDoNotAllowFootprints(False)
    ka.SetZoneName('S3 antenna keepout')
    o = ka.Outline()
    o.NewOutline()
    a = PARAMS['antenna_strip']
    for px, py in [(0, 0), (W, 0), (W, a), (0, a)]:
        o.Append(mm(ox + px), mm(oy + py))
    board.Add(ka)

    # GND pours on both layers below the antenna strip.
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(netinfo['GND'])
        z.SetMinThickness(mm(0.2))
        z.SetLocalClearance(mm(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)   # assembled by machine: no reliefs
        z.SetZoneName(f'GND {"top" if layer == pcbnew.F_Cu else "bottom"}')
        o = z.Outline()
        o.NewOutline()
        for px, py in [(0, a), (W, a), (W, H), (0, H)]:
            o.Append(mm(ox + px), mm(oy + py))
        board.Add(z)

    # Screen outline on the front courtyard-free user layer, for reference.
    sw, sh = PARAMS['screen_w'], PARAMS['screen_h']
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_RECT)
    s.SetStart(pcbnew.VECTOR2I(mm(ox + (W - sw) / 2), mm(oy + a)))
    s.SetEnd(pcbnew.VECTOR2I(mm(ox + (W + sw) / 2), mm(oy + a + sh)))
    s.SetLayer(pcbnew.Dwgs_User)
    s.SetWidth(mm(0.15))
    board.Add(s)
    t = pcbnew.PCB_TEXT(board)
    t.SetText('2.0 in screen outline (assumed)')
    t.SetPosition(pcbnew.VECTOR2I(mm(ox + W / 2), mm(oy + a + sh / 2)))
    t.SetLayer(pcbnew.Dwgs_User)
    board.Add(t)

    path = HERE / f'{STEM}.kicad_pcb'
    board.Save(str(path))
    # Fill zones on a reloaded board so connectivity is built.
    board = pcbnew.LoadBoard(str(path))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(path))
    return path


def build_project():
    pro = json.loads((REV4 / '217A_dttrainer_rev4.kicad_pro').read_text())
    pro['meta']['filename'] = f'{STEM}.kicad_pro'
    rules = pro['board']['design_settings']['rules']
    rules['min_through_hole_diameter'] = 0.2   # S3 module thermal vias
    rules['min_copper_edge_clearance'] = 0.3
    pro['sheets'] = [[uid('root'), 'Root']] + [[uid('sheet', k), t] for k, _, t in SHEETS]
    classes = pro['net_settings']['classes']
    default = next(c for c in classes if c['name'] == 'Default')
    classes[:] = [default,
                  dict(default, name='Power', track_width=0.4),
                  dict(default, name='USB_D', track_width=0.2)]
    pro['net_settings']['netclass_patterns'] = (
        [{'netclass': 'Power', 'pattern': n} for n in POWER_NETS]
        + [{'netclass': 'USB_D', 'pattern': n} for n in ('USB_DP', 'USB_DN')])
    (HERE / f'{STEM}.kicad_pro').write_text(json.dumps(pro, indent=2) + '\n')
    syms = ' '.join(lib_symbol(p, prefix=False) for p in PARTS)
    (HERE / f'{LIB}.kicad_sym').write_text(
        f'(kicad_symbol_lib (version 20220914) (generator build_dtt_v2) {syms})\n')
    (HERE / 'sym-lib-table').write_text(
        '(sym_lib_table\n  (version 7)\n'
        f'  (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/{LIB}.kicad_sym")(options "")(descr ""))\n)\n')


def main():
    problems = check_netlist()
    if problems:
        raise SystemExit('\n'.join(problems))
    build_footprints()
    build_schematic(uid('root'))
    path = build_board()
    build_project()   # after the board: saving the board rewrites the project file
    print(f'{len(PARTS)} parts, {len(nets())} nets -> {path.name}')


if __name__ == '__main__':
    main()
