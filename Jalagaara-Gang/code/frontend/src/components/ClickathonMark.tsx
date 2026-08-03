// CLICK-<mask>-THON wordmark, drawn as vectors so it stays crisp at any size and
// inherits the colour of whatever holds it (the .brand-logo tile).

// 7-row pixel font; each glyph carries its own width so the spacing stays tight.
const GLYPHS: Record<string, string[]> = {
  C: [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
  L: ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
  I: ["###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
  K: ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
  T: ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
  H: ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
  O: [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
  N: ["#...#", "##..#", "#.#.#", "#.#.#", "#.#.#", "#..##", "#...#"],
  "-": ["...", "...", "...", "###", "...", "...", "..."],
};

const LEFT = "CLICK-";
const RIGHT = "-THON";
const MASK_W = 9;
const GAP = 1;

type Cell = { x: number; y: number };

function layout(text: string, startX: number): { cells: Cell[]; nextX: number } {
  const cells: Cell[] = [];
  let x = startX;
  for (const ch of text) {
    const rows = GLYPHS[ch];
    rows.forEach((row, y) =>
      [...row].forEach((px, i) => px === "#" && cells.push({ x: x + i, y }))
    );
    x += rows[0].length + GAP;
  }
  return { cells, nextX: x };
}

const left = layout(LEFT, 0);
const maskX = left.nextX;
const right = layout(RIGHT, maskX + MASK_W + GAP);
const WIDTH = right.nextX - GAP;

export function ClickathonMark({ className = "" }: { className?: string }) {
  return (
    <svg
      className={`clickathon-mark ${className}`.trim()}
      viewBox={`0 0 ${WIDTH} 7`}
      role="img"
      aria-label="Click-a-thon"
      shapeRendering="crispEdges"
    >
      {[...left.cells, ...right.cells].map((c) => (
        <rect key={`${c.x}-${c.y}`} x={c.x} y={c.y} width="1" height="1" fill="currentColor" />
      ))}

      {/* Masked face: smooth shape against the blocky letters, as in the logo. */}
      <g transform={`translate(${maskX} 0)`} shapeRendering="geometricPrecision">
        <rect x="0" y="0" width={MASK_W} height="7" rx="2.6" fill="currentColor" />
        <polygon points="1.5,2.35 4.05,2.95 4.05,4.45 1.5,3.85" fill="var(--clickathon-eye, #ffe000)" />
        <polygon points="7.5,2.35 4.95,2.95 4.95,4.45 7.5,3.85" fill="var(--clickathon-eye, #ffe000)" />
      </g>
    </svg>
  );
}
