export function Header() {
  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 30,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 24,
        padding: "0 28px",
        height: 62,
        background: "rgba(250,248,244,0.92)",
        backdropFilter: "blur(8px)",
        borderBottom: "1px solid #E4DFD4",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div
          style={{
            width: 22,
            height: 22,
            borderRadius: "50%",
            border: "2px solid #2F6E70",
            display: "grid",
            placeItems: "center",
          }}
        >
          <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#B4442B" }} />
        </div>
        <div style={{ fontFamily: "var(--font-newsreader), Georgia, serif", fontSize: 21, letterSpacing: "-0.01em" }}>Baseline</div>
      </div>

    </header>
  );
}
