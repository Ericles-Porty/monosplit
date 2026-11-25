import { slotColor, type Palette } from "../theme/Theme";

/** Service marker: the service colour with its number, so identity never depends on colour alone. */
export function Swatch({ palette, slot }: { palette: Palette; slot: number }) {
  const onYellow = slot === 3;
  return (
    <span className={onYellow ? "swatch on-yellow" : "swatch"} style={{ background: slotColor(palette, slot) }} aria-hidden="true">
      {slot + 1}
    </span>
  );
}
