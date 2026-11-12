// RED-phase stub with the engine's ports: accepts every command, never produces an output beat.
`default_nettype none
module ape_engine #(parameter int D = 32, parameter int A = 4, parameter int SEEDL = 1, parameter int PMAX = 6,
                    parameter int CW = 14, parameter int WW = 24, parameter int EW = 36) (
    input wire logic clk, input wire logic rst_n, input wire logic in_valid, output logic in_ready,
    input wire logic [2:0] in_op, input wire logic [9:0] in_addr, input wire logic [D*CW-1:0] in_data,
    output logic out_valid, output logic [15:0] out_tag, output logic [11:0] out_r, output logic [2:0] out_p,
    output logic [D-1:0] out_bits, output logic [EW-1:0] out_de, output logic busy);
    assign in_ready = 1'b1; assign out_valid = 1'b0; assign out_tag = '0; assign out_r = '0; assign out_p = '0;
    assign out_bits = '0; assign out_de = '0; assign busy = 1'b0;
endmodule
`default_nettype wire
