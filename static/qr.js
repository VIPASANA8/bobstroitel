// A QR encoder small enough to inline, because the page cannot fetch one.
//
// Byte mode, error correction level M, versions 1-6 (up to 106 bytes). That is
// far more than a TRON address needs -- 34 characters land in version 3 -- and
// stopping at 6 drops the whole version-information block, which only exists
// from version 7 and would be one more thing to get subtly wrong. Anything
// longer returns null and the caller shows the address without a code rather
// than a code that does not scan.
//
// Structure follows Nayuki's reference implementation (module placement, format
// bits, penalty rules), which is the shape every correct encoder has. The
// coordinates here are (x = column, y = row) for the same reason: so the
// placement code reads the same as the reference it was checked against.
window.Poker8QR = (() => {
  //: version -> [ec codewords per block, blocks in group 1, data per block in
  //: group 1, blocks in group 2, data per block in group 2]. Level M only.
  const BLOCKS = {
    1: [10, 1, 16, 0, 0],
    2: [16, 1, 28, 0, 0],
    3: [26, 1, 44, 0, 0],
    4: [18, 2, 32, 0, 0],
    5: [24, 2, 43, 0, 0],
    6: [16, 4, 27, 0, 0],
  };
  const ALIGN = { 1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34] };
  const MAX_VERSION = 6;

  // GF(256) with the QR primitive polynomial x^8 + x^4 + x^3 + x^2 + 1.
  const EXP = new Uint8Array(512);
  const LOG = new Uint8Array(256);
  for (let i = 0, x = 1; i < 255; i++) {
    EXP[i] = x;
    LOG[x] = i;
    x <<= 1;
    if (x & 0x100) x ^= 0x11d;
  }
  for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255];
  const mul = (a, b) => (a === 0 || b === 0 ? 0 : EXP[LOG[a] + LOG[b]]);

  // (x - a^0)(x - a^1)...(x - a^(degree-1)), highest power first -- remainder()
  // divides by it in place and needs the leading 1 at index 0.
  function generator(degree) {
    let poly = [1];
    for (let d = 0; d < degree; d++) {
      const next = new Array(poly.length + 1).fill(0);
      for (let i = 0; i < poly.length; i++) {
        next[i] ^= poly[i];                        // times x
        next[i + 1] ^= mul(poly[i], EXP[d]);       // times a^d
      }
      poly = next;
    }
    return poly;
  }

  function remainder(data, count) {
    const gen = generator(count);
    const work = new Uint8Array(data.length + count);
    work.set(data);
    for (let i = 0; i < data.length; i++) {
      const factor = work[i];
      if (!factor) continue;
      for (let j = 0; j < gen.length; j++) work[i + j] ^= mul(gen[j], factor);
    }
    return Array.from(work.slice(data.length));
  }

  const dataCodewords = version => {
    const [, g1, d1, g2, d2] = BLOCKS[version];
    return g1 * d1 + g2 * d2;
  };

  function codewordsFor(bytes, version) {
    const capacity = dataCodewords(version) * 8;
    const bits = [];
    const push = (value, width) => {
      for (let i = width - 1; i >= 0; i--) bits.push((value >>> i) & 1);
    };
    push(0b0100, 4);          // byte mode
    push(bytes.length, 8);    // character count -- 8 bits below version 10
    for (const byte of bytes) push(byte, 8);
    push(0, Math.min(4, capacity - bits.length));
    while (bits.length % 8) bits.push(0);
    for (let i = 0; bits.length < capacity; i++) push(i % 2 ? 0x11 : 0xec, 8);

    const all = [];
    for (let i = 0; i < bits.length; i += 8) {
      let byte = 0;
      for (let j = 0; j < 8; j++) byte = (byte << 1) | bits[i + j];
      all.push(byte);
    }

    // Split into blocks, add the check codewords, then interleave both --
    // a burst of damage then lands across blocks instead of destroying one.
    const [ecCount, g1, d1, g2, d2] = BLOCKS[version];
    const blocks = [];
    let at = 0;
    for (let i = 0; i < g1; i++) blocks.push(all.slice(at, (at += d1)));
    for (let i = 0; i < g2; i++) blocks.push(all.slice(at, (at += d2)));
    const checks = blocks.map(block => remainder(block, ecCount));
    const out = [];
    const longest = Math.max(...blocks.map(block => block.length));
    for (let i = 0; i < longest; i++) {
      for (const block of blocks) if (i < block.length) out.push(block[i]);
    }
    for (let i = 0; i < ecCount; i++) for (const check of checks) out.push(check[i]);
    return out;
  }

  function formatBits(mask) {
    const data = (0b00 << 3) | mask;   // level M
    let rem = data;
    for (let i = 0; i < 10; i++) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
    return ((data << 10) | rem) ^ 0x5412;
  }

  const MASKS = [
    (x, y) => (x + y) % 2 === 0,
    (x, y) => y % 2 === 0,
    (x, y) => x % 3 === 0,
    (x, y) => (x + y) % 3 === 0,
    (x, y) => (Math.floor(y / 2) + Math.floor(x / 3)) % 2 === 0,
    (x, y) => ((x * y) % 2) + ((x * y) % 3) === 0,
    (x, y) => (((x * y) % 2) + ((x * y) % 3)) % 2 === 0,
    (x, y) => (((x + y) % 2) + ((x * y) % 3)) % 2 === 0,
  ];

  function build(bytes, version) {
    const size = version * 4 + 17;
    const grid = Array.from({ length: size }, () => new Array(size).fill(false));
    const fixed = Array.from({ length: size }, () => new Array(size).fill(false));
    const set = (x, y, dark) => {
      grid[y][x] = dark;
      fixed[y][x] = true;
    };

    const finder = (cx, cy) => {
      for (let dy = -4; dy <= 4; dy++) {
        for (let dx = -4; dx <= 4; dx++) {
          const dist = Math.max(Math.abs(dx), Math.abs(dy));
          const x = cx + dx;
          const y = cy + dy;
          if (x >= 0 && x < size && y >= 0 && y < size) set(x, y, dist !== 2 && dist !== 4);
        }
      }
    };
    finder(3, 3);
    finder(size - 4, 3);
    finder(3, size - 4);

    for (let i = 0; i < size; i++) {
      if (!fixed[6][i]) set(i, 6, i % 2 === 0);
      if (!fixed[i][6]) set(6, i, i % 2 === 0);
    }

    const centers = ALIGN[version];
    for (const cy of centers) {
      for (const cx of centers) {
        // The three corners are already finder patterns.
        const corner = (cx === 6 && cy === 6)
          || (cx === 6 && cy === size - 7) || (cx === size - 7 && cy === 6);
        if (corner) continue;
        for (let dy = -2; dy <= 2; dy++) {
          for (let dx = -2; dx <= 2; dx++) {
            set(cx + dx, cy + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
          }
        }
      }
    }

    const drawFormat = mask => {
      const bits = formatBits(mask);
      const bit = i => ((bits >>> i) & 1) === 1;
      for (let i = 0; i <= 5; i++) set(8, i, bit(i));
      set(8, 7, bit(6));
      set(8, 8, bit(7));
      set(7, 8, bit(8));
      for (let i = 9; i < 15; i++) set(14 - i, 8, bit(i));
      for (let i = 0; i < 8; i++) set(size - 1 - i, 8, bit(i));
      for (let i = 8; i < 15; i++) set(8, size - 15 + i, bit(i));
      set(8, size - 8, true);   // the always-dark module
    };
    drawFormat(0);              // reserve the areas before the data goes in

    const codewords = codewordsFor(bytes, version);
    let bitIndex = 0;
    let upward = true;
    for (let right = size - 1; right >= 1; right -= 2) {
      if (right === 6) right = 5;      // the vertical timing column is not data
      for (let step = 0; step < size; step++) {
        for (let column = 0; column < 2; column++) {
          const x = right - column;
          const y = upward ? size - 1 - step : step;
          if (fixed[y][x]) continue;
          const total = codewords.length * 8;
          grid[y][x] = bitIndex < total
            && ((codewords[bitIndex >>> 3] >>> (7 - (bitIndex & 7))) & 1) === 1;
          bitIndex++;
        }
      }
      upward = !upward;
    }
    return { grid, fixed, size, drawFormat };
  }

  function penalty(grid, size) {
    let score = 0;
    const runs = line => {
      let run = 1;
      for (let i = 1; i < size; i++) {
        if (line[i] === line[i - 1]) {
          run++;
          if (run === 5) score += 3;
          else if (run > 5) score += 1;
        } else run = 1;
      }
    };
    for (let y = 0; y < size; y++) runs(grid[y]);
    for (let x = 0; x < size; x++) runs(grid.map(row => row[x]));

    for (let y = 0; y < size - 1; y++) {
      for (let x = 0; x < size - 1; x++) {
        const c = grid[y][x];
        if (c === grid[y][x + 1] && c === grid[y + 1][x] && c === grid[y + 1][x + 1]) score += 3;
      }
    }

    // 1011101 with four light modules on either side, in both directions.
    const FINDERISH = [true, false, true, true, true, false, true];
    const looksLikeFinder = (line, at) => {
      for (let i = 0; i < 7; i++) if (line[at + i] !== FINDERISH[i]) return false;
      const before = line.slice(Math.max(0, at - 4), at);
      const after = line.slice(at + 7, at + 11);
      const clear = part => part.length === 4 && part.every(cell => !cell);
      return clear(before) || clear(after);
    };
    const scan = line => {
      for (let i = 0; i + 7 <= size; i++) if (looksLikeFinder(line, i)) score += 40;
    };
    for (let y = 0; y < size; y++) scan(grid[y]);
    for (let x = 0; x < size; x++) scan(grid.map(row => row[x]));

    let dark = 0;
    for (const row of grid) for (const cell of row) if (cell) dark++;
    const percent = (dark * 100) / (size * size);
    score += Math.floor(Math.abs(percent - 50) / 5) * 10;
    return score;
  }

  /** The module grid for `text`, or null when it does not fit version 6. */
  function matrix(text) {
    const bytes = [];
    for (const char of String(text)) {
      const code = char.codePointAt(0);
      // Byte mode is Latin-1 by specification; anything above it would have to
      // be declared as UTF-8 through an ECI header we do not emit.
      if (code > 0xff) return null;
      bytes.push(code);
    }
    let version = 0;
    for (let candidate = 1; candidate <= MAX_VERSION; candidate++) {
      // 4 mode bits + 8 count bits, then the payload.
      if (dataCodewords(candidate) * 8 >= 12 + bytes.length * 8) {
        version = candidate;
        break;
      }
    }
    if (!version) return null;

    const { grid, fixed, size, drawFormat } = build(bytes, version);
    let best = null;
    for (let mask = 0; mask < 8; mask++) {
      const candidate = grid.map(row => row.slice());
      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          if (!fixed[y][x] && MASKS[mask](x, y)) candidate[y][x] = !candidate[y][x];
        }
      }
      // Format bits are part of what the penalty sees, so they go on first.
      const bits = formatBits(mask);
      const bit = i => ((bits >>> i) & 1) === 1;
      const put = (x, y, dark) => { candidate[y][x] = dark; };
      for (let i = 0; i <= 5; i++) put(8, i, bit(i));
      put(8, 7, bit(6));
      put(8, 8, bit(7));
      put(7, 8, bit(8));
      for (let i = 9; i < 15; i++) put(14 - i, 8, bit(i));
      for (let i = 0; i < 8; i++) put(size - 1 - i, 8, bit(i));
      for (let i = 8; i < 15; i++) put(8, size - 15 + i, bit(i));
      put(8, size - 8, true);

      const score = penalty(candidate, size);
      if (best === null || score < best.score) best = { score, grid: candidate };
    }
    void drawFormat;
    return best.grid;
  }

  /**
   * `text` as an inline SVG, or null when it will not fit.
   *
   * Always light-on-dark-free: a scanner needs a light quiet zone and light
   * background, so the code carries its own regardless of the panel it sits on.
   */
  function svg(text, options = {}) {
    const grid = matrix(text);
    if (!grid) return null;
    const quiet = options.quiet ?? 4;
    const side = grid.length + quiet * 2;
    let path = "";
    for (let y = 0; y < grid.length; y++) {
      for (let x = 0; x < grid.length; x++) {
        if (grid[y][x]) path += `M${x + quiet} ${y + quiet}h1v1h-1z`;
      }
    }
    const label = options.label || "QR-код";
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${side} ${side}"`
      + ` width="100%" height="100%" shape-rendering="crispEdges" role="img"`
      + ` aria-label="${label}"><rect width="${side}" height="${side}" fill="#ffffff"/>`
      + `<path d="${path}" fill="#0b0c10"/></svg>`;
  }

  return { matrix, svg };
})();
