#!/usr/bin/env python3

#
# This file is part of LiteDRAM.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import argparse

from migen import *

from litex.boards.platforms import kc705

from litex.soc.cores.clock import *
from litex.soc.interconnect.csr import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *

from litedram.phy import s7ddrphy
from litedram.modules import MT8JTF12864

from liteeth.phy import LiteEthPHY

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module, AutoCSR):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys_pll   = ClockDomain()
        self.clock_domains.cd_sys       = ClockDomain()
        self.clock_domains.cd_sys4x     = ClockDomain(reset_less=True)
        self.clock_domains.cd_clk200    = ClockDomain()

        # # #

        self.submodules.main_pll = main_pll = S7PLL(speedgrade=-2)
        self.comb += main_pll.reset.eq(platform.request("cpu_reset"))
        main_pll.register_clkin(platform.request("clk200"), 200e6)
        main_pll.create_clkout(self.cd_sys_pll, sys_clk_freq)
        main_pll.create_clkout(self.cd_clk200,  200e6)
        main_pll.expose_drp()
        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_clk200)

        sys_clk_counter = Signal(32)
        self.sync += sys_clk_counter.eq(sys_clk_counter + 1)
        self.sys_clk_counter = CSRStatus(32)
        self.comb += self.sys_clk_counter.status.eq(sys_clk_counter)

        self.submodules.pll = pll = S7PLL(speedgrade=-2)
        self.comb += pll.reset.eq(~main_pll.locked)
        pll.register_clkin(self.cd_sys_pll.clk, sys_clk_freq)
        pll.create_clkout(self.cd_sys,    sys_clk_freq)
        pll.create_clkout(self.cd_sys4x,  4*sys_clk_freq)

# Bench SoC ----------------------------------------------------------------------------------------

class BenchSoC(SoCCore):
    def __init__(self, sys_clk_freq=int(175e6)):
        platform = kc705.Platform()

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq,
            integrated_rom_size = 0x8000,
            integrated_rom_mode = "rw",
            csr_data_width      = 32,
            uart_name           = "crossover")

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = _CRG(platform, sys_clk_freq)
        self.add_csr("crg")

        # DDR3 SDRAM -------------------------------------------------------------------------------
        self.submodules.ddrphy = s7ddrphy.K7DDRPHY(platform.request("ddram"),
            memtype      = "DDR3",
            nphases      = 4,
            sys_clk_freq = sys_clk_freq,
            cmd_latency  = 1)
        self.add_csr("ddrphy")
        self.add_sdram("sdram",
            phy    = self.ddrphy,
            module = MT8JTF12864(sys_clk_freq, "1:4"),
            origin = self.mem_map["main_ram"]
        )

        # Etherbone --------------------------------------------------------------------------------
        self.submodules.ethphy = LiteEthPHY(
            clock_pads = self.platform.request("eth_clocks"),
            pads       = self.platform.request("eth"),
            clk_freq   = self.clk_freq)
        self.add_csr("ethphy")
        self.add_etherbone(phy=self.ethphy)

        # Leds -------------------------------------------------------------------------------------
        from litex.soc.cores.led import LedChaser
        self.submodules.leds = LedChaser(
            pads         = platform.request_all("user_led"),
            sys_clk_freq = sys_clk_freq)
        self.add_csr("leds")

# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteDRAM Bench on KC705")
    parser.add_argument("--build", action="store_true", help="Build bitstream")
    parser.add_argument("--load",  action="store_true", help="Load bitstream")
    parser.add_argument("--test",  action="store_true", help="Run Test")
    args = parser.parse_args()

    soc     = BenchSoC()
    builder = Builder(soc, csr_csv="csr.csv")
    builder.build(run=args.build)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".bit"))

    if args.test:
        from common import s7_bench_test
        s7_bench_test(
            freq_min      = 60e6,
            freq_max      = 180e6,
            freq_step     = 10e6,
            vco_freq      = soc.crg.main_pll.compute_config()["vco"],
            bios_filename = "build/kc705/software/bios/bios.bin",
            bios_timeout  = 10,
        )

if __name__ == "__main__":
    main()