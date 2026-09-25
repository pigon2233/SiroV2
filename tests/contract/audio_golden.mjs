import fs from "node:fs";

const fixture = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const bytes = Buffer.from(fixture.encoded_hex, "hex");
if (bytes.subarray(0, 4).toString("ascii") !== "SRA1") throw new Error("magic");
const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
if (view.getUint8(4) !== 1 || view.getUint16(6, false) !== 32) throw new Error("header");
if (view.getBigUint64(8, false).toString(16).padStart(16, "0") !== fixture.stream_token) throw new Error("token");
if (view.getUint32(16, false) !== fixture.sequence) throw new Error("sequence");
if (view.getBigUint64(20, false).toString(16).padStart(16, "0") !== fixture.sample_offset) throw new Error("offset");
if (view.getUint32(28, false) !== bytes.length - 32) throw new Error("length");
process.stdout.write("ok\n");
