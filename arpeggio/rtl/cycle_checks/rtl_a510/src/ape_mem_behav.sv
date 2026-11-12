// Behavioural single-port memories of the Antiphase engine (simulation, flip-flop synthesis, FPGA inference).
// Port timing = the compiler macros' flow-through mode: inputs sampled at the rising edge; read data valid in the next
// cycle and held until the next read; a write leaves rdata unchanged. The macro wrappers with the same module names
// and ports live on the synthesis server only (kit cell and pin names).
`default_nettype none
module ape_gmem #(parameter int D = 32, parameter int CW = 14) (
    input  wire logic                 clk,
    input  wire logic                 ce,
    input  wire logic                 we,
    input  wire logic [$clog2(D)-1:0] addr,
    input  wire logic [D*CW-1:0]      wdata,
    output logic      [D*CW-1:0]      rdata
);
    logic [D*CW-1:0] mem [D];
    always_ff @(posedge clk) if (ce) begin
        if (we) mem[addr] <= wdata;
        else rdata <= mem[addr];
    end
endmodule

module ape_tmem (
    input  wire logic        clk,
    input  wire logic        ce,
    input  wire logic        we,
    input  wire logic [9:0]  addr,
    input  wire logic [31:0] wdata,
    output logic      [31:0] rdata
);
    logic [31:0] mem [1024];
    always_ff @(posedge clk) if (ce) begin
        if (we) mem[addr] <= wdata;
        else rdata <= mem[addr];
    end
endmodule
`default_nettype wire
