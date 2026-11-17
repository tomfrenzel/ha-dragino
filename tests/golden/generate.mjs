// Generates vectors.json by running the vendor JavaScript decoders over many payloads.
//
// The decoders are not part of this repository. Point CATALOG_CODECS at a local copy of
// vendors/dragino/codecs of https://github.com/chirpstack/chirpstack-device-profiles:
//
//   node generate.mjs  (writes vectors.json next to this file)
//
// Timestamps are dropped from the expectations because they depend on the local time zone.

import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const here = path.dirname(fileURLToPath(import.meta.url));
const catalog = process.env.CATALOG_CODECS;
if (!catalog) {
  throw new Error("Set CATALOG_CODECS");
}

const TIME_KEYS = ["Data_time", "TIME", "DATALOG", "retransmission_message", "Systimestamp"];

function load(file) {
  const context = {};
  vm.runInNewContext(readFileSync(file, "utf8"), context);
  return context.decodeUplink;
}

function mulberry32(seed) {
  let state = seed;
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function generator(seed) {
  const random = mulberry32(seed);
  const byte = () => Math.floor(random() * 256);
  return { bytes: (length) => Array.from({ length }, byte) };
}

function run(decode, fPort, bytes) {
  let result;
  try {
    result = decode({ fPort, bytes: [...bytes], variables: {} });
  } catch (error) {
    return { error: String(error) };
  }
  const data = result?.data ?? null;
  if (data !== null) {
    for (const key of TIME_KEYS) delete data[key];
  }
  return { data, errors: result?.errors ?? null };
}

const vectors = {};

function add(device, decode, cases) {
  vectors[device] = cases.map(([fPort, bytes]) => ({
    f_port: fPort,
    data: bytes,
    js: run(decode, fPort, bytes),
  }));
}

{
  const g = generator(1);
  const cases = [[2, [13, 10, 7, 233, 0, 0, 0, 1]]];
  for (let i = 0; i < 60; i++) cases.push([2, g.bytes(8)]);
  for (const distance of [0, 20, 21, 65535]) {
    const bytes = g.bytes(8);
    bytes.splice(2, 2, distance >> 8, distance & 0xff);
    cases.push([2, bytes]);
  }
  add("ldds75", load(`${catalog}/ldds75.js`), cases);
}

for (const [device, seed] of [["lds02", 2], ["lwl02", 3]]) {
  const g = generator(seed);
  const cases = [];
  for (const mode of [0, 1, 2, 3, 4, 255]) {
    for (let i = 0; i < 12; i++) {
      const bytes = g.bytes(10);
      bytes[2] = mode;
      cases.push([10, bytes]);
    }
  }
  for (const length of [9, 11]) {
    const bytes = g.bytes(length);
    bytes[2] = 1;
    cases.push([10, bytes]);
  }
  add(device, load(`${catalog}/${device}.js`), cases);
}

{
  const g = generator(4);
  const cases = [[2, [203, 198, 0, 130, 0, 242, 1, 127, 255, 127, 255]]];
  for (let external = 0; external < 16; external++) {
    for (let i = 0; i < 6; i++) {
      const length = external === 4 || i >= 4 ? 15 : 11;
      const bytes = g.bytes(length);
      bytes[6] = external;
      cases.push([2, bytes]);
    }
  }
  for (const external of [1, 2, 11]) {
    const bytes = g.bytes(11);
    bytes[6] = external;
    bytes.splice(7, 2, 0x7f, 0xff);
    cases.push([2, bytes]);
  }
  for (const flags of [0x40, 0x80, 0xc0]) {
    const bytes = g.bytes(11);
    bytes[6] = flags | 1;
    cases.push([2, bytes]);
  }
  for (let i = 0; i < 8; i++) cases.push([5, g.bytes(7)]);
  add("lht65n", load(`${catalog}/lht65n.js`), cases);
}

{
  const g = generator(5);
  const cases = [[2, [14, 28, 9, 246, 0, 101, 83, 241, 0]]];
  for (let i = 0; i < 40; i++) cases.push([2, g.bytes(9)]);
  for (let i = 0; i < 8; i++) cases.push([5, g.bytes(7)]);
  add("t68dl", load(`${catalog}/t68dl.js`), cases);
}

{
  const g = generator(6);
  const cases = [];
  for (let mode = 0; mode < 9; mode++) {
    for (const hardware of [0, 1, 2, 3]) {
      for (let i = 0; i < 3; i++) {
        const bytes = g.bytes(11);
        bytes[10] = (hardware << 6) | mode;
        cases.push([2, bytes]);
      }
    }
  }
  for (let i = 0; i < 8; i++) cases.push([5, g.bytes(7)]);
  add("lt22222l", load(`${catalog}/lt-22222-l.js`), cases);
}

{
  const g = generator(7);
  const cases = [];
  for (let i = 0; i < 64; i++) cases.push([2, g.bytes(11)]);
  for (let i = 0; i < 64; i++) cases.push([6, g.bytes(i % 2 ? 11 : 10)]);
  for (let b0 = 0; b0 < 64; b0++) cases.push([7, [b0]]);
  for (let band = 0; band < 16; band++) {
    const bytes = g.bytes(7);
    bytes[0] = 0x20;
    bytes[3] = band;
    cases.push([5, bytes]);
  }
  for (let i = 0; i < 4; i++) cases.push([5, g.bytes(7)]);
  for (const [fPort, length] of [[2, 10], [2, 12], [6, 9], [6, 12], [5, 6], [7, 0]]) {
    cases.push([fPort, g.bytes(length)]);
  }
  add("cpl03lb", load(`${catalog}/cpl03-lb.js`), cases);
}

writeFileSync(path.join(here, "vectors.json"), JSON.stringify(vectors) + "\n");
console.log(Object.entries(vectors).map(([k, v]) => `${k}: ${v.length}`).join("\n"));
